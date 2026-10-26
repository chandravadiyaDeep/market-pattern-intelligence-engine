"""SQLite persistence for local-first research. No broker connection is provided."""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone


def database_path() -> str:
    """Resolve the DB path from environment variables or the local .env settings file."""
    direct_value = os.getenv("MPIE_DATABASE_PATH") or os.getenv("MARKET_ENGINE_DB")
    if direct_value:
        return direct_value
    # Pydantic Settings reads the optional .env file without exposing its contents.
    from .config import settings

    return settings.database_path


def now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a SQLite row to a regular dictionary for JSON responses."""
    return dict(row)


@contextmanager
def connect(db_path: str | Path | None = None):
    """Open a connection, create its parent directory, and handle transactions."""
    path = str(db_path or database_path())
    if path != ":memory:":
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Create all V1 tables and indexes idempotently."""
    with connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS source_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            published_at TEXT,
            first_seen_at TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            content_hash TEXT,
            text_excerpt TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(url, content_hash)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            event_at TEXT,
            disclosed_at TEXT,
            source_id INTEGER REFERENCES source_documents(id),
            evidence_confidence REAL NOT NULL DEFAULT 0.5,
            materiality INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'unverified',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_symbol_disclosed
            ON events(symbol, disclosed_at);
        CREATE INDEX IF NOT EXISTS idx_events_type_disclosed
            ON events(event_type, disclosed_at);
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            target_name TEXT NOT NULL,
            horizon_sessions INTEGER NOT NULL,
            probability REAL NOT NULL CHECK(probability >= 0 AND probability <= 1),
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            evidence_note TEXT NOT NULL DEFAULT '',
            as_of TEXT NOT NULL,
            created_at TEXT NOT NULL,
            outcome INTEGER CHECK(outcome IN (0,1)),
            outcome_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_predictions_as_of ON predictions(as_of);
        CREATE TABLE IF NOT EXISTS market_bars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            session_date TEXT NOT NULL,
            open REAL NOT NULL CHECK(open > 0),
            high REAL NOT NULL CHECK(high > 0),
            low REAL NOT NULL CHECK(low > 0),
            close REAL NOT NULL CHECK(close > 0),
            adjusted_close REAL CHECK(adjusted_close IS NULL OR adjusted_close > 0),
            volume REAL CHECK(volume IS NULL OR volume >= 0),
            source_name TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            UNIQUE(symbol, session_date, source_name),
            CHECK(high >= low),
            CHECK(high >= open AND high >= close),
            CHECK(low <= open AND low <= close)
        );
        CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_date
            ON market_bars(symbol, session_date);
        CREATE TABLE IF NOT EXISTS paper_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
            quantity REAL NOT NULL CHECK(quantity > 0),
            reference_price REAL NOT NULL CHECK(reference_price > 0),
            estimated_cost REAL NOT NULL DEFAULT 0,
            strategy_name TEXT NOT NULL,
            signal_time TEXT NOT NULL,
            expected_fill_time TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'PENDING',
            simulated_fill_price REAL,
            simulated_fill_time TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS event_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL UNIQUE REFERENCES source_documents(id),
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            disclosed_at TEXT,
            matched_alias TEXT NOT NULL,
            matched_terms TEXT NOT NULL,
            rule_strength INTEGER NOT NULL CHECK(rule_strength BETWEEN 1 AND 3),
            classifier_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_review'
                CHECK(status IN ('pending_review','accepted','rejected')),
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_event_candidates_status
            ON event_candidates(status, disclosed_at);
        CREATE TABLE IF NOT EXISTS headline_triage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL UNIQUE REFERENCES source_documents(id),
            classifier_version TEXT NOT NULL,
            matched INTEGER NOT NULL CHECK(matched IN (0,1)),
            processed_at TEXT NOT NULL
        );
        """)
