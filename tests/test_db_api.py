"""API tests use an isolated temporary SQLite database."""
from fastapi.testclient import TestClient
from market_engine import db
from market_engine.api import app


def test_health_and_event_timeline(monkeypatch, tmp_path):
    database = str(tmp_path / "test.sqlite3")
    monkeypatch.setenv("MPIE_DATABASE_PATH", database)
    monkeypatch.setenv("MARKET_ENGINE_DB", database)
    db.init_db(database)
    with TestClient(app) as client:
        assert client.get("/health").json()["live_trading"] is False
        source = client.post("/sources", json={
            "source_type": "official_filing",
            "title": "Example filing",
            "url": "https://example.com/filing/1",
            "published_at": "2026-01-01T10:00:00Z",
            "first_seen_at": "2026-01-01T10:01:00Z",
            "retrieved_at": "2026-01-01T10:02:00Z",
            "content_hash": "hash-1"
        })
        assert source.status_code == 201
        event = client.post("/events", json={
            "symbol": "reliance",
            "event_type": "governance",
            "title": "Example governance update",
            "summary": "Synthetic test record, not real news.",
            "disclosed_at": "2026-01-01T10:00:00Z",
            "source_id": source.json()["id"],
            "status": "official"
        })
        assert event.status_code == 201
        assert client.get("/events?symbol=RELIANCE").json()["count"] == 1


def test_forecast_outcome_is_immutable(monkeypatch, tmp_path):
    database = str(tmp_path / "test.sqlite3")
    monkeypatch.setenv("MPIE_DATABASE_PATH", database)
    monkeypatch.setenv("MARKET_ENGINE_DB", database)
    db.init_db(database)
    with TestClient(app) as client:
        response = client.post("/predictions", json={
            "symbol": "TCS",
            "target_name": "negative sector-relative return in 5 sessions",
            "horizon_sessions": 5,
            "probability": 0.35,
            "model_name": "baseline",
            "model_version": "0.1",
            "as_of": "2026-01-01T10:00:00Z"
        })
        assert response.status_code == 201
        pid = response.json()["id"]
        resolved = client.post(f"/predictions/{pid}/outcome?outcome=0&outcome_at=2026-01-08T10:00:00Z")
        assert resolved.status_code == 200
        second = client.post(f"/predictions/{pid}/outcome?outcome=1&outcome_at=2026-01-09T10:00:00Z")
        assert second.status_code == 409
