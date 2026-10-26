# Mathematical framework

The engine is designed to measure uncertainty and test hypotheses, not to generate confident-looking signals from arbitrary rules. Every model must declare its target, horizon, information cutoff, baseline, assumptions, sample size, and evaluation protocol.

## 1. Return definitions

For a price series P_t, the simple return is r_t = P_t / P_(t-1) - 1 and the log return is g_t = ln(P_t / P_(t-1)). Choose one definition for each experiment and use it consistently across the stock and benchmark. Prices must be adjusted appropriately for corporate actions when the research question requires it.

## 2. Market-model event study

Fit only on an estimation window before the event window:

R_i,t = alpha + beta R_m,t + epsilon_t

OLS estimates:

beta_hat = sum((R_m,t - mean(R_m))(R_i,t - mean(R_i))) / sum((R_m,t - mean(R_m))^2)

alpha_hat = mean(R_i) - beta_hat mean(R_m)

Abnormal return:

AR_t = R_i,t - (alpha_hat + beta_hat R_m,t)

Cumulative abnormal return over L event sessions:

CAR = sum(AR_t), t in event window

Residual variance estimate:

s^2 = sum(epsilon_hat_t^2) / (n - 2)

For the classical OLS market model, the implementation estimates CAR variance with the estimation-parameter uncertainty term and event-window benchmark leverage. It reports CAR, standard error, t-statistic and two-sided Student-t p-value. The interval shown is explicitly a normal approximation, not an exact small-sample interval.

Assumptions and caveats: model parameters are stable across windows; returns are aligned and correctly timestamped; the estimation sample is sufficiently informative; classical residual assumptions are reasonable. Overlapping events, heteroskedasticity, event-induced variance and multiple comparisons can distort inference. Statistical significance does not prove causation.

## 3. General forecasting principles

- Start with a predeclared target such as next 1/5/20-session excess return, a return threshold, or realized volatility—not an ambiguous target like "what happens next".
- Compare a constant historical base-rate forecast, a benchmark/momentum baseline, and a more complex model on identical chronological splits.
- Keep every feature timestamp at or before the forecast cutoff. Labels must finish after the cutoff and must not overlap training outcomes in validation.
- Fit scalers, imputers, feature selection and hyperparameters on training data only.
- Use rolling or expanding walk-forward validation and retain a final untouched test period.
- For probabilities, report Brier score, log loss, calibration and base-rate comparisons. For return forecasts, report out-of-sample error and benchmark-relative results. For trading simulations, include next-feasible execution, costs, slippage, turnover and drawdown.
- Use confidence intervals and sample counts. Apply a multiple-testing correction when screening many symbols, horizons or event definitions.
- Never treat a heuristic match score, a p-value, or an in-sample backtest as a calibrated probability of future profit.

## 4. General event taxonomy

The event-study mathematics is independent of event type. Earnings, regulation, leadership, capital allocation, operations, macro releases, sector shocks, price/volume anomalies, and other events can all be studied when their timestamps and evidence are available. Taxonomies organize the data; they must not hard-code a presumed market direction.

## 5. Next implementation gates

1. Obtain legally usable, timestamped stock and benchmark prices.
2. Verify historical constituent membership and corporate-action adjustments.
3. Build event windows from disclosure availability, not merely the date an event happened.
4. Run event studies with predeclared horizons and report missing data.
5. Test robustness across time periods, symbols, sectors, and market regimes.
6. Only then compare candidate predictive models against simple baselines.
