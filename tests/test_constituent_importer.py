"""Tests for the historical constituent membership importer."""
import csv

from market_engine.constituent_importer import import_constituents_csv
from market_engine.db import connect, init_db


def _write_csv(path, rows):
    """Write a small deterministic membership fixture for importer tests."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["symbol", "company_name", "start_date", "end_date", "source_name"]
        )
        writer.writeheader()
        writer.writerows(rows)


def test_import_constituent_history_and_skip_duplicates(tmp_path):
    """Membership intervals are normalized, persisted, and deduplicated by source."""
    db_file = tmp_path / "constituents.sqlite3"
    init_db(db_file)
    source = tmp_path / "membership.csv"
    _write_csv(source, [
        {"symbol": " tcs ", "company_name": "Tata Consultancy Services",
         "start_date": "2020-04-01", "end_date": "2022-03-31", "source_name": "official-test"},
        {"symbol": "TCS", "company_name": "Tata Consultancy Services",
         "start_date": "2020-04-01", "end_date": "2022-03-31", "source_name": "official-test"},
        {"symbol": "INFY", "company_name": "Infosys",
         "start_date": "2022-04-01", "end_date": "", "source_name": "official-test"},
    ])

    first = import_constituents_csv(source, db_path=db_file, dry_run=False)
    second = import_constituents_csv(source, db_path=db_file, dry_run=False)

    assert first["valid_rows"] == 3
    assert first["inserted_rows"] == 2
    assert first["invalid_rows"] == 0
    assert second["inserted_rows"] == 0
    assert second["duplicates_skipped"] == 3
    with connect(db_file) as conn:
        rows = conn.execute("SELECT * FROM constituent_membership ORDER BY symbol").fetchall()
    assert len(rows) == 2
    assert rows[1]["symbol"] == "TCS"


def test_constituent_import_rejects_invalid_date_interval(tmp_path):
    """Invalid membership intervals are reported rather than silently accepted."""
    db_file = tmp_path / "invalid-membership.sqlite3"
    init_db(db_file)
    source = tmp_path / "invalid.csv"
    _write_csv(source, [
        {"symbol": "ABC", "company_name": "Example Corp",
         "start_date": "2025-01-02", "end_date": "2025-01-01", "source_name": "test"},
    ])

    result = import_constituents_csv(source, db_path=db_file)
    assert result["invalid_rows"] == 1
    assert result["inserted_rows"] == 0
