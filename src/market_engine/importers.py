"""CSV import helpers for manually curated or licensed event datasets."""
import csv
import hashlib
from pathlib import Path
from typing import Any
from pydantic import ValidationError
from .db import connect, now_iso
from .models import EventIn

REQUIRED_COLUMNS = {"symbol", "event_type", "title", "summary"}
OPTIONAL_COLUMNS = {
    "event_at", "disclosed_at", "evidence_confidence", "materiality", "status",
    "source_url", "source_type", "source_title", "source_published_at",
}


def import_events_csv(
    csv_path: str | Path, db_path: str | Path | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Validate and import event rows, skipping duplicate event keys.

    If source_url is supplied, create or reuse a source-document record and link it to
    the event. This importer does not fetch data or prove that a row is factually correct.
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
        missing_sources = 0
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
                if not (row.get("source_url") or "").strip():
                    missing_sources += 1
                continue

            with connect(db_path) as conn:
                event_time = event.disclosed_at.isoformat() if event.disclosed_at else ""
                existing = conn.execute(
                    """SELECT id FROM events
                    WHERE symbol=? AND event_type=? AND title=? AND COALESCE(disclosed_at,'')=?""",
                    (event.symbol, event.event_type, event.title, event_time),
                ).fetchone()
                if existing:
                    duplicates += 1
                    continue

                source_id = None
                source_url = (row.get("source_url") or "").strip() or None
                if source_url:
                    source_type = (row.get("source_type") or "manual").strip() or "manual"
                    source_title = (row.get("source_title") or event.title).strip() or event.title
                    published_at = row.get("source_published_at") or (
                        event.disclosed_at.isoformat() if event.disclosed_at else None
                    )
                    content_hash = hashlib.sha256(
                        f"{source_url}|{published_at or ''}".encode("utf-8")
                    ).hexdigest()
                    source = conn.execute(
                        "SELECT id FROM source_documents WHERE content_hash=?", (content_hash,)
                    ).fetchone()
                    if source:
                        source_id = int(source["id"])
                    else:
                        cursor = conn.execute(
                            """INSERT INTO source_documents
                            (source_type,title,url,published_at,first_seen_at,retrieved_at,
                             content_hash,text_excerpt,created_at)
                            VALUES (?,?,?,?,?,?,?,NULL,?)""",
                            (source_type, source_title, source_url, published_at, now_iso(),
                             now_iso(), content_hash, now_iso()),
                        )
                        source_id = int(cursor.lastrowid)
                else:
                    missing_sources += 1

                conn.execute(
                    """INSERT INTO events
                    (symbol,event_type,title,summary,event_at,disclosed_at,source_id,
                     evidence_confidence,materiality,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (event.symbol, event.event_type, event.title, event.summary,
                     event.event_at.isoformat() if event.event_at else None,
                     event.disclosed_at.isoformat() if event.disclosed_at else None,
                     source_id, event.evidence_confidence, event.materiality, event.status, now_iso()),
                )
                imported += 1

    return {
        "file": str(path),
        "dry_run": dry_run,
        "valid_rows": imported,
        "duplicates_skipped": duplicates,
        "invalid_rows": len(errors),
        "rows_missing_source_url": missing_sources,
        "errors": errors[:50],
    }
