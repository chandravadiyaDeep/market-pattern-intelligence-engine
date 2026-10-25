"""Tests for validated daily price CSV ingestion."""
from pathlib import Path

from market_engine.db import connect, init_db
from market_engine.market_data_importer import import_prices_csv


def write_csv(path: Path, rows: str) -> Path:
    """Write a minimal test CSV with the required daily OHLC columns."""
    path.write_text(
        "symbol,date,open,high,low,close,adjusted_close,volume\n" + rows,
        encoding="utf-8",
    )
    return path


def test_price_import_and_duplicate_protection(tmp_path: Path):
    """Repeated import of the same symbol/date/source does not duplicate rows."""
    database = tmp_path / "prices.sqlite3"
    init_db(database)
    csv_path = write_csv(
        tmp_path / "prices.csv",
        "reliance,2026-10-20,100,110,95,108,107,1000\n",
    )
    first = import_prices_csv(csv_path, db_path=database, source_name="licensed-provider")
    second = import_prices_csv(csv_path, db_path=database, source_name="licensed-provider")
    assert first["inserted_rows"] == 1
    assert second["inserted_rows"] == 0
    assert second["duplicates_skipped"] == 1
    with connect(database) as conn:
        row = conn.execute("SELECT symbol,session_date,close FROM market_bars").fetchone()
        assert tuple(row) == ("RELIANCE", "2026-10-20", 108.0)


def test_invalid_ohlc_range_is_rejected(tmp_path: Path):
    """A high below the closing price must be rejected."""
    database = tmp_path / "bad.sqlite3"
    init_db(database)
    csv_path = write_csv(tmp_path / "bad.csv", "TCS,2026-10-20,100,101,95,105,,100\n")
    result = import_prices_csv(csv_path, db_path=database)
    assert result["invalid_rows"] == 1
    assert result["inserted_rows"] == 0


def test_price_import_dry_run_does_not_write(tmp_path: Path):
    """Dry-run validates data but leaves the database unchanged."""
    database = tmp_path / "dry.sqlite3"
    init_db(database)
    csv_path = write_csv(tmp_path / "dry.csv", "INFY,2026-10-20,100,110,90,105,,200\n")
    result = import_prices_csv(csv_path, db_path=database, dry_run=True)
    assert result["valid_rows"] == 1
    assert result["inserted_rows"] == 0
    with connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_bars").fetchone()[0] == 0
