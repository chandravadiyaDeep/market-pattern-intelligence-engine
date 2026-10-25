"""SQLite persistence for local-first research. No broker connection is provided."""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone


def database_path() -> str:
    """Resolve database path from supported environment variables."""
    return os.getenv("MPIE_DATABASE_PATH", os.getenv("MARKET_ENGINE_DB", "./data/mpie.sqlite3"))


def now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: str | None = None):
    """Open a connection, create its parent directory, and handle transactions."""
    path = db_path or database_path()
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


def init_db(db_path: str | None = None) -> None:
    """Create V1 tables and indexes idempotently."""
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
        CREATE INDEX IF NOT EXISTS idx_events_symbol_disclosed ON events(symbol, disclosed_at);
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
            outcome INTEGER CHECK(outcome IN (0,1)),
            outcome_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_predictions_as_of ON predictions(as_of);
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
        """)
