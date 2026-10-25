"""Unit tests for probability evaluation and chronological split."""
import pytest
from market_engine.evaluation import evaluate_binary_probabilities, chronological_split


def test_perfect_forecasts_have_zero_brier_score():
    """Correct 0/1 forecasts should attain a zero Brier score."""
    result = evaluate_binary_probabilities([0.0, 1.0], [0, 1])
    assert result.brier_score == 0.0
    assert result.accuracy_at_half == 1.0


def test_chronological_split_does_not_shuffle():
    """Train indices must precede test indices."""
    train, test = chronological_split(10, 0.7)
    assert max(train) < min(test)


def test_metric_length_mismatch_raises():
    """Forecast and outcome lists must align."""
    with pytest.raises(ValueError):
        evaluate_binary_probabilities([0.5], [0, 1])
