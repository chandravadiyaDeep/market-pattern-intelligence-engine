"""Tests for point-in-time event features and verification filtering."""
from datetime import date, timedelta

from market_engine.event_features import add_event_features
from market_engine.prediction_dataset import build_prediction_dataset


def test_event_features_include_only_prior_verified_disclosures():
    """Same-day, unverified, and other-company events must not enter the features."""
    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    stock = {session_date: 100.0 + index * 0.3 for index, session_date in enumerate(dates)}
    benchmark = {session_date: 100.0 + index * 0.2 for index, session_date in enumerate(dates)}
    dataset = build_prediction_dataset(stock, benchmark, horizon_sessions=3)
    feature_date = dates[40]
    events = [
        {"symbol": "TCS", "event_type": "earnings", "disclosed_at": dates[39] + "T17:00:00+05:30", "status": "official"},
        # Same-day disclosures are conservatively excluded from a close-based feature row.
        {"symbol": "TCS", "event_type": "earnings", "disclosed_at": feature_date + "T10:00:00+05:30", "status": "official"},
        {"symbol": "TCS", "event_type": "regulatory", "disclosed_at": dates[39], "status": "unverified"},
        {"symbol": "INFY", "event_type": "earnings", "disclosed_at": dates[39], "status": "official"},
    ]

    result = add_event_features(dataset, events, "tcs")
    row = next(item for item in result["rows"] if item["date"] == feature_date)
    feature_index = {name: index for index, name in enumerate(result["feature_names"])}

    assert result["event_features_added"] is True
    assert result["verified_events_used"] == 2  # verified records for TCS, including same-day
    assert row["features"][feature_index["event_earnings_count_5s"]] == 1.0
    assert row["features"][feature_index["event_regulatory_count_5s"]] == 0.0
    assert row["features"][feature_index["any_verified_event_count_5s"]] == 1.0
    assert len(row["features"]) == len(result["feature_names"])


def test_event_features_do_not_use_events_disclosed_after_feature_date():
    """A future disclosure cannot alter an earlier row's event feature vector."""
    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    stock = {session_date: 100.0 + index for index, session_date in enumerate(dates)}
    benchmark = {session_date: 100.0 + index * 0.5 for index, session_date in enumerate(dates)}
    dataset = build_prediction_dataset(stock, benchmark, horizon_sessions=3)
    feature_date = dates[40]
    event = {
        "symbol": "TCS", "event_type": "governance",
        "disclosed_at": dates[41] + "T09:00:00+05:30", "status": "corroborated",
    }

    result = add_event_features(dataset, [event], "TCS")
    row = next(item for item in result["rows"] if item["date"] == feature_date)
    feature_index = {name: index for index, name in enumerate(result["feature_names"])}
    assert row["features"][feature_index["event_governance_count_5s"]] == 0.0
