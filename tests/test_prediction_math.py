"""Tests for feature timing, ridge fitting, and chronological model evaluation."""
import math

import pytest

from market_engine.prediction_dataset import build_prediction_dataset
from market_engine.ridge_model import fit_ridge, predict_ridge, walk_forward_ridge


def test_dataset_target_is_future_excess_return_and_features_stop_at_date():
    """Changing only future prices must not change the feature vector for the current row."""
    dates = [f"2026-01-{day:02d}" for day in range(1, 31)]
    stock = {date: 100.0 + index for index, date in enumerate(dates)}
    market = {date: 100.0 + index * 0.4 for index, date in enumerate(dates)}
    result = build_prediction_dataset(stock, market, horizon_sessions=3)
    assert result["status"] == "ok"
    row = next(item for item in result["rows"] if item["date"] == dates[22])
    original_features = row["features"]
    changed = dict(stock)
    for date in dates[23:]:
        changed[date] *= 1.5
    changed_result = build_prediction_dataset(changed, market, horizon_sessions=3)
    changed_row = next(item for item in changed_result["rows"] if item["date"] == dates[22])
    assert changed_row["features"] == pytest.approx(original_features)
    assert changed_row["target_forward_excess_log_return"] != pytest.approx(
        row["target_forward_excess_log_return"]
    )


def test_ridge_recovers_simple_linear_relationship():
    """A regularized linear model should approximate a stable synthetic relationship."""
    x = [[float(i), float(i % 3)] for i in range(1, 40)]
    y = [0.02 * row[0] - 0.01 * row[1] + 0.5 for row in x]
    model = fit_ridge(x, y, ridge_alpha=1e-6)
    assert predict_ridge(model, [20.0, 2.0]) == pytest.approx(0.88, abs=0.02)


def test_walk_forward_uses_only_prior_rows_and_compares_zero_baseline():
    """The first evaluated date must be later than every training date."""
    rows = [
        {"date": f"2026-01-{i:02d}", "features": [float(i), float(i % 4)],
         "target_forward_excess_log_return": 0.001 * i}
        for i in range(1, 51)
    ]
    result = walk_forward_ridge(rows, train_fraction=0.7, minimum_training_rows=20)
    assert result["status"] == "ok"
    assert result["out_of_sample_predictions"] > 0
    assert result["predictions"][0]["date"] > rows[result["training_rows_at_first_prediction"] - 1]["date"]
    assert result["mae"] < 0.1


def test_ridge_rejects_bad_data_and_unsorted_walk_forward_rows():
    """Reject malformed numeric matrices instead of silently producing model output."""
    with pytest.raises(ValueError):
        fit_ridge([[1.0], [2.0]], [1.0], 1.0)
    with pytest.raises(ValueError):
        walk_forward_ridge([
            {"date": "2026-01-02", "features": [1.0], "target_forward_excess_log_return": 0.1},
            {"date": "2026-01-01", "features": [2.0], "target_forward_excess_log_return": 0.2},
            {"date": "2026-01-03", "features": [3.0], "target_forward_excess_log_return": 0.3},
        ], minimum_training_rows=1)
