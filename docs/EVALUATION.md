# Evaluation protocol

## Define targets first

Specify the event definition, exclusions, horizon and resolution rules before training. For market impact, define the return horizon and benchmark-relative threshold in advance.

## Chronological evaluation

Use rolling or walk-forward splits. Train on past observations and test on later periods. Purge overlapping label windows where appropriate. Only use features and source versions available at the prediction time.

## Metrics

- Event forecasts: precision, recall, PR-AUC, Brier score, log loss and calibration.
- Market forecasts: probability metrics, benchmark-relative returns, turnover, drawdown and risk-adjusted performance.
- Paper strategies: realistic fill timing, brokerage, taxes, exchange charges, slippage, liquidity, corporate actions and position limits.

## Baselines

Compare every complex model with historical base rates and simple market/sector and price/volatility baselines. A model should be retained only if it improves out-of-sample performance robustly.

## Forecast registry

Store target, horizon, timestamp, probability, model version and evidence snapshot before the outcome is known. Record outcomes once; never silently overwrite historical forecasts.
