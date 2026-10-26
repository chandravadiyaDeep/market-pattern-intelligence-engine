"""Mathematical tests for the general benchmark-relative event study."""
import pytest

from market_engine.event_study import run_event_study


def test_event_study_calculates_cumulative_abnormal_return():
    """For each session, the log-relative wealth return equals stock growth over benchmark."""
    prices = {
        "TCS": {
            "2026-01-01": 100.0,
            "2026-01-02": 110.0,
            "2026-01-05": 121.0,
            "2026-01-06": 121.0,
        },
        "NIFTY50": {
            "2026-01-01": 100.0,
            "2026-01-02": 105.0,
            "2026-01-05": 110.25,
            "2026-01-06": 110.25,
        },
    }
    result = run_event_study(
        [{"id": 7, "symbol": "TCS", "event_type": "any_event", "disclosed_at": "2026-01-01T18:00:00+05:30"}],
        prices, "NIFTY50", horizons=(1, 2),
    )
    assert result["status"] == "ok"
    one_day = result["events"][0]["horizons"]["1"]
    assert one_day["stock_return"] == pytest.approx(0.1)
    assert one_day["benchmark_return"] == pytest.approx(0.05)
    assert one_day["abnormal_return"] == pytest.approx(1.1 / 1.05 - 1.0)
    assert result["overall"]["1"]["observations"] == 1
    assert result["overall"]["1"]["standard_error"] is None


def test_event_study_requires_strictly_post_disclosure_session():
    """No same-calendar-day close is used if disclosure time is ambiguous."""
    prices = {
        "ABC": {"2026-01-01": 100, "2026-01-02": 101, "2026-01-05": 102},
        "NIFTY50": {"2026-01-01": 100, "2026-01-02": 100, "2026-01-05": 100},
    }
    result = run_event_study(
        [{"id": 1, "symbol": "ABC", "event_type": "other", "disclosed_at": "2026-01-01T09:00:00+05:30"}],
        prices, "NIFTY50", horizons=(1,),
    )
    assert result["events"][0]["first_eligible_session"] == "2026-01-02"


def test_event_study_skips_missing_prices_and_reports_empty_benchmark():
    """Missing histories produce explicit status and skip reasons, not fabricated values."""
    result = run_event_study(
        [{"id": 1, "symbol": "MISSING", "event_type": "other", "disclosed_at": "2026-01-01"}],
        {"NIFTY50": {"2026-01-01": 100, "2026-01-02": 101}}, "NIFTY50", horizons=(1,),
    )
    assert result["status"] == "insufficient_data"
    assert result["events_analyzed"] == 0
    assert result["skipped_counts"]["missing_stock_price_history"] == 1
    no_benchmark = run_event_study([], {}, "NIFTY50", horizons=(1,))
    assert no_benchmark["status"] == "insufficient_data"


def test_event_study_rejects_nonpositive_prices_and_invalid_horizons():
    """Log-return calculations must reject mathematically invalid inputs."""
    with pytest.raises(ValueError):
        run_event_study([], {"NIFTY50": {"2026-01-01": 0}}, "NIFTY50")
    with pytest.raises(ValueError):
        run_event_study([], {"NIFTY50": {"2026-01-01": 100}}, "NIFTY50", horizons=(0,))
