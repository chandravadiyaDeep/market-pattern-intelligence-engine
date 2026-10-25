"""Authorized RSS/Atom ingestion into a provenance-preserving source registry."""
import hashlib
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from .db import connect, now_iso

DEFAULT_CONFIG = Path("config/research_sources.yaml")
MAX_FEED_BYTES = 5_000_000
USER_AGENT = "MarketPatternIntelligenceEngine/0.1 (research; contact: repository owner)"


def parse_timestamp(value: str | None) -> str | None:
    """Parse common RSS/Atom dates to UTC ISO-8601; preserve unknown dates as null."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value.strip())
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _local_name(tag: str) -> str:
    """Remove an XML namespace prefix from a tag."""
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, names: set[str]) -> str | None:
    """Return the first non-empty direct child value matching a local tag name."""
    for child in element:
        if _local_name(child.tag) in names:
            value = "".join(child.itertext()).strip()
            if value:
                return value
    return None


def _entry_link(element: ET.Element) -> str | None:
    """Extract an RSS link or Atom alternate link."""
    for child in element:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        rel = child.attrib.get("rel", "alternate").strip().lower()
        if href and rel in {"alternate", ""}:
            return href
        value = (child.text or "").strip()
        if value:
            return value
    return None


def parse_feed(xml_bytes: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom entries without fetching linked article pages."""
    if len(xml_bytes) > MAX_FEED_BYTES:
        raise ValueError("Feed exceeds the configured 5 MB safety limit")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid RSS/Atom XML: {exc}") from exc

    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    records: list[dict[str, Any]] = []
    for entry in entries:
        title = _child_text(entry, {"title"})
        link = _entry_link(entry)
        published = _child_text(entry, {"pubdate", "published", "updated", "date", "dc:date"})
        if not title or not link:
            continue
        summary = _child_text(entry, {"description", "summary", "subtitle", "content"}) or ""
        # Store only a short feed-provided excerpt; do not fetch or archive article bodies.
        excerpt = " ".join(summary.split())[:1000] or None
        published_at = parse_timestamp(published)
        canonical_url = link.strip()
        fingerprint = hashlib.sha256(
            f"{source.get('id', source.get('name', 'feed'))}|{canonical_url}|{published_at or ''}|{title.strip()}".encode("utf-8")
        ).hexdigest()
        records.append({
            "source_type": str(source.get("source_type", "rss_news")),
            "title": title.strip()[:500],
            "url": canonical_url,
            "published_at": published_at,
            "first_seen_at": now_iso(),
            "retrieved_at": now_iso(),
            "content_hash": fingerprint,
            "text_excerpt": excerpt,
        })
    return records


def fetch_feed(url: str, timeout_seconds: int = 15) -> bytes:
    """Fetch one configured feed URL with a timeout, user agent and response-size limit."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if not any(kind in content_type for kind in ("xml", "rss", "atom", "text/plain", "octet-stream")):
            raise ValueError(f"Unexpected feed content type: {content_type or 'unknown'}")
        body = response.read(MAX_FEED_BYTES + 1)
    if len(body) > MAX_FEED_BYTES:
        raise ValueError("Feed exceeds the configured 5 MB safety limit")
    return body


def load_feed_config(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load feed configuration and validate the minimal expected structure."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Feed config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    feeds = config.get("feeds")
    if not isinstance(feeds, list):
        raise ValueError("Feed configuration must contain a 'feeds' list")
    for feed in feeds:
        if not isinstance(feed, dict) or not feed.get("id") or not feed.get("url"):
            raise ValueError("Each feed needs non-empty 'id' and 'url' fields")
        if not str(feed["url"]).startswith("https://"):
            raise ValueError(f"Only HTTPS feed URLs are permitted: {feed['id']}")
    return config


def ingest_feeds(
    config_path: str | Path = DEFAULT_CONFIG,
    db_path: str | Path | None = None,
    dry_run: bool = False,
    fetcher: Callable[[str], bytes] = fetch_feed,
    delay_seconds: float = 0.5,
) -> dict[str, Any]:
    """Fetch configured feeds and save deduplicated source metadata.

    Each feed failure is reported and does not stop the other feeds. Dry-run fetches and
    parses feeds but makes no database writes. Only sources marked enabled are fetched.
    """
    config = load_feed_config(config_path)
    result: dict[str, Any] = {
        "started_at": now_iso(), "dry_run": dry_run, "feeds_attempted": 0,
        "feeds_succeeded": 0, "feeds_failed": 0, "records_seen": 0,
        "records_inserted": 0, "duplicates_skipped": 0, "errors": [],
    }
    enabled_feeds = [feed for feed in config["feeds"] if feed.get("enabled", False)]
    for index, feed in enumerate(enabled_feeds):
        result["feeds_attempted"] += 1
        try:
            xml_bytes = fetcher(str(feed["url"]))
            records = parse_feed(xml_bytes, feed)
            result["feeds_succeeded"] += 1
            result["records_seen"] += len(records)
            for record in records:
                if dry_run:
                    result["records_inserted"] += 1
                    continue
                with connect(db_path) as conn:
                    cursor = conn.execute(
                        """INSERT OR IGNORE INTO source_documents
                        (source_type,title,url,published_at,first_seen_at,retrieved_at,
                         content_hash,text_excerpt,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (record["source_type"], record["title"], record["url"],
                         record["published_at"], record["first_seen_at"], record["retrieved_at"],
                         record["content_hash"], record["text_excerpt"], now_iso()),
                    )
                    if cursor.rowcount == 1:
                        result["records_inserted"] += 1
                    else:
                        result["duplicates_skipped"] += 1
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
            result["feeds_failed"] += 1
            result["errors"].append({"feed_id": feed["id"], "error": str(exc)[:500]})
        if delay_seconds > 0 and index < len(enabled_feeds) - 1:
            time.sleep(delay_seconds)
    result["finished_at"] = now_iso()
    return result
