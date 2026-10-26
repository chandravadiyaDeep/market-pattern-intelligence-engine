# Market Pattern Intelligence Engine

Personal research software for studying how corporate events and evolving company signals may relate to future outcomes across the Nifty 50 universe.

> **Research and paper simulation only.** There is no live broker integration. Baseline probability functions are not validated trading models and do not guarantee future performance.

## Quick start — Windows PowerShell

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
market-engine init-db
pytest -q
uvicorn market_engine.api:app --reload
```

Open the API explorer at http://127.0.0.1:8000/docs.

## Current capabilities

- Source registry that retains publication, first-seen and retrieval timestamps.
- Structured event timeline with evidence confidence, materiality and verification status.
- CSV import for manually curated or otherwise permitted event datasets.
- RSS/Atom ingestion pipeline for official NSE announcements, corporate actions, board meetings and financial results, plus market-specific news feeds; includes dry-run mode, timestamp normalization, source metadata storage and duplicate detection.
- Transparent keyword-based headline triage that creates a human-review queue of possible corporate events; issuer aliases are configurable in `config/company_aliases.yaml`, and candidates are never automatically treated as verified events.
- Descriptive event-frequency exploration over a lookback window.
- Transparent smoothed historical base-rate estimates.
- Point-in-time market features: daily returns, trailing momentum, annualized realized volatility and benchmark-relative returns.
- Brier score, log loss and chronological train/test splitting utilities.
- Timestamped forecasts with outcomes recorded separately and immutable once resolved.
- Paper-order ledger with explicitly simulated fills; no broker or live order placement.

## Useful commands

```powershell
# Initialize local SQLite database
market-engine init-db

# Validate a CSV without writing it
market-engine import-events --file .\data\sample_events.csv --dry-run

# Import a CSV after reviewing the dry-run report
market-engine import-events --file .\data\sample_events.csv

# Fetch configured RSS feeds without writing to the database
market-engine fetch-feeds --dry-run

# Fetch configured RSS feeds and store source metadata
market-engine fetch-feeds

# Preview rule-based event candidates from stored headlines without writing
market-engine classify-news --dry-run

# Create pending-review candidates from stored headlines
market-engine classify-news

# Validate the synthetic example (not real market data)
market-engine import-prices --file .\\examples\\sample_prices.csv --source synthetic-demo --dry-run

# Import an authorized provider's daily OHLCV CSV
market-engine import-prices --file .\\data\\licensed_prices.csv --source your-provider

# Start API
uvicorn market_engine.api:app --reload
```

CSV required columns: `symbol,event_type,title,summary`. Optional columns: `event_at,disclosed_at,evidence_confidence,materiality,status`. Timestamp strings should include an explicit UTC offset. Imported events are not automatically fact-checked.

## Research source links

Maintain source links in [resources/RESEARCH_SOURCES.md](resources/RESEARCH_SOURCES.md). The machine-readable registry is [config/research_sources.yaml](config/research_sources.yaml). Only entries under feeds with enabled set to true are fetched by the RSS pipeline. The initial feeds are general news feeds, not a complete or verified Nifty 50 event feed.

## API routes

- `GET /health`
- `POST /sources` and `GET /sources`
- `GET /pipeline/feeds` (configuration only; does not trigger a network fetch)
- `GET /research-sources` (source-link catalog)
- `GET /market-bars`
- `GET /market-bars/{symbol}/features`
- `POST /events` and `GET /events`
- `POST /predictions` and `GET /predictions`
- `POST /predictions/{id}/outcome`
- `GET /evaluation/summary`
- `GET /patterns/event-counts`
- `POST /paper-orders` and `GET /paper-orders`
- `POST /paper-orders/{id}/fill` (simulated only)

## Research safeguards

1. Keep event time, publication time, first-seen time, retrieval time and forecast time separate.
2. Use only information available at the historical forecast timestamp.
3. Evaluate chronologically; never randomly mix future and past observations.
4. Use historical Nifty 50 constituent membership for historical universe tests to avoid survivorship bias.
5. Save forecasts before outcomes; do not rewrite outcomes after they have been recorded.
6. Model next eligible execution prices, corporate actions, brokerage, taxes, exchange charges, slippage and liquidity.
7. Treat LLM-generated extraction as a claim that needs evidence, not as a verified fact or calibrated probability.
8. Never commit API keys, credentials, or licensed data dumps.

## Data source policy

Begin with small manually curated datasets or sources whose terms permit the intended use. Verify current provider terms before automated collection, bulk downloading or redistribution. See [data source notes](docs/DATA_SOURCES.md).

## Important limitations

The repository now includes a configurable RSS/Atom metadata-ingestion pipeline, a rule-based event-candidate review queue, and a validated CSV importer for daily OHLCV history. The event-candidate rules and starter company alias list are deliberately incomplete and need ongoing validation. It does **not yet** include a dedicated NSE/BSE filings connector, a historical Nifty 50 constituent loader, a licensed live or historical price feed, automatic event extraction and verification, a validated corporate-event prediction model, or a complete return-aware walk-forward strategy simulator. The included sample prices are synthetic only. The initial enabled feeds are general news feeds, not a complete or guaranteed Nifty 50 feed. The market-feature utilities are not yet connected to a persisted historical price store.
