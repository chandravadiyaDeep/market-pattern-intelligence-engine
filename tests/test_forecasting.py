"""Unit tests for baseline probability estimation."""
import pytest
from market_engine.forecasting import estimate_event_probability


def test_beta_smoothed_probability():
    result = estimate_event_probability([1, 1, 1])
    assert result.observations == 3
    assert result.positives == 3
    assert result.probability == pytest.approx(0.8)


def test_empty_sample_returns_prior():
    assert estimate_event_probability([]).probability == pytest.approx(0.5)


def test_invalid_labels_rejected():
    with pytest.raises(ValueError):
        estimate_event_probability([0, 2])
