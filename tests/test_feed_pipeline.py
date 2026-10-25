"""Tests for RSS ingestion, timestamp parsing and source deduplication."""
from pathlib import Path

import pytest

from market_engine.db import connect, init_db
from market_engine.feed_pipeline import ingest_feeds, parse_feed, parse_timestamp

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>Company announces quarterly results</title>
<link>https://example.com/news/1</link>
<pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate>
<description>Short test excerpt.</description></item>
</channel></rss>"""


def test_parse_rss_entry_keeps_link_and_utc_timestamp():
    """Headline metadata is extracted without requesting the linked article."""
    records = parse_feed(RSS, {"id": "test-feed", "source_type": "news_rss"})
    assert len(records) == 1
    assert records[0]["title"] == "Company announces quarterly results"
    assert records[0]["url"] == "https://example.com/news/1"
    assert records[0]["published_at"] == "2026-10-05T10:00:00+00:00"
    assert records[0]["text_excerpt"] == "Short test excerpt."


def test_parse_atom_feed():
    """Atom namespace prefixes do not prevent headline and link extraction."""
    atom = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Atom headline</title>
      <link href="https://example.com/atom/2" rel="alternate"/>
      <updated>2026-10-05T12:30:00Z</updated></entry></feed>'''
    records = parse_feed(atom, {"id": "atom", "source_type": "news_rss"})
    assert records[0]["title"] == "Atom headline"
    assert records[0]["published_at"] == "2026-10-05T12:30:00+00:00"


def test_bad_timestamp_is_null_not_fabricated():
    """Unparseable provider dates remain unknown instead of being guessed."""
    assert parse_timestamp("not a date") is None


def test_feed_pipeline_deduplicates_persisted_records(tmp_path: Path):
    """The same feed item is stored once across repeated ingestion runs."""
    database = tmp_path / "test.sqlite3"
    init_db(database)
    config = tmp_path / "feeds.yaml"
    config.write_text(
        "feeds:\n"
        "  - id: test\n"
        "    name: Test feed\n"
        "    source_type: news_rss\n"
        "    url: https://example.com/feed.xml\n"
        "    enabled: true\n",
        encoding="utf-8",
    )
    def fetcher(url: str) -> bytes:
        return RSS
    first = ingest_feeds(config, db_path=database, fetcher=fetcher, delay_seconds=0)
    second = ingest_feeds(config, db_path=database, fetcher=fetcher, delay_seconds=0)
    assert first["records_inserted"] == 1
    assert second["records_inserted"] == 0
    assert second["duplicates_skipped"] == 1
    with connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 1


def test_dry_run_does_not_write_records(tmp_path: Path):
    """Dry run fetches and parses but leaves the database unchanged."""
    database = tmp_path / "dry.sqlite3"
    init_db(database)
    config = tmp_path / "feeds.yaml"
    config.write_text(
        "feeds:\n"
        "  - id: test\n"
        "    name: Test feed\n"
        "    source_type: news_rss\n"
        "    url: https://example.com/feed.xml\n"
        "    enabled: true\n",
        encoding="utf-8",
    )
    result = ingest_feeds(config, db_path=database, dry_run=True,
                          fetcher=lambda url: RSS, delay_seconds=0)
    assert result["records_seen"] == 1
    assert result["records_inserted"] == 1
    with connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 0


def test_non_https_feed_url_is_rejected(tmp_path: Path):
    """Plain HTTP is rejected so credentials and feed content are not sent unencrypted."""
    config = tmp_path / "feeds.yaml"
    config.write_text(
        "feeds:\n"
        "  - id: test\n"
        "    url: http://example.com/feed.xml\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Only HTTPS"):
        ingest_feeds(config, fetcher=lambda url: RSS, delay_seconds=0)
