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


## General mathematical event study

The `GET /research/event-study` endpoint analyzes every event explicitly marked `verified`, without restricting the analysis to leadership, earnings, or another predefined event category. It groups estimates by the stored event type only after computing event-level outcomes.

For event window H, it computes cumulative abnormal log return against the chosen benchmark:

`CAR_H = Σ[log(P_stock,t / P_stock,t-1) − log(P_benchmark,t / P_benchmark,t-1)]`

The reported relative return is `exp(CAR_H) − 1`. The event window begins at the first issuer trading session strictly after the disclosure calendar date, which is conservative when the exact release time relative to market close is uncertain.

The endpoint reports event-level stock and benchmark returns, mean/median relative returns, sample standard deviation, standard error and an approximate 95% confidence interval. The confidence interval uses a normal approximation and is not reliable for very small samples. The diagnostic t-statistic is not a substitute for robust inference with overlapping events, repeated issuer observations or event clustering.

Run it after importing issuer and benchmark prices and verifying events:

    GET /research/event-study?benchmark_symbol=NIFTY50&horizons=1,3,5,10,20

The default analysis excludes unverified events. It returns explicit skipped-data counts and an insufficient-data status rather than inventing observations. Event studies describe historical association; they do not establish causality or forecast future returns. Next research stages should include cross-sectional controls, clustered inference, walk-forward validation and transaction-cost-aware paper simulation.
