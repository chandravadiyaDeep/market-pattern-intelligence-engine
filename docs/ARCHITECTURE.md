# Architecture

## V1 data flow

1. Collect authorized official filings, news references and daily market data.
2. Preserve source publication time, first-seen time, retrieval time and event time separately.
3. Normalize companies and classify events; link events to original source records.
4. Generate features only from information available at each forecast timestamp.
5. Run corporate-event and market-impact predictions as separate targets.
6. Save forecasts before outcomes become known.
7. Evaluate chronological holdout forecasts and paper simulations with realistic execution assumptions.

## Modules

- `models.py`: validated source, event, forecast and paper-order domain objects.
- `db.py`: local SQLite schema and transaction management.
- `data_sources.py`: connector contract and candidate source catalog.
- `patterns.py`: descriptive event-frequency analysis.
- `forecasting.py`: transparent historical base-rate estimate.
- `evaluation.py`: probability metrics and chronological split.
- `paper.py`: simulated order ledger; no broker integration.
- `api.py`: research API.

## Guardrails

An LLM may extract claims and summarize evidence; it is not itself a calibrated probability model. Event probability, market impact and trade profitability are distinct questions. Do not use future revisions, current index membership, or later price information in historical forecasts.
