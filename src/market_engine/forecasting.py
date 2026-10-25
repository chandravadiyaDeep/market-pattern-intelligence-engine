"""Transparent baseline probability estimators; not market-validated models."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityEstimate:
    """Historical-rate estimate with sample size and smoothing metadata."""
    probability: float
    positives: int
    observations: int
    prior_probability: float
    prior_strength: float
    method: str = "beta_binomial_smoothed_rate"
    warning: str = "Baseline only; validate chronologically before research use."


def estimate_event_probability(
    outcomes: list[int], prior_probability: float = 0.5, prior_strength: float = 2.0
) -> ProbabilityEstimate:
    """Estimate smoothed event frequency from binary historical labels.

    Supply only labels known within the training window. This function does not select
    analogues, model features, or guarantee calibration.
    """
    if not 0 <= prior_probability <= 1:
        raise ValueError("prior_probability must be in [0, 1]")
    if prior_strength <= 0:
        raise ValueError("prior_strength must be positive")
    if any(value not in (0, 1) for value in outcomes):
        raise ValueError("outcomes must contain only 0 or 1")
    positives = sum(outcomes)
    n = len(outcomes)
    probability = (positives + prior_probability * prior_strength) / (n + prior_strength)
    return ProbabilityEstimate(probability, positives, n, prior_probability, prior_strength)
