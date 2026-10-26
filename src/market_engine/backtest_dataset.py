"""Build a point-in-time cross-sectional panel for historical universe research."""
from datetime import date
from math import isfinite, log, sqrt
from pathlib import Path
from statistics import stdev
from typing import Any

from .db import connect


def build_backtest_panel(
    start_date: str,
    end_date: str,
    source_name: str,
    db_path: str | Path | None = None,
    benchmark_symbol: str = "NIFTY50",
    momentum_windows: tuple[int, ...] = (5, 20),
    volatility_window: int = 20,
    horizon_sessions: int = 5,
) -> dict[str, Any]:
    """Create rows for companies that were constituents on each feature date.

    All prices are taken from one named source to avoid silently mixing vendors.
    Features use adjusted close when available (otherwise close) through the feature
    date only. Targets use future stock-minus-benchmark log returns over shared sessions.
    Membership is checked on the feature date; later removals do not erase historical rows.
    This function does not certify data coverage, corporate-action adjustments, or licensing.
    """
    try:
        start = date.fromisoformat(start_date).isoformat()
        end = date.fromisoformat(end_date).isoformat()
    except ValueError as exc:
        raise ValueError("start_date and end_date must use YYYY-MM-DD") from exc
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if not source_name.strip():
        raise ValueError("source_name is required so price sources are not mixed")
    if not benchmark_symbol.strip():
        raise ValueError("benchmark_symbol is required")
    if not momentum_windows or any(window < 1 for window in momentum_windows):
        raise ValueError("momentum_windows must contain positive integers")
    if volatility_window < 2 or horizon_sessions < 1:
        raise ValueError("volatility_window must be >= 2 and horizon_sessions must be positive")

    with connect(db_path) as conn:
        bar_rows = conn.execute(
            """SELECT symbol,session_date,COALESCE(adjusted_close,close) AS price
            FROM market_bars
            WHERE source_name=? ORDER BY symbol,session_date""",
            (source_name.strip(),),
        ).fetchall()
        memberships = conn.execute(
            """SELECT symbol,company_name,start_date,end_date,source_name
            FROM constituent_membership
            WHERE start_date<=? AND (end_date IS NULL OR end_date>=?)
            ORDER BY symbol,start_date DESC,retrieved_at DESC""",
            (end, start),
        ).fetchall()

    prices: dict[str, dict[str, float]] = {}
    for item in bar_rows:
        symbol = str(item["symbol"]).strip().upper()
        prices.setdefault(symbol, {})[str(item["session_date"])] = float(item["price"])

    benchmark_key = benchmark_symbol.strip().upper()
    benchmark_prices = prices.get(benchmark_key, {})
    if not benchmark_prices:
        return {
            "status": "insufficient_data", "reason": f"No benchmark bars found for {benchmark_key} from source {source_name}.",
            "rows": [], "source_name": source_name, "benchmark_symbol": benchmark_key,
        }

    max_lookback = max(max(momentum_windows), volatility_window)
    feature_names = ["stock_return_1", "benchmark_return_1", "relative_return_1"]
    feature_names.extend(f"momentum_{window}" for window in momentum_windows)
    feature_names.append(f"volatility_{volatility_window}_annualized")
    panel: list[dict[str, Any]] = []
    missing_price_symbols: set[str] = set()

    # Keep the most recently retrieved applicable interval for each symbol/date.
    membership_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for member in memberships:
        membership_by_symbol.setdefault(str(member["symbol"]).strip().upper(), []).append(dict(member))

    for symbol, intervals in membership_by_symbol.items():
        if symbol == benchmark_key:
            continue
        stock_prices = prices.get(symbol, {})
        if not stock_prices:
            missing_price_symbols.add(symbol)
            continue
        shared_dates = sorted(set(stock_prices).intersection(benchmark_prices))
        if len(shared_dates) <= max_lookback + horizon_sessions:
            continue
        stock = [float(stock_prices[day]) for day in shared_dates]
        market = [float(benchmark_prices[day]) for day in shared_dates]
        if any(not isfinite(value) or value <= 0 for value in stock + market):
            continue
        stock_returns: list[float | None] = [None] + [
            log(stock[i] / stock[i - 1]) for i in range(1, len(shared_dates))
        ]
        market_returns: list[float | None] = [None] + [
            log(market[i] / market[i - 1]) for i in range(1, len(shared_dates))
        ]

        for index, feature_date in enumerate(shared_dates):
            # The entire target horizon must be inside the requested data window.
            if feature_date < start or feature_date > end:
                continue
            target_index = index + horizon_sessions
            if target_index >= len(shared_dates) or shared_dates[target_index] > end:
                continue
            if index < max_lookback:
                continue
            active = [
                interval for interval in intervals
                if str(interval["start_date"]) <= feature_date
                and (interval["end_date"] is None or str(interval["end_date"]) >= feature_date)
            ]
            if not active:
                continue
            # Missing return values are guarded before feature calculation.
            return_start = index - volatility_window + 1
            trailing = stock_returns[return_start:index + 1]
            if any(value is None for value in trailing):
                continue
            if stock_returns[index] is None or market_returns[index] is None:
                continue

            features = [
                float(stock_returns[index]),
                float(market_returns[index]),
                float(stock_returns[index]) - float(market_returns[index]),
            ]
            for window in momentum_windows:
                features.append(log(stock[index] / stock[index - window]))
            features.append(stdev([float(value) for value in trailing]) * sqrt(252))
            target = (
                log(stock[target_index] / stock[index])
                - log(market[target_index] / market[index])
            )
            # This is a feature-date membership join, not today's constituent list.
            panel.append({
                "date": feature_date,
                "symbol": symbol,
                "company_name": str(active[0]["company_name"]),
                "features": features,
                "target_forward_excess_log_return": target,
                "target_end_date": shared_dates[target_index],
                "membership_source": str(active[0]["source_name"]),
                "price_source": source_name.strip(),
            })

    panel.sort(key=lambda row: (row["date"], row["symbol"]))
    return {
        "status": "ok" if panel else "insufficient_data",
        "rows": panel,
        "row_count": len(panel),
        "symbols_with_rows": len({row["symbol"] for row in panel}),
        "feature_names": feature_names,
        "benchmark_symbol": benchmark_key,
        "source_name": source_name.strip(),
        "start_date": start,
        "end_date": end,
        "horizon_sessions": horizon_sessions,
        "volatility_window": volatility_window,
        "membership_rule": "constituent interval must include feature date",
        "feature_cutoff": "feature date close; no future prices enter feature vectors",
        "target_definition": "future stock log return minus future benchmark log return",
        "missing_price_symbols": sorted(missing_price_symbols),
        "warnings": [
            "Use adjusted prices from a consistent provider; fallback to close may leave corporate-action distortion.",
            "Event features and disclosure availability timestamps are not yet joined into this panel.",
            "Rows are for research only; no execution costs or fills are simulated by this dataset builder.",
        ],
    }
