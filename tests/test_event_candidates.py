"""Tests for transparent headline triage and human-reviewed event candidates."""
from market_engine.db import connect, init_db
from market_engine.event_candidates import _compile_aliases, classify_headline, classify_source_documents


def test_classifier_requires_company_and_event_match():
    """A company-only headline or event-only headline should not create a candidate."""
    aliases = _compile_aliases()
    assert classify_headline("Reliance announces a new website", "", aliases) is None
    assert classify_headline("SEBI imposes a penalty on an unnamed firm", "", aliases) is None


def test_classifier_matches_event_and_company():
    """A clear headline maps to a candidate without claiming verification."""
    aliases = _compile_aliases()
    result = classify_headline("Reliance Industries announces quarterly results", "", aliases)
    assert result is not None
    assert result["symbol"] == "RELIANCE"
    assert result["event_type"] == "earnings"
    assert "quarterly results" in result["matched_terms"]


def test_source_documents_create_pending_review_candidates(tmp_path):
    """Candidate generation must be idempotent and keep candidates unverified."""
    db_file = tmp_path / "candidates.sqlite3"
    init_db(db_file)
    with connect(db_file) as conn:
        conn.execute(
            """INSERT INTO source_documents
            (source_type,title,url,published_at,first_seen_at,retrieved_at,content_hash,
             text_excerpt,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            ("news_rss", "Reliance Industries announces quarterly results",
             "https://example.com/reliance-results", "2026-10-20T09:00:00+00:00",
             "2026-10-20T09:01:00+00:00", "2026-10-20T09:01:00+00:00",
             "candidate-test-hash", "Quarterly results were announced.", "2026-10-20T09:01:00+00:00"),
        )
    first = classify_source_documents(db_file)
    assert first["documents_scanned"] == 1
    assert first["candidates_inserted"] == 1
    with connect(db_file) as conn:
        row = conn.execute("SELECT * FROM event_candidates").fetchone()
        assert row["symbol"] == "RELIANCE"
        assert row["status"] == "pending_review"
    second = classify_source_documents(db_file)
    assert second["documents_scanned"] == 0
    assert second["candidates_inserted"] == 0


def test_candidate_dry_run_does_not_write(tmp_path):
    """Dry-run should return proposed candidates without adding queue rows."""
    db_file = tmp_path / "dryrun.sqlite3"
    init_db(db_file)
    with connect(db_file) as conn:
        conn.execute(
            """INSERT INTO source_documents
            (source_type,title,url,published_at,first_seen_at,retrieved_at,content_hash,
             text_excerpt,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            ("news_rss", "TCS wins contract worth Rs 500 crore",
             "https://example.com/tcs-contract", "2026-10-20T09:00:00+00:00",
             "2026-10-20T09:01:00+00:00", "2026-10-20T09:01:00+00:00",
             "candidate-test-hash-2", "TCS wins contract worth Rs 500 crore.", "2026-10-20T09:01:00+00:00"),
        )
    result = classify_source_documents(db_file, dry_run=True)
    assert result["candidates_found"] == 1
    assert result["candidates_inserted"] == 0
    with connect(db_file) as conn:
        assert conn.execute("SELECT COUNT(*) FROM event_candidates").fetchone()[0] == 0
