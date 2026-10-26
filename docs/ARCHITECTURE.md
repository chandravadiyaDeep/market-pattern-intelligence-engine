# Architecture

## Core flow

1. Ingest permitted public/paid records and preserve source metadata and publication times.
2. Normalize entities and symbols; deduplicate without discarding source references.
3. Apply transparent headline rules and configurable issuer aliases to propose event candidates.
4. Review candidate records manually; accepted candidates enter the event ledger as unverified until the source disclosure is checked.
5. Extract verified events into a controlled taxonomy; distinguish claims, verified disclosures, and retractions.
6. Build point-in-time features using only records available by each prediction timestamp.
7. Forecast corporate-event likelihood and market impact in separate models.
8. Register predictions with target, horizon, probability, evidence snapshot and model version.
9. Evaluate forecasts on later chronological windows.
10. Simulate trades only in a separate paper ledger.

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


## Headline triage boundary

The initial candidate classifier is keyword-based, not an ML model. It can miss relevant headlines, match ambiguous phrases, and only recognize issuers present in `config/company_aliases.yaml`. Its rule-strength field counts matching phrases; it is not a probability of truth or market impact. Candidate acceptance is a workflow decision, not verification of the underlying claim. Expand aliases using dated official constituent records and add regression tests for false positives before using candidates in research.
