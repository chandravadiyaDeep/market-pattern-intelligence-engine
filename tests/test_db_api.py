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


def test_sources_endpoint_and_feed_registry(tmp_path, monkeypatch):
    """API exposes stored source metadata and config without triggering a fetch."""
    db_file = tmp_path / "sources.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    client = TestClient(app)
    sources = client.get("/sources")
    assert sources.status_code == 200
    assert "items" in sources.json()
    feeds = client.get("/pipeline/feeds")
    assert feeds.status_code == 200
    assert feeds.json()["count"] >= 2
    assert any(item["enabled"] for item in feeds.json()["items"])


def test_market_bars_and_trailing_features(tmp_path, monkeypatch):
    """Imported price history can be browsed and converted to trailing features."""
    db_file = tmp_path / "market-bars.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    with connect(db_file) as conn:
        for day in range(1, 8):
            conn.execute(
                """INSERT INTO market_bars
                (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("TCS", f"2026-10-{day:02d}", 100 + day, 102 + day, 99 + day,
                 101 + day, 101 + day, 1000, "test", "2026-10-25T00:00:00+00:00"),
            )
    client = TestClient(app)
    bars = client.get("/market-bars?symbol=TCS")
    assert bars.status_code == 200
    assert bars.json()["count"] == 7
    features = client.get("/market-bars/TCS/features?momentum_windows=5&volatility_window=3")
    assert features.status_code == 200
    assert features.json()["count"] == 7
    assert features.json()["items"][4]["momentum_5"] is None
    assert features.json()["items"][5]["momentum_5"] is not None


def test_research_sources_endpoint_returns_link_catalog():
    """Research links are available through the API without fetching those sites."""
    client = TestClient(app)
    response = client.get("/research-sources")
    assert response.status_code == 200
    items = response.json()["items"]
    assert response.json()["count"] >= 15
    assert any(item["id"] == "nse_announcements" for item in items)
    assert any(item["id"] == "google_trends" for item in items)
    assert all(item["url"].startswith("https://") for item in items)



def test_event_candidate_review_accepts_as_unverified_event(tmp_path, monkeypatch):
    """A reviewed candidate becomes an event but is not marked as fact-verified."""
    db_file = tmp_path / "review.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    with connect(db_file) as conn:
        source = conn.execute(
            """INSERT INTO source_documents
            (source_type,title,url,published_at,first_seen_at,retrieved_at,content_hash,
             text_excerpt,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            ("news_rss", "Reliance announces quarterly results",
             "https://example.com/reliance-results", "2026-10-20T09:00:00+00:00",
             "2026-10-20T09:01:00+00:00", "2026-10-20T09:01:00+00:00",
             "review-test-hash", "Quarterly results were announced.", "2026-10-20T09:01:00+00:00"),
        )
        source_id = int(source.lastrowid)
        candidate = conn.execute(
            """INSERT INTO event_candidates
            (source_id,symbol,event_type,title,summary,disclosed_at,matched_alias,
             matched_terms,rule_strength,classifier_version,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (source_id, "RELIANCE", "earnings", "Reliance announces quarterly results",
             "Quarterly results were announced.", "2026-10-20T09:00:00+00:00",
             "Reliance", '["quarterly results"]', 1, "rules-0.1.0",
             "pending_review", "2026-10-20T09:01:00+00:00"),
        )
        candidate_id = int(candidate.lastrowid)
    client = TestClient(app)
    queued = client.get("/event-candidates")
    assert queued.status_code == 200
    assert queued.json()["count"] == 1
    accepted = client.post(f"/event-candidates/{candidate_id}/review?decision=accept")
    assert accepted.status_code == 200
    assert accepted.json()["event_status"] == "unverified"
    with connect(db_file) as conn:
        event = conn.execute("SELECT * FROM events WHERE id=?", (accepted.json()["event_id"],)).fetchone()
        assert event["status"] == "unverified"
        candidate_row = conn.execute("SELECT status FROM event_candidates WHERE id=?", (candidate_id,)).fetchone()
        assert candidate_row["status"] == "accepted"
    repeated = client.post(f"/event-candidates/{candidate_id}/review?decision=reject")
    assert repeated.status_code == 409
