# Point-in-time backtest dataset panel

The `build_backtest_panel` function builds a research panel from imported daily bars and dated constituent intervals. It does not train a model or simulate orders.

## Requirements

- Import daily OHLCV history from a provider whose terms permit your use.
- Include the benchmark symbol (default `NIFTY50`) in the same named `source_name`.
- Import dated membership intervals from a verified historical source.
- Prefer consistently adjusted closing prices. The engine uses `adjusted_close` when present and falls back to `close` when it is blank.

## API

Start the service:

```powershell
uvicorn market_engine.api:app --reload
```

Example request:

`GET /research/backtest-panel?start_date=2020-01-01&end_date=2025-12-31&source_name=your-provider&benchmark_symbol=NIFTY50&horizon_sessions=5&volatility_window=20&momentum_windows=5,20&limit=5000`

The response contains one row per symbol and feature date where:

- the membership interval includes that date;
- stock and benchmark have a shared trading session;
- the feature lookback is available; and
- the complete forward target horizon is within the requested end date.

Each row has a numeric feature vector, forward stock-minus-benchmark log-return target, target end date, and membership/price source labels. Rows are ordered by date and symbol. The endpoint caps returned rows using `limit` and reports whether output was truncated.

## Python use

```python
# Build a reproducible panel from the configured SQLite database.
from market_engine.backtest_dataset import build_backtest_panel

panel = build_backtest_panel(
    start_date="2020-01-01",
    end_date="2025-12-31",
    source_name="your-provider",
    benchmark_symbol="NIFTY50",
    horizon_sessions=5,
)
print(panel["status"], panel.get("row_count", 0))
```

## Important limitations

- The panel does not yet join corporate-event features. Event joins must use disclosure availability timestamps, not event dates alone.
- It does not calculate brokerage, taxes, slippage, liquidity constraints, or realistic entry/exit fills.
- It cannot validate whether the source actually provides adjusted prices or complete historical membership.
- The same source label must be used for all bars; this prevents accidental cross-provider mixing but does not guarantee the provider's data quality.
- This is research infrastructure, not evidence of a profitable strategy. Evaluate using purged walk-forward testing and a final untouched holdout before drawing conclusions.
