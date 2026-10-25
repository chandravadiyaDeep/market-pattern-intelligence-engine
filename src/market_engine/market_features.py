"""Point-in-time market features computed only from prices available as of each bar."""
from dataclasses import dataclass
from math import sqrt
from statistics import stdev


@dataclass(frozen=True)
class PriceBar:
    """One daily close. Date must be an ISO date or comparable sortable string."""
    date: str
    close: float
    volume: float | None = None


def validate_bars(bars: list[PriceBar]) -> None:
    """Reject invalid prices and unsorted/duplicate dates before calculating features."""
    if not bars:
        raise ValueError("At least one price bar is required")
    previous_date: str | None = None
    for bar in bars:
        if bar.close <= 0:
            raise ValueError("Closing prices must be positive")
        if bar.volume is not None and bar.volume < 0:
            raise ValueError("Volume cannot be negative")
        if previous_date is not None and bar.date <= previous_date:
            raise ValueError("Price bars must have unique, ascending dates")
        previous_date = bar.date


def daily_returns(bars: list[PriceBar]) -> list[float | None]:
    """Return close-to-close returns; the first row has no prior bar and is None."""
    validate_bars(bars)
    returns: list[float | None] = [None]
    returns.extend(
        bars[index].close / bars[index - 1].close - 1.0
        for index in range(1, len(bars))
    )
    return returns


def build_market_features(
    bars: list[PriceBar], momentum_windows: tuple[int, ...] = (5, 20),
    volatility_window: int = 20, annualization_days: int = 252,
) -> list[dict[str, float | str | None]]:
    """Build trailing momentum and realized volatility for each date.

    Each output row only uses prices dated on or before that row. Early values are None
    when there is insufficient history; no forward filling is performed.
    """
    validate_bars(bars)
    if any(window < 1 for window in momentum_windows):
        raise ValueError("Momentum windows must be positive")
    if volatility_window < 2 or annualization_days < 1:
        raise ValueError("volatility_window must be >= 2 and annualization_days positive")

    returns = daily_returns(bars)
    rows: list[dict[str, float | str | None]] = []
    for index, bar in enumerate(bars):
        row: dict[str, float | str | None] = {
            "date": bar.date,
            "close": bar.close,
            "daily_return": returns[index],
        }
        for window in momentum_windows:
            row[f"momentum_{window}"] = (
                bar.close / bars[index - window].close - 1.0
                if index >= window else None
            )
        trailing_returns = [
            value for value in returns[max(1, index - volatility_window + 1):index + 1]
            if value is not None
        ]
        row[f"volatility_{volatility_window}_annualized"] = (
            stdev(trailing_returns) * sqrt(annualization_days)
            if len(trailing_returns) == volatility_window else None
        )
        rows.append(row)
    return rows


def benchmark_relative_returns(
    stock_returns: list[float | None], benchmark_returns: list[float | None]
) -> list[float | None]:
    """Subtract benchmark returns from stock returns at matching dates.

    Callers must align both series by the same trading dates before passing them here.
    """
    if len(stock_returns) != len(benchmark_returns):
        raise ValueError("Stock and benchmark return series must have equal length")
    result: list[float | None] = []
    for stock, benchmark in zip(stock_returns, benchmark_returns, strict=True):
        result.append(None if stock is None or benchmark is None else stock - benchmark)
    return result
