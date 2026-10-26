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
- General event-study engine that measures post-disclosure stock returns against a benchmark across multiple horizons, for any event category with verified timestamps and sufficient price history.
- Experimental mathematical forecasting baseline using leakage-aware forward excess-return targets, standardized ridge regression, and expanding-window out-of-sample evaluation; includes fixed-taxonomy event-count features from official/corroborated disclosures using conservative point-in-time cutoffs.
- Point-in-time cross-sectional backtest panel builder that joins dated constituent membership to same-source stock/benchmark prices, creates trailing price features, and labels future excess returns.
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

# Import dated historical index membership (verify source and dates first)
market-engine import-constituents --file .\\data\\nifty_constituents_history.csv --source official-or-authorized-source

# Start API
uvicorn market_engine.api:app --reload
```

CSV required columns: `symbol,event_type,title,summary`. Optional columns: `event_at,disclosed_at,evidence_confidence,materiality,status`. Timestamp strings should include an explicit UTC offset. Imported events are not automatically fact-checked.

## Deployment

This repository is a FastAPI backend, not a finished frontend website. For a personal hosted API, see [DEPLOYMENT.md](DEPLOYMENT.md). The included Dockerfile and Railway configuration use a persistent volume mounted at `/data` for SQLite. Set `MPIE_MODE=production`, `MPIE_DATABASE_PATH=/data/mpie.sqlite3`, and a secret `MPIE_API_KEY` of at least 32 characters in the host's environment settings before exposing a public domain. Keep the service to one instance while using SQLite on a mounted volume.

The deployment configuration does not provide historical market data, automatic feed scheduling, multi-user authentication, or a validated trading strategy. Do not commit local databases, API keys, or licensed data files.

## Research source links

Maintain source links in [resources/RESEARCH_SOURCES.md](resources/RESEARCH_SOURCES.md). The machine-readable registry is [config/research_sources.yaml](config/research_sources.yaml). Only entries under feeds with enabled set to true are fetched by the RSS pipeline. The initial feeds are general news feeds, not a complete or verified Nifty 50 event feed.

## API routes

- `GET /health`
- `POST /sources` and `GET /sources`
- `GET /event-candidates` (defaults to pending review)
- `POST /event-candidates/{id}/review?decision=accept|reject` (accepted records remain unverified)
- `GET /pipeline/feeds` (configuration only; does not trigger a network fetch)
- `GET /research-sources` (source-link catalog)
- `GET /research/event-study?benchmark_symbol=NIFTY50&horizons=1,3,5,10,20` (official/corroborated event study)
- `GET /research/predictive-baseline/TCS?benchmark_symbol=NIFTY50&horizon_sessions=5` (experimental price + verified-event baseline; requires sufficient aligned stock and benchmark history; excludes disclosures from the same feature date)
- `GET /universe/constituents?as_of=2024-01-01` (historical membership intervals from imported data)
- `GET /research/backtest-panel?start_date=2020-01-01&end_date=2025-12-31&source_name=your-provider` (point-in-time panel from imported bars and membership)\n- `GET /market-bars`
- `GET /market-bars/{symbol}/features`
- `POST /events` and `GET /events`
- `POST /predictions` and `GET /predictions`
- `POST /predictions/{id}/outcome`
- `GET /evaluation/summary`
- `GET /patterns/event-counts`
- `POST /paper-orders` and `GET /paper-orders`
- `POST /paper-orders/{id}/fill` (simulated only)

See [the mathematical framework](docs/MATHEMATICAL_FRAMEWORK.md) for return definitions, event-study formulas, ridge objective, assumptions, and validation gates. See [historical universe data guidance](docs/HISTORICAL_UNIVERSE.md) for membership CSV format, import commands, and point-in-time cautions. See [backtest dataset documentation](docs/BACKTEST_DATASET.md) for panel requirements, API parameters, and limitations.

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

The repository now includes a configurable RSS/Atom metadata-ingestion pipeline, a rule-based event-candidate review queue, and a validated CSV importer for daily OHLCV history. The event-candidate rules and starter company alias list are deliberately incomplete and need ongoing validation. It does **not yet** include a dedicated NSE/BSE filings connector, an automatic or authoritative Nifty 50 constituent loader, a licensed live or historical price feed, automatic event extraction and verification, a validated corporate-event prediction model, or a complete return-aware walk-forward strategy simulator. The included sample prices are synthetic only. The initial enabled feeds are general news feeds, not a complete or guaranteed Nifty 50 feed. Historical constituent membership can now be imported from a curated CSV and queried by date; the engine does not download or certify official membership history for you. The market-feature utilities are not yet fully connected to a persisted historical price store.
