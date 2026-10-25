"""CSV import helpers for manually curated or licensed event datasets."""
import csv
from pathlib import Path
from typing import Any
from pydantic import ValidationError
from .db import connect, now_iso
from .models import EventIn

REQUIRED_COLUMNS = {"symbol", "event_type", "title", "summary"}
OPTIONAL_COLUMNS = {
    "event_at", "disclosed_at", "evidence_confidence", "materiality", "status"
}


def import_events_csv(
    csv_path: str | Path, db_path: str | Path | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Validate and import event rows, skipping exact duplicate event keys.

    CSV timestamps should include an explicit UTC offset where possible. This importer
    does not fetch external data and does not establish that a row is factually verified.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}")

        imported = 0
        duplicates = 0
        errors: list[dict[str, Any]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                event = EventIn(
                    symbol=row.get("symbol", ""),
                    event_type=row.get("event_type", ""),
                    title=row.get("title", ""),
                    summary=row.get("summary", ""),
                    event_at=row.get("event_at") or None,
                    disclosed_at=row.get("disclosed_at") or None,
                    evidence_confidence=float(row.get("evidence_confidence") or 0.5),
                    materiality=int(row.get("materiality") or 1),
                    status=row.get("status") or "unverified",
                )
            except (ValidationError, ValueError, TypeError) as exc:
                errors.append({"row": row_number, "error": str(exc)})
                continue

            if dry_run:
                imported += 1
                continue

            with connect(db_path) as conn:
                existing = conn.execute(
                    """SELECT id FROM events
                    WHERE symbol=? AND event_type=? AND title=? AND COALESCE(disclosed_at,'')=?""",
                    (event.symbol, event.event_type, event.title,
                     event.disclosed_at.isoformat() if event.disclosed_at else ""),
                ).fetchone()
                if existing:
                    duplicates += 1
                    continue
                conn.execute(
                    """INSERT INTO events
                    (symbol,event_type,title,summary,event_at,disclosed_at,source_id,
                     evidence_confidence,materiality,status,created_at)
                    VALUES (?,?,?,?,?, ?,NULL,?,?,?,?)""",
                    (event.symbol, event.event_type, event.title, event.summary,
                     event.event_at.isoformat() if event.event_at else None,
                     event.disclosed_at.isoformat() if event.disclosed_at else None,
                     event.evidence_confidence, event.materiality, event.status, now_iso()),
                )
                imported += 1

    return {
        "file": str(path),
        "dry_run": dry_run,
        "valid_rows": imported,
        "duplicates_skipped": duplicates,
        "invalid_rows": len(errors),
        "errors": errors[:50],
    }
