"""Rule-based headline triage; outputs candidates, never verified events."""
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .db import connect, now_iso

DEFAULT_ALIASES = Path("config/company_aliases.yaml")
CLASSIFIER_VERSION = "rules-0.1.0"

# Keywords are transparent triage rules, not a trained model or a probability estimate.
EVENT_RULES: dict[str, tuple[str, ...]] = {
    "earnings": (
        "financial results", "quarterly results", "annual results", "net profit",
        "revenue", "earnings", "profit rises", "profit falls", "results declared",
    ),
    "regulatory": (
        "sebi", "regulator", "regulatory", "penalty", "show cause", "investigation",
        "antitrust", "compliance order", "fine imposed",
    ),
    "leadership": (
        "resigns", "resignation", "appointed as", "appoints", "chief executive",
        "managing director", "chief financial officer", "chairman", "ceo", "cfo",
    ),
    "merger_acquisition": (
        "acquisition", "acquires", "acquire", "merger", "merges with", "stake sale",
        "buyout", "open offer",
    ),
    "capital_allocation": (
        "dividend", "share buyback", "buyback", "rights issue", "bonus issue",
        "stock split", "fundraising", "qualified institutional placement", "qip",
    ),
    "governance": (
        "auditor resigns", "auditor resignation", "fraud", "whistleblower",
        "related party", "governance issue", "pledges shares", "pledge of shares",
    ),
    "operations": (
        "order win", "wins contract", "contract worth", "capacity expansion",
        "plant shutdown", "plant commissioning", "production halt", "production",
        "launches", "expansion plan", "operations disrupted",
    ),
}


def _compile_aliases(path: str | Path = DEFAULT_ALIASES) -> list[tuple[str, str]]:
    """Load aliases and compile longest aliases first to reduce short-name collisions."""
    alias_path = Path(path)
    if not alias_path.is_file():
        raise FileNotFoundError(f"Company alias config not found: {alias_path}")
    with alias_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    companies = config.get("companies")
    if not isinstance(companies, list):
        raise ValueError("Company alias config must contain a companies list")
    pairs: list[tuple[str, str]] = []
    seen_symbols: set[str] = set()
    for company in companies:
        if not isinstance(company, dict) or not company.get("symbol"):
            raise ValueError("Each company alias entry needs a symbol")
        symbol = str(company["symbol"]).strip().upper()
        if symbol in seen_symbols:
            raise ValueError(f"Duplicate company symbol in alias config: {symbol}")
        seen_symbols.add(symbol)
        aliases = company.get("aliases", [])
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"Company {symbol} must have at least one alias")
        for alias in aliases:
            value = str(alias).strip()
            if value:
                pairs.append((value, symbol))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def _find_symbol(title: str, excerpt: str, aliases: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    """Return the first alias match using token boundaries to avoid partial-word matches."""
    text = f"{title} {excerpt}"
    for alias, symbol in aliases:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return symbol, alias
    return None, None


def classify_headline(title: str, excerpt: str, aliases: list[tuple[str, str]]) -> dict[str, Any] | None:
    """Classify one headline only when both an issuer alias and event rule match."""
    symbol, matched_alias = _find_symbol(title, excerpt, aliases)
    if not symbol:
        return None
    text = f"{title} {excerpt}".casefold()
    matches: list[tuple[str, str]] = []
    for event_type, keywords in EVENT_RULES.items():
        for keyword in keywords:
            if keyword.casefold() in text:
                matches.append((event_type, keyword))
    if not matches:
        return None
    # Prefer the event type with the most matched phrases; ties follow the stable rule order.
    counts: dict[str, int] = {}
    for event_type, _ in matches:
        counts[event_type] = counts.get(event_type, 0) + 1
    chosen_type = max(counts, key=counts.get)
    matched_terms = sorted({keyword for event_type, keyword in matches if event_type == chosen_type})
    return {
        "symbol": symbol,
        "event_type": chosen_type,
        "matched_alias": matched_alias,
        "matched_terms": matched_terms,
        "rule_strength": min(3, len(matched_terms)),
    }


def classify_source_documents(
    db_path: str | Path | None = None,
    aliases_path: str | Path = DEFAULT_ALIASES,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a review queue from previously ingested headlines; do not auto-verify events."""
    aliases = _compile_aliases(aliases_path)
    result: dict[str, Any] = {
        "classifier_version": CLASSIFIER_VERSION,
        "dry_run": dry_run,
        "documents_scanned": 0,
        "candidates_found": 0,
        "candidates_inserted": 0,
        "unmatched": 0,
        "items": [],
    }
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT s.* FROM source_documents s
            LEFT JOIN headline_triage t ON t.source_id = s.id
            WHERE t.id IS NULL ORDER BY s.published_at DESC, s.id DESC"""
        ).fetchall()
        result["documents_scanned"] = len(rows)
        for row in rows:
            candidate = classify_headline(row["title"], row["text_excerpt"] or "", aliases)
            if candidate is None:
                result["unmatched"] += 1
                if not dry_run:
                    conn.execute(
                        """INSERT OR IGNORE INTO headline_triage
                        (source_id,classifier_version,matched,processed_at)
                        VALUES (?,?,?,?)""",
                        (row["id"], CLASSIFIER_VERSION, 0, now_iso()),
                    )
                continue
            result["candidates_found"] += 1
            item = {
                "source_id": row["id"],
                "symbol": candidate["symbol"],
                "event_type": candidate["event_type"],
                "title": row["title"],
                "disclosed_at": row["published_at"],
                "matched_alias": candidate["matched_alias"],
                "matched_terms": candidate["matched_terms"],
                "rule_strength": candidate["rule_strength"],
            }
            result["items"].append(item)
            if dry_run:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO event_candidates
                (source_id,symbol,event_type,title,summary,disclosed_at,matched_alias,
                 matched_terms,rule_strength,classifier_version,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (row["id"], candidate["symbol"], candidate["event_type"], row["title"],
                 row["text_excerpt"] or "", row["published_at"], candidate["matched_alias"],
                 json.dumps(candidate["matched_terms"]), candidate["rule_strength"],
                 CLASSIFIER_VERSION, "pending_review", now_iso()),
            )
            result["candidates_inserted"] += 1
            conn.execute(
                """INSERT OR IGNORE INTO headline_triage
                (source_id,classifier_version,matched,processed_at)
                VALUES (?,?,?,?)""",
                (row["id"], CLASSIFIER_VERSION, 1, now_iso()),
            )
    return result
