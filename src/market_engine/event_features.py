"""Build event-aware features with conservative point-in-time disclosure cutoffs."""
from datetime import datetime
from typing import Any

# Keep a fixed, broad taxonomy so feature positions remain stable across samples.
EVENT_TYPES = (
    "leadership", "regulatory", "earnings", "governance",
    "merger_acquisition", "capital_allocation", "operations", "other",
)
EVENT_LOOKBACK_SESSIONS = (5, 20, 60)


def _disclosure_date(value: Any) -> str | None:
    """Parse an ISO disclosure timestamp and return its calendar date."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except (TypeError, ValueError):
        return None


def add_event_features(
    prediction_dataset: dict[str, Any],
    events: list[dict[str, Any]],
    symbol: str,
    *,
    verified_statuses: tuple[str, ...] = ("official", "corroborated"),
) -> dict[str, Any]:
    """Append point-in-time event counts to the price dataset for one issuer.

    Only verified events for the requested issuer are considered. A disclosure on the
    feature date is excluded because date-only data cannot prove that it preceded the
    market close. Lookback windows count available trading-session rows, not calendar days.
    """
    if prediction_dataset.get("status") != "ok":
        return {**prediction_dataset, "event_features_added": False}

    normalized_symbol = symbol.strip().upper()
    valid_events: list[dict[str, str]] = []
    for event in events:
        disclosed_date = _disclosure_date(event.get("disclosed_at"))
        if (
            str(event.get("symbol", "")).strip().upper() != normalized_symbol
            or str(event.get("status", "")).strip().lower() not in verified_statuses
            or disclosed_date is None
        ):
            continue
        event_type = str(event.get("event_type", "other")).strip().lower()
        if event_type not in EVENT_TYPES:
            event_type = "other"
        valid_events.append({"date": disclosed_date, "event_type": event_type})

    # Labeled rows start after price-feature warm-up; include the latest feature date too.
    row_dates = [str(row["date"]) for row in prediction_dataset["rows"]]
    latest_date = str(prediction_dataset["latest_feature_row"]["date"])
    all_dates = sorted(set(row_dates + [latest_date]))
    index_by_date = {session_date: index for index, session_date in enumerate(all_dates)}

    event_feature_names = [
        f"event_{event_type}_count_{window}s"
        for event_type in EVENT_TYPES
        for window in EVENT_LOOKBACK_SESSIONS
    ]
    event_feature_names += [
        f"any_verified_event_count_{window}s" for window in EVENT_LOOKBACK_SESSIONS
    ]

    def counts_for_date(feature_date: str) -> list[float]:
        """Count events disclosed before this date and within each trailing session window."""
        date_index = index_by_date[feature_date]
        counts: list[float] = []
        for event_type in EVENT_TYPES:
            for window in EVENT_LOOKBACK_SESSIONS:
                threshold_date = all_dates[max(0, date_index - window)]
                counts.append(float(sum(
                    event["event_type"] == event_type
                    and threshold_date <= event["date"] < feature_date
                    for event in valid_events
                )))
        for window in EVENT_LOOKBACK_SESSIONS:
            threshold_date = all_dates[max(0, date_index - window)]
            counts.append(float(sum(
                threshold_date <= event["date"] < feature_date
                for event in valid_events
            )))
        return counts

    updated_rows = [
        {**row, "features": list(row["features"]) + counts_for_date(str(row["date"]))}
        for row in prediction_dataset["rows"]
    ]
    latest = prediction_dataset["latest_feature_row"]
    return {
        **prediction_dataset,
        "feature_names": list(prediction_dataset["feature_names"]) + event_feature_names,
        "rows": updated_rows,
        "latest_feature_row": {
            **latest, "features": list(latest["features"]) + counts_for_date(latest_date)
        },
        "event_features_added": True,
        "event_feature_policy": (
            "official/corroborated events only; disclosure date strictly before feature date; "
            "lookback measured in available price sessions"
        ),
        "verified_events_used": len(valid_events),
    }
