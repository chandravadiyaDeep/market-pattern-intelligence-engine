# Architecture

## Core flow

1. Ingest permitted public/paid records and preserve source metadata and publication times.
2. Normalize entities and symbols; deduplicate without discarding source references.
3. Extract events into a controlled taxonomy; distinguish claims, verified disclosures, and retractions.
4. Build point-in-time features using only records available by each prediction timestamp.
5. Forecast corporate-event likelihood and market impact in separate models.
6. Register predictions with target, horizon, probability, evidence snapshot and model version.
7. Evaluate forecasts on later chronological windows.
8. Simulate trades only in a separate paper ledger.

## Timestamp contract

- `event_at`: when the underlying event occurred, if known.
- `published_at` / `disclosed_at`: when an external source made it available.
- `first_seen_at`: when this collector first observed it.
- `as_of`: the cutoff timestamp used to form a forecast.
- `created_at`: when this application stored a record.

Do not backfill an event into features before the disclosure could have been known. A later article about an older event must not be treated as a signal available in the past.

## V1 choices

- One Python application, not microservices.
- SQLite for simple local setup; migrate to PostgreSQL when justified.
- Explicit source provenance and model versions.
- LLMs may extract facts into a schema, but probabilities come from measurable estimators.
- No broker credentials or live order placement.
