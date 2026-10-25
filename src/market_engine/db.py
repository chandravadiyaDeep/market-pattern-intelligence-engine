"""Small SQLite persistence layer suitable for local-first V1."""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone


def database_path() -> str:
    """Read configured DB path, defaulting to a local SQLite file."""
    return os.getenv("MARKET_ENGINE_DB", "./data/market_engine.sqlite")


@contextmanager
def connect():
    """Open a database connection and always close it."""
    path = database_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes idempotently."""
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            event_time TEXT,
            published_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            severity INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            content_hash TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_symbol_published
            ON events(symbol, published_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source_title_time
            ON events(source_url, title, published_at);
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            target TEXT NOT NULL,
            horizon_days INTEGER NOT NULL,
            probability REAL NOT NULL CHECK(probability >= 0 AND probability <= 1),
            model_version TEXT NOT NULL,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            outcome INTEGER CHECK(outcome IN (0, 1)),
            outcome_recorded_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_forecasts_created ON forecasts(created_at);
        CREATE TABLE IF NOT EXISTS paper_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
            quantity REAL NOT NULL CHECK(quantity > 0),
            submitted_at TEXT NOT NULL,
            reference_price REAL NOT NULL CHECK(reference_price > 0),
            estimated_cost REAL NOT NULL DEFAULT 0,
            strategy_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'simulated'
        );
        """)


def utc_now() -> str:
    """Return timezone-aware ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()
