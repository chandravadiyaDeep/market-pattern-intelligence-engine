"""General event-study statistics for measuring post-disclosure market response.

This module does not assume any particular event category. Events must have a disclosure
date and are aligned conservatively to the first stock session strictly after that date.
Results are descriptive historical estimates, not causal proof or guaranteed forecasts.
"""
from collections import defaultdict
from math import exp, isfinite, log, sqrt
from statistics import mean, median, stdev
from typing import Any


def _validate_price_series(series: dict[str, float], label: str) -> None:
    """Reject invalid price values before taking logarithms."""
    for date, value in series.items():
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{label} prices must be finite and positive; invalid value on {date}")


def _summarize(values: list[float]) -> dict[str, float | int | None]:
    """Summarize event-level cumulative abnormal log returns with a normal CI approximation."""
    n = len(values)
    if n == 0:
        return {
            "observations": 0, "mean_abnormal_return": None, "median_abnormal_return": None,
            "standard_deviation": None, "standard_error": None, "t_statistic": None,
            "ci95_low_log_return": None, "ci95_high_log_return": None,
        }
    # Convert log-relative return to relative wealth return only after summing daily log returns.
    relative_returns = [exp(value) - 1.0 for value in values]
    average_log_return = mean(values)
    sd = stdev(values) if n >= 2 else None
    standard_error = sd / sqrt(n) if sd is not None else None
    return {
        "observations": n,
        "mean_abnormal_return": mean(relative_returns),
        "median_abnormal_return": median(relative_returns),
        "mean_abnormal_log_return": average_log_return,
        "standard_deviation": sd,
        "standard_error": standard_error,
        # This is a diagnostic t-statistic; small samples need a Student-t interval instead.
        "t_statistic": average_log_return / standard_error if standard_error else None,
        "ci95_low_log_return": average_log_return - 1.96 * standard_error if standard_error is not None else None,
        "ci95_high_log_return": average_log_return + 1.96 * standard_error if standard_error is not None else None,
    }


