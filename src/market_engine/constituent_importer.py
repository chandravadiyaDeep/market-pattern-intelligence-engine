"""CSV importer for dated index-constituent membership history."""
import csv
from datetime import date
from pathlib import Path
from typing import Any

from .db import connect, now_iso

REQUIRED_COLUMNS = {"symbol", "company_name", "start_date"}
OPTIONAL_COLUMNS = {"end_date", "source_name"}


def import_constituents_csv(
    csv_path: str | Path,
    db_path: str | Path | None = None,
    source_name: str = "manual_constituents_csv",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate and store symbol membership intervals without inferring historical members.

    The supplied dates and source are preserved as given. This importer does not download,
    authenticate, or certify official index constituent records.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not source_name.strip():
        raise ValueError("source_name must not be empty")

    valid_rows = inserted_rows = duplicates = 0
    errors: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}")

        for row_number, row in enumerate(reader, start=2):
            try:
                # Normalize symbols for consistent point-in-time joins.
                symbol = (row.get("symbol") or "").strip().upper()
                company_name = (row.get("company_name") or "").strip()
                if not symbol:
                    raise ValueError(f"row {row_number}: symbol is required")
                if not company_name:
                    raise ValueError(f"row {row_number}: company_name is required")

                try:
                    start_date = date.fromisoformat((row.get("start_date") or "").strip()).isoformat()
                except ValueError as exc:
                    raise ValueError(f"row {row_number}: start_date must use YYYY-MM-DD") from exc

                end_text = (row.get("end_date") or "").strip()
                try:
                    end_date = date.fromisoformat(end_text).isoformat() if end_text else None
                except ValueError as exc:
                    raise ValueError(f"row {row_number}: end_date must use YYYY-MM-DD or be blank") from exc
                if end_date and end_date < start_date:
                    raise ValueError(f"row {row_number}: end_date cannot precede start_date")

                row_source = (row.get("source_name") or "").strip() or source_name.strip()
                valid_rows += 1
                with connect(db_path) as conn:
                    existing = conn.execute(
                        """SELECT id FROM constituent_membership
                        WHERE symbol=? AND start_date=? AND source_name=?""",
                        (symbol, start_date, row_source),
                    ).fetchone()
                    if existing:
                        duplicates += 1
                        continue
                    if not dry_run:
                        conn.execute(
                            """INSERT INTO constituent_membership
                            (symbol,company_name,start_date,end_date,source_name,retrieved_at)
                            VALUES (?,?,?,?,?,?)""",
                            (symbol, company_name, start_date, end_date, row_source, now_iso()),
                        )
                        inserted_rows += 1
            except (ValueError, TypeError) as exc:
                errors.append({"row": row_number, "error": str(exc)})

    return {
        "file": str(path),
        "dry_run": dry_run,
        "valid_rows": valid_rows,
        "inserted_rows": inserted_rows,
        "duplicates_skipped": duplicates,
        "invalid_rows": len(errors),
        "errors": errors[:50],
        "source_name_default": source_name,
    }
