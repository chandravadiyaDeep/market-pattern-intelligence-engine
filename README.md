# Market Pattern Intelligence Engine

A personal research platform for Nifty 50 corporate-event intelligence, market-impact analysis, historical pattern exploration, walk-forward backtesting, and paper trading.

> **Research software only.** V1 does not place live orders and does not provide guaranteed forecasts or investment advice. Initial models are baselines and must be evaluated out of sample before any strategy is trusted.

## V1 goals

- Maintain source-linked, timestamp-aware corporate event records.
- Explore event frequency, sequences, and similar historical cases.
- Estimate explicitly defined event probabilities using transparent baselines.
- Evaluate forecast calibration and market outcomes without look-ahead leakage.
- Simulate paper orders with explicit costs and risk limits.

## Quick start

Requires Python 3.11 or newer.

```powershell
# Windows PowerShell, from the repository root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
pytest
market-engine init-db
market-engine demo
uvicorn market_engine.api:app --reload
```

API docs are available at `http://127.0.0.1:8000/docs`.

## Current implementation

- FastAPI service and SQLite-first local development database.
- Event and prediction data models.
- Baseline event probability and market-impact helpers.
- Brier score, log loss, and calibration summaries.
- Pattern-window and event-sequence helpers.
- Simulated paper orders only; no broker integration.
- Source registry and data collection guidance.

## Data policy

Start with small, manually curated or otherwise permitted datasets. Verify the provider's terms before automated collection, bulk download, or redistribution. Never commit API keys, licensed datasets, or private credentials. See [data source notes](docs/DATA_SOURCES.md).

## Research safeguards

1. Store event time, publication time, first-seen time, and prediction time separately.
2. Forecast only from information available at prediction time.
3. Use chronological/walk-forward splits; do not randomly mix future and past.
4. Use historical index constituents for historical universe tests to reduce survivorship bias.
5. Save forecasts before outcomes and never overwrite the original prediction.
6. Include transaction costs, realistic execution timing, and corporate actions in strategy tests.

## Development plan

See [architecture](docs/ARCHITECTURE.md), [data sources](docs/DATA_SOURCES.md), and [evaluation protocol](docs/EVALUATION.md). V1 begins with reliable historical records and baseline evaluation; advanced models and live trading are intentionally postponed.
