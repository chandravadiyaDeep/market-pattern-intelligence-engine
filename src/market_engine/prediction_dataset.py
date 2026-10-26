"""Create leakage-aware numeric features and future excess-return targets."""
from math import isfinite, log, sqrt
from statistics import stdev
from typing import Any


def build_prediction_dataset(
    stock_prices: dict[str, float],
    benchmark_prices: dict[str, float],
    horizon_sessions: int = 5,
    momentum_windows: tuple[int, ...] = (5, 20),
    volatility_window: int = 20,
    annualization_sessions: int = 252,
) -> dict[str, Any]:
    """Build aligned rows using information through t and target returns after t.

    Prices should be adjusted closes where possible. Stock and benchmark are aligned on
    shared session dates. Features use prices/returns no later than the feature date.
    Target is the next-horizon benchmark-relative log return, so event type is not hard-coded.
    """
    if horizon_sessions < 1 or volatility_window < 2 or annualization_sessions < 1:
        raise ValueError("horizon_sessions, volatility_window and annualization_sessions are invalid")
    if not momentum_windows or any(window < 1 for window in momentum_windows):
        raise ValueError("momentum_windows must contain positive integers")
    for label, prices in (("stock", stock_prices), ("benchmark", benchmark_prices)):
        if any(not isfinite(float(price)) or float(price) <= 0 for price in prices.values()):
            raise ValueError(f"{label} prices must be finite and positive")
    dates = sorted(set(stock_prices).intersection(benchmark_prices))
    max_lookback = max(max(momentum_windows), volatility_window)
    if len(dates) <= max_lookback + horizon_sessions:
        return {
            "status": "insufficient_data", "reason": "Not enough aligned history for lookback and target horizon",
            "feature_names": [], "rows": [], "horizon_sessions": horizon_sessions,
        }

    stock = [float(stock_prices[date]) for date in dates]
    market = [float(benchmark_prices[date]) for date in dates]
    stock_returns = [None] + [log(stock[i] / stock[i - 1]) for i in range(1, len(dates))]
    market_returns = [None] + [log(market[i] / market[i - 1]) for i in range(1, len(dates))]
    feature_names = ["stock_return_1", "benchmark_return_1", "relative_return_1"]
    feature_names += [f"momentum_{window}" for window in momentum_windows]
    feature_names += [f"volatility_{volatility_window}_annualized"]
    rows: list[dict[str, Any]] = []

    for index in range(max_lookback, len(dates) - horizon_sessions):
        trailing_stock = [float(stock_returns[j]) for j in range(index - volatility_window + 1, index + 1)]
        trailing_market = [float(market_returns[j]) for j in range(index - volatility_window + 1, index + 1)]
        if any(stock_returns[j] is None or market_returns[j] is None for j in range(index - volatility_window + 1, index + 1)):
            continue
        volatility = stdev(trailing_stock) * sqrt(annualization_sessions)
        features = [
            float(stock_returns[index]),
            float(market_returns[index]),
            float(stock_returns[index]) - float(market_returns[index]),
        ]
        for window in momentum_windows:
            features.append(log(stock[index] / stock[index - window]))
        features.append(volatility)
        target = (
            log(stock[index + horizon_sessions] / stock[index])
            - log(market[index + horizon_sessions] / market[index])
        )
        rows.append({
            "date": dates[index],
            "features": features,
            "target_forward_excess_log_return": target,
            "target_end_date": dates[index + horizon_sessions],
        })
    return {
        "status": "ok" if rows else "insufficient_data",
        "feature_names": feature_names,
        "horizon_sessions": horizon_sessions,
        "target_definition": "future stock log return minus future benchmark log return",
        "feature_cutoff": "close on row date; no future prices in features",
        "rows": rows,
    }
