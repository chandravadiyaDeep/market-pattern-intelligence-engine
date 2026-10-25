# Evaluation and backtesting protocol

## Define targets before training

Every event target must define taxonomy, target population, window, positive/negative label rules, treatment of scheduled events, and handling of unknown outcomes. Market targets must define benchmark, return horizon, thresholds, execution timing and corporate-action treatment.

## Validation

- Split by time, not random rows.
- Use rolling or expanding walk-forward tests.
- Purge training observations whose outcome windows overlap validation/test windows.
- Keep a final untouched period; repeated tuning makes a test set no longer untouched.
- Use point-in-time constituent membership, prices, event data, and financial releases.
- Compare models with simple base-rate, momentum and volatility baselines.

## Event forecast metrics

- Precision and recall for thresholded alerts.
- PR-AUC for rare event classes.
- Brier score and log loss for probabilities.
- Calibration plots by probability bucket.
- Results by event type, sector and market regime.

## Market forecast metrics

- Brier score/log loss for direction or threshold-crossing probabilities.
- Benchmark-relative returns and drawdown for strategies.
- Turnover, exposure, tail losses and transaction costs.
- Performance stability by period and sector.

## Paper execution

- Signals become eligible only after actual availability timestamps.
- Define next-session/open or other feasible entry rules before testing.
- Model brokerage, taxes, exchange charges, slippage and liquidity where relevant.
- Keep forecasts and trading rules separately versioned.
- Do not infer an edge from a tiny sample or one market regime.

## Research gate before any live-trading discussion

Require repeatable out-of-sample performance, reasonable calibration, robustness to costs, explicit drawdown limits, and review of current regulatory/broker obligations. V1 contains no live order placement.
