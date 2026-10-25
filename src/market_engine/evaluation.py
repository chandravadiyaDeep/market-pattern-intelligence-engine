"""Minimal evaluation metrics and chronological splitting utilities."""
from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class BinaryMetrics:
    """Metrics for probability forecasts and binary outcomes."""
    observations: int
    brier_score: float | None
    log_loss: float | None
    accuracy_at_half: float | None


def evaluate_binary_probabilities(probabilities: list[float], outcomes: list[int]) -> BinaryMetrics:
    """Evaluate probability forecasts; lower Brier score and log loss are better."""
    if len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have equal length")
    if any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError("probabilities must be between 0 and 1")
    if any(y not in (0, 1) for y in outcomes):
        raise ValueError("outcomes must be binary")
    if not outcomes:
        return BinaryMetrics(0, None, None, None)
    eps = 1e-15
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes, strict=True)) / len(outcomes)
    logloss = -sum(
        y * log(max(eps, p)) + (1 - y) * log(max(eps, 1 - p))
        for p, y in zip(probabilities, outcomes, strict=True)
    ) / len(outcomes)
    accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(probabilities, outcomes, strict=True)) / len(outcomes)
    return BinaryMetrics(len(outcomes), brier, logloss, accuracy)


def chronological_split(n_rows: int, train_fraction: float = 0.7) -> tuple[range, range]:
    """Split ordered rows without shuffling; rows must already be time-sorted."""
    if n_rows < 2:
        raise ValueError("At least two observations are required")
    if not 0.1 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be between 0.1 and 0.9")
    split_at = min(max(int(n_rows * train_fraction), 1), n_rows - 1)
    return range(0, split_at), range(split_at, n_rows)