def run_event_study(
    events: list[dict[str, Any]],
    prices_by_symbol: dict[str, dict[str, float]],
    benchmark_symbol: str,
    horizons: tuple[int, ...] = (1, 3, 5, 10, 20),
) -> dict[str, Any]:
    """Estimate post-disclosure benchmark-relative returns for arbitrary event types.

    Required event fields: symbol, disclosed_at, event_type, id.
    Price series map ISO session dates to adjusted close (or a clearly declared fallback close).
    The event window starts at the first stock trading session strictly after the disclosure
    calendar date, avoiding use of the same day's close when release timing is ambiguous.
    For each horizon H, the calculation is:
      CAR_H = sum(log(P_stock,t / P_stock,t-1) - log(P_benchmark,t / P_benchmark,t-1))
    over H consecutive aligned sessions. Relative return is exp(CAR_H) - 1.
    """
    if not horizons or any(not isinstance(h, int) or h < 1 for h in horizons):
        raise ValueError("horizons must contain positive integers")
    if len(set(horizons)) != len(horizons):
        raise ValueError("horizons must be unique")
    benchmark_key = benchmark_symbol.strip().upper()
    benchmark = prices_by_symbol.get(benchmark_key)
    if not benchmark:
        return {
            "status": "insufficient_data", "reason": f"No price history found for benchmark {benchmark_key}",
            "benchmark_symbol": benchmark_key, "horizons": list(horizons), "results": [],
        }
    _validate_price_series(benchmark, f"Benchmark {benchmark_key}")
    for symbol, series in prices_by_symbol.items():
        _validate_price_series(series, symbol)
    if any(any(a >= b for a, b in zip(sorted(series), sorted(series)[1:])) for series in prices_by_symbol.values()):
        # Dict keys are unique by definition; this guard is retained for clarity in API contract.
        raise ValueError("Price session dates must be unique")

    summaries: dict[int, list[float]] = {horizon: [] for horizon in horizons}
    event_results: list[dict[str, Any]] = []
    by_type_values: dict[str, dict[int, list[float]]] = defaultdict(lambda: {h: [] for h in horizons})
    skipped: dict[str, int] = defaultdict(int)

    for event in events:
        symbol = str(event.get("symbol", "")).strip().upper()
        disclosed_at = event.get("disclosed_at")
        event_type = str(event.get("event_type") or "unspecified")
        if not symbol or not disclosed_at:
            skipped["missing_symbol_or_disclosure_time"] += 1
            continue
        stock = prices_by_symbol.get(symbol)
        if not stock:
            skipped["missing_stock_price_history"] += 1
            continue
        disclosure_date = str(disclosed_at)[:10]
        stock_dates = sorted(stock)
        # Strictly after disclosure date: conservative when intraday release time is unknown.
        start_index = next((i for i, date in enumerate(stock_dates) if date > disclosure_date), None)
        if start_index is None or start_index == 0:
            skipped["no_post_disclosure_session_with_prior_close"] += 1
            continue
        prior_date = stock_dates[start_index - 1]
        if prior_date not in benchmark:
            skipped["benchmark_missing_prior_session"] += 1
            continue
        result_item: dict[str, Any] = {
            "event_id": event.get("id"),
            "symbol": symbol,
            "event_type": event_type,
            "disclosed_at": disclosed_at,
            "first_eligible_session": stock_dates[start_index],
            "horizons": {},
        }
        has_any_horizon = False
        for horizon in horizons:
            end_index = start_index + horizon
            if end_index > len(stock_dates):
                skipped[f"insufficient_{horizon}_session_stock_history"] += 1
                continue
            window_dates = stock_dates[start_index:end_index]
            if any(date not in benchmark for date in window_dates):
                skipped[f"benchmark_missing_{horizon}_session_window"] += 1
                continue
            # Both assets must share the same previous close date and event-window dates.
            if any(
                stock_dates[index - 1] not in benchmark
                for index in range(start_index, end_index)
            ):
                skipped[f"benchmark_missing_{horizon}_session_prior_close"] += 1
                continue
            stock_log_return = sum(
                log(stock[date] / stock[stock_dates[index - 1]])
                for index, date in zip(range(start_index, end_index), window_dates, strict=True)
            )
            benchmark_log_return = sum(
                log(benchmark[date] / benchmark[stock_dates[index - 1]])
                for index, date in zip(range(start_index, end_index), window_dates, strict=True)
            )
            car = stock_log_return - benchmark_log_return
            abnormal_return = exp(car) - 1.0
            summaries[horizon].append(car)
            by_type_values[event_type][horizon].append(car)
            result_item["horizons"][str(horizon)] = {
                "stock_return": exp(stock_log_return) - 1.0,
                "benchmark_return": exp(benchmark_log_return) - 1.0,
                "abnormal_log_return": car,
                "abnormal_return": abnormal_return,
            }
            has_any_horizon = True
        if has_any_horizon:
            event_results.append(result_item)

    overall = {str(h): _summarize(values) for h, values in summaries.items()}
    grouped = {
        event_type: {str(h): _summarize(values) for h, values in horizon_values.items()}
        for event_type, horizon_values in sorted(by_type_values.items())
    }
    return {
        "status": "ok" if event_results else "insufficient_data",
        "method": "cumulative_abnormal_log_return_vs_benchmark",
        "benchmark_symbol": benchmark_key,
        "horizons_sessions": list(horizons),
        "event_alignment": "first trading session strictly after disclosure calendar date",
        "formula": "CAR_H = sum(log(stock_t/stock_prev) - log(benchmark_t/benchmark_prev)); relative_return = exp(CAR_H)-1",
        "overall": overall,
        "by_event_type": grouped,
        "events": event_results,
        "events_analyzed": len(event_results),
        "skipped_counts": dict(sorted(skipped.items())),
        "caveats": [
            "Observational event studies do not prove causation.",
            "Confidence intervals use a normal approximation and can be unreliable for small samples.",
            "Overlapping events, repeated events per issuer, market regimes and confounding news can bias estimates.",
            "Use adjusted prices where possible; verify benchmark data, dividends, corporate actions and disclosure timestamps.",
            "A positive historical abnormal return is not a validated prediction or trading signal.",
        ],
    }
