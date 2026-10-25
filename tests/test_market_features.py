"""Tests for point-in-time market feature generation."""
import pytest
from market_engine.market_features import (
    PriceBar, benchmark_relative_returns, build_market_features, daily_returns,
)


def test_daily_returns_use_previous_close():
    """First return is unavailable; later returns use the previous close."""
    bars = [PriceBar("2026-01-01", 100), PriceBar("2026-01-02", 110), PriceBar("2026-01-05", 121)]
    assert daily_returns(bars) == [None, pytest.approx(0.1), pytest.approx(0.1)]


def test_momentum_uses_only_prices_up_to_current_row():
    """A five-session momentum appears at row six and excludes future prices."""
    bars = [PriceBar(f"2026-01-{i:02d}", 100 + i) for i in range(1, 8)]
    features = build_market_features(bars, momentum_windows=(5,), volatility_window=3)
    assert features[4]["momentum_5"] is None
    assert features[5]["momentum_5"] == pytest.approx(106 / 101 - 1)
    assert features[5]["momentum_5"] != pytest.approx(107 / 101 - 1)


def test_invalid_or_unsorted_bars_are_rejected():
    """Invalid prices and duplicate/out-of-order dates must not silently pass."""
    with pytest.raises(ValueError):
        daily_returns([PriceBar("2026-01-01", 100), PriceBar("2026-01-01", 101)])
    with pytest.raises(ValueError):
        build_market_features([PriceBar("2026-01-01", 0)])


def test_benchmark_relative_returns_align_by_position():
    """Relative returns are unavailable when either series lacks a value."""
    assert benchmark_relative_returns([None, 0.03, -0.01], [None, 0.01, 0.02]) == [
        None, pytest.approx(0.02), pytest.approx(-0.03)
    ]
