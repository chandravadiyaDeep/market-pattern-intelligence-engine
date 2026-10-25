"""Validated CSV ingestion for licensed/manual daily OHLCV data."""
import csv
import math
from datetime import date
from pathlib import Path
from typing import Any

from .db import connect, now_iso

REQUIRED_COLUMNS = {"symbol", "date", "open", "high", "low", "close"}
OPTIONAL_COLUMNS = {"adjusted_close", "volume", "source_name"}


def _number(raw: str | None, field: str, row_number: int, optional: bool = False) -> float | None:
    """Parse a finite numeric field and return None only for a blank optional value."""
    if raw is None or not raw.strip():
        if optional:
            return None
        raise ValueError(f"row {row_number}: missing {field}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return value


def import_prices_csv(
    csv_path: str | Path,
    db_path: str | Path | None = None,
    source_name: str = "manual_csv",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate and persist daily OHLCV rows, skipping duplicates by symbol/date/source.

    The input must come from a provider whose terms allow the intended research use.
    This importer does not download prices or validate the provider's licensing.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not source_name.strip():
        raise ValueError("source_name must not be empty")

    valid_rows = 0
    inserted_rows = 0
    duplicates = 0
    errors: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"Missing required CSV columns: {', '.join(sorted(missing))}")

        for row_number, row in enumerate(reader, start=2):
            try:
                symbol = (row.get("symbol") or "").strip().upper()
                if not symbol:
                    raise ValueError(f"row {row_number}: symbol is required")
                date_text = (row.get("date") or "").strip()
                try:
                    session_date = date.fromisoformat(date_text).isoformat()
                except ValueError as exc:
                    raise ValueError(f"row {row_number}: date must use YYYY-MM-DD") from exc

                opening = _number(row.get("open"), "open", row_number)
                high = _number(row.get("high"), "high", row_number)
                low = _number(row.get("low"), "low", row_number)
                close = _number(row.get("close"), "close", row_number)
                adjusted = _number(row.get("adjusted_close"), "adjusted_close", row_number, True)
                volume = _number(row.get("volume"), "volume", row_number, True)
                assert opening is not None and high is not None and low is not None and close is not None

                if min(opening, high, low, close) <= 0:
                    raise ValueError(f"row {row_number}: OHLC prices must be positive")
                if high < max(opening, low, close) or low > min(opening, high, close):
                    raise ValueError(f"row {row_number}: invalid OHLC range (high/low inconsistent)")
                if adjusted is not None and adjusted <= 0:
                    raise ValueError(f"row {row_number}: adjusted_close must be positive")
                if volume is not None and volume < 0:
                    raise ValueError(f"row {row_number}: volume cannot be negative")

                row_source = (row.get("source_name") or "").strip() or source_name.strip()
                valid_rows += 1
                with connect(db_path) as conn:
                    existing = conn.execute(
                        "SELECT id FROM market_bars WHERE symbol=? AND session_date=? AND source_name=?",
                        (symbol, session_date, row_source),
                    ).fetchone()
                    if existing:
                        duplicates += 1
                        continue
                    if not dry_run:
                        conn.execute(
                            """INSERT INTO market_bars
                            (symbol,session_date,open,high,low,close,adjusted_close,volume,source_name,retrieved_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (symbol, session_date, opening, high, low, close, adjusted, volume,
                             row_source, now_iso()),
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
