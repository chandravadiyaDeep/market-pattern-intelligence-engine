"""Unit tests for transparent baseline probability estimation."""
import pytest
from market_engine.forecasting import estimate_event_probability


def test_smoothed_probability_stays_between_zero_and_one():
    """Estimate remains valid with no positive labels."""
    result = estimate_event_probability([0, 0, 0], prior_probability=0.2, prior_strength=4)
    assert 0 <= result.probability <= 1
    assert result.observations == 3
    assert result.positives == 0


def test_all_positive_outcomes_increase_probability():
    """More positive outcomes should increase estimate against the same prior."""
    low = estimate_event_probability([0, 0, 0, 0], prior_probability=0.1)
    high = estimate_event_probability([1, 1, 1, 1], prior_probability=0.1)
    assert high.probability > low.probability


def test_reject_non_binary_outcomes():
    """Invalid labels must not be silently coerced."""
    with pytest.raises(ValueError):
        estimate_event_probability([0, 2, 1])
