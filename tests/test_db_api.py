"""Tests for database setup and local API behavior."""
import pytest
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



def test_event_study_endpoint_requires_verified_events_and_price_history(tmp_path, monkeypatch):
    """The study uses verified events only and reports data gaps instead of guessing."""
    db_file = tmp_path / "event-study.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    with connect(db_file) as conn:
        # Unverified records must not silently enter the primary event study.
        conn.execute(
            """INSERT INTO events
            (symbol,event_type,title,summary,disclosed_at,status,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            ("TCS", "other", "Unverified test event", "test", "2026-01-01T12:00:00+00:00",
             "unverified", "2026-01-01T12:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO market_bars
            (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("NIFTY50", "2026-01-01", 100, 101, 99, 100, 100, 1000, "test", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO market_bars
            (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("NIFTY50", "2026-01-02", 101, 102, 100, 101, 101, 1000, "test", "2026-01-02T00:00:00+00:00"),
        )
    client = TestClient(app)
    response = client.get("/research/event-study?horizons=1,3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["verified_events_loaded"] == 0
    assert payload["status"] == "insufficient_data"
    assert "No forecast is generated" in payload["note"]
    invalid = client.get("/research/event-study?horizons=0,2")
    assert invalid.status_code == 422



def test_event_study_includes_official_event_and_benchmark_relative_math(tmp_path, monkeypatch):
    """Officially verified events are analyzed against aligned benchmark prices."""
    db_file = tmp_path / "event-study-official.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    with connect(db_file) as conn:
        conn.execute(
            """INSERT INTO events
            (symbol,event_type,title,summary,disclosed_at,status,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            ("TCS", "other", "Official test disclosure", "test", "2026-01-01T12:00:00+00:00",
             "official", "2026-01-01T12:00:00+00:00"),
        )
        for symbol, prices in {
            "TCS": [100.0, 110.0, 121.0],
            "NIFTY50": [100.0, 105.0, 110.25],
        }.items():
            for session_date, price in zip(
                ["2026-01-01", "2026-01-02", "2026-01-05"], prices, strict=True
            ):
                conn.execute(
                    """INSERT INTO market_bars
                    (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (symbol, session_date, price, price, price, price, price, 1000, "test",
                     f"{session_date}T00:00:00+00:00"),
                )
    response = TestClient(app).get("/research/event-study?horizons=1,2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["verified_events_loaded"] == 1
    assert payload["events_analyzed"] == 1
    one_day = payload["events"][0]["horizons"]["1"]
    assert one_day["stock_return"] == pytest.approx(0.1)
    assert one_day["benchmark_return"] == pytest.approx(0.05)
    assert one_day["abnormal_return"] == pytest.approx(1.1 / 1.05 - 1.0)



def test_event_study_endpoint_calculates_abnormal_returns_for_official_event(tmp_path, monkeypatch):
    """A verified-source event and aligned price series produce a transparent estimate."""
    db_file = tmp_path / "event-study-calculation.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    with connect(db_file) as conn:
        conn.execute(
            """INSERT INTO events
            (symbol,event_type,title,summary,disclosed_at,status,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            ("TCS", "other", "Official-source test event", "synthetic test only",
             "2026-01-01T18:00:00+00:00", "official", "2026-01-01T18:00:00+00:00"),
        )
        # Prices are synthetic unit-test fixtures, not real market observations.
        for symbol, prices in {
            "TCS": [100.0, 110.0, 121.0],
            "NIFTY50": [100.0, 105.0, 110.25],
        }.items():
            for date, price in zip(["2026-01-01", "2026-01-02", "2026-01-05"], prices, strict=True):
                conn.execute(
                    """INSERT INTO market_bars
                    (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (symbol, date, price, price, price, price, price, 1000, "test",
                     f"{date}T00:00:00+00:00"),
                )
    response = TestClient(app).get("/research/event-study?benchmark_symbol=NIFTY50&horizons=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["events_analyzed"] == 1
    assert payload["overall"]["1"]["observations"] == 1
    assert payload["events"][0]["horizons"]["1"]["abnormal_return"] == pytest.approx(1.1 / 1.05 - 1)



def test_predictive_baseline_endpoint_returns_walk_forward_metrics(tmp_path, monkeypatch):
    """The model endpoint trains on prior labels and returns an experimental estimate."""
    from datetime import date, timedelta
    from math import cos, exp, sin

    db_file = tmp_path / "predictive-baseline.sqlite3"
    monkeypatch.setattr(api_module, "connect", lambda: connect(db_file))
    init_db(db_file)
    current_date = date(2025, 1, 1)
    market_price = 100.0
    stock_price = 100.0
    inserted = 0
    with connect(db_file) as conn:
        while inserted < 100:
            if current_date.weekday() < 5:
                market_price *= exp(0.0002 + 0.002 * sin(inserted / 3))
                stock_price *= exp(0.0001 + 0.0015 * cos(inserted / 5) + 0.0008 * sin(inserted / 2))
                for symbol, price in (("TCS", stock_price), ("NIFTY50", market_price)):
                    conn.execute(
                        """INSERT INTO market_bars
                        (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (symbol, current_date.isoformat(), price, price, price, price, price,
                         1000, "synthetic-test", f"{current_date.isoformat()}T00:00:00+00:00"),
                    )
                inserted += 1
            current_date += timedelta(days=1)
    response = TestClient(app).get("/research/predictive-baseline/TCS?horizon_sessions=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["walk_forward_evaluation"]["out_of_sample_predictions"] > 0
    assert payload["latest_estimate"]["model"] == "standardized_ridge_regression"
    assert "not a trading recommendation" in payload["warning"]
