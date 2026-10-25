# Market Pattern Intelligence Engine

A personal research platform for Nifty 50 corporate-event intelligence, market-impact research, historical pattern exploration, walk-forward evaluation, and paper trading.

> **Research only.** V1 does not submit live broker orders and does not promise predictive performance. The current probability functions are transparent baselines, not validated trading models.

## Quick start (Windows PowerShell)

Requires Python 3.11+.

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

## V1 modules

- **Source records:** preserve source URL, publication time, first-seen time, retrieval time and content hash.
- **Event timeline:** store structured company events with source linkage and verification status.
- **Pattern explorer:** describe event frequencies within a time window; descriptive patterns are not automatically predictive.
- **Probability baseline:** smoothed historical event frequencies with sample size metadata.
- **Evaluation:** Brier score, log loss and chronological splits.
- **Paper orders:** simulated order ledger and explicit simulated fills only. No broker integration exists.

## API routes

- `GET /health`
- `POST/GET /sources`
- `POST/GET /events`
- `POST/GET /predictions`
- `POST /predictions/{id}/outcome`
- `GET /patterns/event-frequency`
- `GET /evaluation/summary`
- `POST/GET /paper/orders`
- `POST /paper/orders/{id}/fill`

## Research safeguards

1. Keep event time, publication time, first-seen time, retrieval time and prediction time separate.
2. Use only information available at the forecast timestamp.
3. Evaluate chronologically; never randomly mix future and past observations.
4. Use historical Nifty 50 constituents for historical universe tests to avoid survivorship bias.
5. Record forecasts before outcomes; outcomes are immutable after recording.
6. Model next executable prices, corporate actions, brokerage, taxes, exchange charges and slippage.
7. Do not treat LLM-generated summaries as probabilities or verified facts without evidence.
8. Never commit secrets or restricted datasets.

## Data sources

Begin with a small, manually curated or otherwise permitted dataset. Confirm provider terms before automated collection or redistribution. See [data source policy](docs/DATA_SOURCES.md).

## Current limitations

There is not yet a production data-ingestion connector, historical Nifty 50 constituent loader, trained prediction model, walk-forward trading simulator, or market-data feed. Those should be added only with a tested data contract and evaluation protocol. This repo is the auditable foundation, not a completed forecasting system.

Read [architecture](docs/ARCHITECTURE.md) and [evaluation protocol](docs/EVALUATION.md) before adding predictive features.
