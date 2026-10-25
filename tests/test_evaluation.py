"""Unit tests for chronological evaluation."""
import pytest
from market_engine.evaluation import evaluate_binary_probabilities, chronological_split


def test_probability_metrics():
    result = evaluate_binary_probabilities([0.8, 0.2], [1, 0])
    assert result.observations == 2
    assert result.brier_score == pytest.approx(0.04)
    assert result.accuracy_at_half == 1.0


def test_chronological_split_does_not_shuffle():
    train, test = chronological_split(10, 0.7)
    assert list(train) == list(range(7))
    assert list(test) == list(range(7, 10))


def test_empty_metrics_are_explicit():
    assert evaluate_binary_probabilities([], []).observations == 0
