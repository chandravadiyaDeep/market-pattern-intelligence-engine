"""Tests for CSV event import and duplicate protection."""
import csv
from market_engine.db import connect, init_db
from market_engine.importers import import_events_csv


def write_csv(path, rows):
    """Write a small CSV fixture with a stable set of columns."""
    fields = ["symbol", "event_type", "title", "summary", "disclosed_at", "status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_importer_validates_then_imports_and_skips_duplicates(tmp_path):
    """A valid row imports once; a repeated row is skipped on later imports."""
    db_path = tmp_path / "test.sqlite3"
    init_db(db_path)
    csv_path = tmp_path / "events.csv"
    write_csv(csv_path, [{
        "symbol": "reliance",
        "event_type": "earnings",
        "title": "Synthetic results event",
        "summary": "Synthetic test fixture only.",
        "disclosed_at": "2026-10-01T12:00:00+00:00",
        "status": "unverified",
    }])

    dry = import_events_csv(csv_path, db_path=db_path, dry_run=True)
    assert dry["valid_rows"] == 1
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0

    first = import_events_csv(csv_path, db_path=db_path)
    second = import_events_csv(csv_path, db_path=db_path)
    assert first["valid_rows"] == 1
    assert second["duplicates_skipped"] == 1
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


def test_importer_reports_missing_columns(tmp_path):
    """Required schema errors should fail early with a useful message."""
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("symbol,title\nRELIANCE,Missing fields\n", encoding="utf-8")
    try:
        import_events_csv(csv_path, dry_run=True)
    except ValueError as exc:
        assert "Missing required CSV columns" in str(exc)
    else:
        raise AssertionError("Expected missing-column validation error")
