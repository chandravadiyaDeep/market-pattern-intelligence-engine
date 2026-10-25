"""Tests for database setup and local API behavior."""
from fastapi.testclient import TestClient
from market_engine.api import app
from market_engine import api as api_module
from market_engine.db import connect, init_db


def test_health_endpoint():
    """Health endpoint must identify research-only mode."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "research_only"


def test_event_creation_and_listing_uses_temp_database(tmp_path, monkeypatch):
    """Event endpoints should work with an isolated temporary SQLite database."""
    db_file = tmp_path / "test.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    client = TestClient(app)
    response = client.post("/events", json={
        "symbol": "reliance",
        "event_type": "earnings",
        "title": "Test event",
        "summary": "Synthetic test event only.",
        "disclosed_at": "2025-01-01T12:00:00+00:00",
        "evidence_confidence": 0.8,
        "materiality": 2,
        "status": "unverified"
    })
    assert response.status_code == 201
    assert response.json()["symbol"] == "RELIANCE"
    listed = client.get("/events?symbol=RELIANCE")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1


def test_pattern_endpoint_reports_descriptive_counts(tmp_path, monkeypatch):
    """Pattern route should count disclosed events without presenting counts as forecasts."""
    db_file = tmp_path / "patterns.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    client = TestClient(app)
    response = client.post("/events", json={
        "symbol": "HDFCBANK",
        "event_type": "governance",
        "title": "Synthetic governance event",
        "summary": "Test-only record.",
        "disclosed_at": "2026-10-01T12:00:00+00:00",
        "status": "unverified"
    })
    assert response.status_code == 201
    result = client.get("/patterns/event-counts?lookback_days=90&symbol=HDFCBANK")
    assert result.status_code == 200
    assert result.json()["event_count"] == 1
    assert result.json()["by_event_type"][0]["event_type"] == "governance"
    assert result.json()["interpretation"] == "descriptive_frequency_only_not_a_forecast"


def test_prediction_outcome_is_recorded_once(tmp_path, monkeypatch):
    """Outcome can be added after a forecast but cannot be silently rewritten."""
    db_file = tmp_path / "predictions.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    client = TestClient(app)
    created = client.post("/predictions", json={
        "symbol": "TCS",
        "target_name": "negative sector-relative return within 5 sessions",
        "horizon_sessions": 5,
        "probability": 0.35,
        "model_name": "baseline",
        "model_version": "0.1.0",
        "as_of": "2026-01-01T10:00:00+00:00"
    })
    assert created.status_code == 201
    prediction_id = created.json()["id"]
    resolved = client.post(
        f"/predictions/{prediction_id}/outcome",
        params={"outcome": 0, "outcome_at": "2026-01-08T10:00:00+00:00"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["outcome"] == 0
    repeated = client.post(
        f"/predictions/{prediction_id}/outcome",
        params={"outcome": 1, "outcome_at": "2026-01-09T10:00:00+00:00"},
    )
    assert repeated.status_code == 409
