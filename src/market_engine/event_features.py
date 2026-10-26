"""Build event-aware features with conservative point-in-time disclosure cutoffs."""
from datetime import datetime
from typing import Any

# Keep a fixed, broad taxonomy so model feature positions do not change by sample.
EVENT_TYPES = (
    "leadership",
    "regulatory",
    "earnings",
    "governance",
    "merger_acquisition",
    "capital_allocation",
    "operations",
    "other",
)
EVENT_LOOKBACK_SESSIONS = (5, 20, 60)


def _disclosure_date(value: Any) -> str | None:
    """Parse a disclosure timestamp and return its calendar date, or None if absent."""
    if not value:
        return None
    try:
        # Accept ISO timestamps with UTC offsets; date-only ISO strings are also valid.
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
    """Add per-symbol event indicators to price rows without future-disclosure leakage.

    Only explicitly verified events for the requested symbol are used. Events disclosed
    on the feature date are deliberately excluded: date-only timestamps cannot establish
    whether the disclosure preceded that session's close. Counts use prior trading rows
    (not calendar days), and the taxonomy includes all supported event categories.
    """
    if prediction_dataset.get("status") != "ok":
        return {**prediction_dataset, "event_features_added": False}

    normalized_symbol = symbol.strip().upper()
    feature_names = list(prediction_dataset["feature_names"])
    event_feature_names = [
        f"event_{event_type}_count_{window}s"
        for event_type in EVENT_TYPES
        for window in EVENT_LOOKBACK_SESSIONS
    ]
    event_feature_names += [f"any_verified_event_count_{window}s" for window in EVENT_LOOKBACK_SESSIONS]

    valid_events: list[dict[str, str]] = []
    for event in events:
        event_symbol = str(event.get("symbol", "")).strip().upper()
        status = str(event.get("status", "")).strip().lower()
        disclosed_date = _disclosure_date(event.get("disclosed_at"))
        event_type = str(event.get("event_type", "other")).strip().lower()
        if event_symbol != normalized_symbol or status not in verified_statuses or not disclosed_date:
            continue
        if event_type not in EVENT_TYPES:
            event_type = "other"
        valid_events.append({"date": disclosed_date, "event_type": event_type})

    # Preserve chronological ordering and map each event to a disclosure date.
    valid_events.sort(key=lambda item: item["date"])
    def features_for_date(feature_date: str, date_index: int, all_dates: list[str]) -> list[float]:
        """Count verified disclosures strictly before the feature date."""
        previous_dates = set(all_dates[max(0, date_index - max(EVENT_LOOKBACK_SESSIONS)):date_index])
        prior = [
            event for event in valid_events
            if event["date"] < feature_date
            and any(session_date >= event["date"] for session_date in previous_dates)
        ]
        counts: list[float] = []
        for event_type in EVENT_TYPES:
            for window in EVENT_LOOKBACK_SESSIONS:
                eligible_dates = set(all_dates[max(0, date_index - window):date_index])
                counts.append(float(sum(
                    event["event_type"] == event_type
                    and any(session_date >= event["date"] for session_date in eligible_dates)
                    for event in valid_events
                    if event["date"] < feature_date
                )))
        for window in EVENT_LOOKBACK_SESSIONS:
            eligible_dates = set(all_dates[max(0, date_index - window):date_index])
            counts.append(float(sum(
                any(session_date >= event["date"] for session_date in eligible_dates)
                for event in valid_events
                if event["date"] < feature_date
            )))
        return counts

    # The labelled rows do not necessarily include the latest date, so use their dates
    # and the latest feature date as the available price-session timeline.
    row_dates = [str(row["date"]) for row in prediction_dataset["rows"]]
    latest_date = str(prediction_dataset["latest_feature_row"]["date"])
    all_dates = sorted(set(row_dates + [latest_date]))
    index_by_date = {value: index for index, value in enumerate(all_dates)}

    updated_rows = []
    for row in prediction_dataset["rows"]:
        event_values = features_for_date(row_dates[row_dates.index(str(row["date"]))],
                                         index_by_date[str(row["date"])], all_dates)
        updated_rows.append({**row, "features": list(row["features"]) + event_values})
    latest = prediction_dataset["latest_feature_row"]
    latest_values = features_for_date(latest_date, index_by_date[latest_date], all_dates)

    return {
        **prediction_dataset,
        "feature_names": feature_names + event_feature_names,
        "rows": updated_rows,
        "latest_feature_row": {**latest, "features": list(latest["features"]) + latest_values},
        "event_features_added": True,
        "event_feature_policy": (
            "official/corroborated events only; disclosure date must be strictly before feature date; "
            "lookback measured in available price sessions"
        ),
        "verified_events_used": len(valid_events),
    }
