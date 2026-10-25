"""Simple, interpretable event-pattern functions."""
from collections import Counter
from datetime import datetime, timedelta
from typing import Any


def summarize_event_counts(
    events: list[dict[str, Any]], lookback_days: int = 90, as_of: datetime | None = None
) -> dict[str, int]:
    """Count disclosed event types in a time window; exclude future and undated events."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive")
    cutoff_time = as_of or datetime.now().astimezone()
    cutoff = cutoff_time - timedelta(days=lookback_days)
    counts: Counter[str] = Counter()
    for event in events:
        disclosed_at = event.get("disclosed_at")
        if not disclosed_at:
            continue
        if isinstance(disclosed_at, str):
            disclosed_at = datetime.fromisoformat(disclosed_at)
        if disclosed_at.tzinfo is None and cutoff.tzinfo is not None:
            disclosed_at = disclosed_at.replace(tzinfo=cutoff.tzinfo)
        if cutoff <= disclosed_at <= cutoff_time:
            counts[str(event.get("event_type", "other"))] += 1
    return dict(counts)


def describe_pattern(counts: dict[str, int]) -> list[dict[str, Any]]:
    """Rank event counts transparently; frequency is not causation or a trading signal."""
    return [
        {"event_type": name, "count": count, "interpretation": "frequency_only"}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
