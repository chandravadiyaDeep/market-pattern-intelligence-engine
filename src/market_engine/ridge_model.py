"""Small dependency-free ridge regression with chronological evaluation."""
from math import isfinite, sqrt
from statistics import mean, stdev
from typing import Any


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Solve a square linear system by pivoted Gaussian elimination."""
    n = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Singular model matrix; increase ridge_alpha or check features")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][j] - factor * augmented[column][j] for j in range(n + 1)
            ]
    return [augmented[i][-1] for i in range(n)]


def fit_ridge(features: list[list[float]], targets: list[float], ridge_alpha: float = 1.0) -> dict[str, Any]:
    """Fit ridge regression after standardizing features using training data only.

    Objective: minimize sum((y_i - b - X_i w)^2) + alpha * sum(w_j^2).
    The intercept is unpenalized because targets and standardized features are centered.
    """
    if len(features) != len(targets) or len(features) < 2:
        raise ValueError("Need at least two aligned feature rows and targets")
    if ridge_alpha <= 0 or not isfinite(ridge_alpha):
        raise ValueError("ridge_alpha must be finite and positive")
    width = len(features[0])
    if width < 1 or any(len(row) != width for row in features):
        raise ValueError("Feature rows must have a consistent positive width")
    if any(not isfinite(value) for row in features for value in row) or any(not isfinite(y) for y in targets):
        raise ValueError("Model inputs must be finite numbers")
    means = [mean(row[j] for row in features) for j in range(width)]
    scales = []
    for j in range(width):
        values = [row[j] for row in features]
        scale = stdev(values) if len(values) > 1 else 0.0
        scales.append(scale if scale > 1e-12 else 1.0)
    target_mean = mean(targets)
    standardized = [[(row[j] - means[j]) / scales[j] for j in range(width)] for row in features]
    centered_y = [value - target_mean for value in targets]
    gram = [[sum(row[i] * row[j] for row in standardized) for j in range(width)] for i in range(width)]
    for i in range(width):
        gram[i][i] += ridge_alpha
    rhs = [sum(row[j] * y for row, y in zip(standardized, centered_y, strict=True)) for j in range(width)]
    weights = _solve_linear_system(gram, rhs)
    return {
        "feature_means": means, "feature_scales": scales,
        "target_mean": target_mean, "weights_standardized": weights,
        "ridge_alpha": ridge_alpha, "features": width, "training_rows": len(features),
        "method": "standardized_ridge_regression",
    }


def predict_ridge(model: dict[str, Any], features: list[float]) -> float:
    """Predict one continuous target using the stored training-only scaler."""
    if len(features) != model["features"]:
        raise ValueError("Feature count does not match the fitted model")
    if any(not isfinite(value) for value in features):
        raise ValueError("Prediction features must be finite")
    standardized = [
        (features[j] - model["feature_means"][j]) / model["feature_scales"][j]
        for j in range(len(features))
    ]
    return model["target_mean"] + sum(
        x * weight for x, weight in zip(standardized, model["weights_standardized"], strict=True)
    )


def walk_forward_ridge(
    rows: list[dict[str, Any]], train_fraction: float = 0.7, ridge_alpha: float = 1.0,
    minimum_training_rows: int = 30,
) -> dict[str, Any]:
    """Evaluate one-step-ahead predictions in date order with expanding training history."""
    if not 0.5 <= train_fraction < 1.0:
        raise ValueError("train_fraction must be in [0.5, 1)")
    if len(rows) < max(3, minimum_training_rows + 1):
        return {"status": "insufficient_data", "rows": len(rows), "predictions": []}
    dates = [str(row["date"]) for row in rows]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("Rows must be in unique ascending date order")
    features = [row["features"] for row in rows]
    targets = [float(row["target_forward_excess_log_return"]) for row in rows]
    if any(not row for row in features) or len({len(row) for row in features}) != 1:
        raise ValueError("Feature vectors must have a consistent non-zero width")
    split = max(minimum_training_rows, int(len(rows) * train_fraction))
    if split >= len(rows):
        split = len(rows) - 1
    predictions = []
    target_end_dates = [str(row.get("target_end_date", row["date"])) for row in rows]
    # Refit on an expanding window. Purge any earlier row whose forward label had not
    # fully resolved strictly before the test feature date, preventing horizon overlap.
    for index in range(split, len(rows)):
        eligible_train_indices = [
            train_index for train_index in range(index)
            if target_end_dates[train_index] < dates[index]
        ]
        if len(eligible_train_indices) < minimum_training_rows:
            continue
        train_features = [features[train_index] for train_index in eligible_train_indices]
        train_targets = [targets[train_index] for train_index in eligible_train_indices]
        model = fit_ridge(train_features, train_targets, ridge_alpha)
        estimate = predict_ridge(model, features[index])
        predictions.append({
            "date": dates[index],
            "actual": targets[index],
            "predicted": estimate,
            "baseline_zero_prediction": 0.0,
            "training_rows": len(eligible_train_indices),
            "last_training_target_end_date": max(target_end_dates[i] for i in eligible_train_indices),
        })
    actual = [item["actual"] for item in predictions]
    predicted = [item["predicted"] for item in predictions]
    baseline_errors = actual
    model_errors = [a - p for a, p in zip(actual, predicted, strict=True)]
    mae = mean(abs(error) for error in model_errors)
    rmse = sqrt(mean(error * error for error in model_errors))
    baseline_mae = mean(abs(error) for error in baseline_errors)
    baseline_rmse = sqrt(mean(error * error for error in baseline_errors))
    direction_accuracy = mean(
        (a >= 0) == (p >= 0) for a, p in zip(actual, predicted, strict=True)
    )
    return {
        "status": "ok",
        "method": "expanding_window_ridge_regression",
        "train_fraction": train_fraction,
        "minimum_training_rows": minimum_training_rows,
        "purging": "training target_end_date must be strictly before each test feature date",
        "ridge_alpha": ridge_alpha,
        "training_rows_at_first_prediction": split,
        "out_of_sample_predictions": len(predictions),
        "mae": mae, "rmse": rmse, "zero_baseline_mae": baseline_mae,
        "zero_baseline_rmse": baseline_rmse,
        "direction_accuracy": direction_accuracy,
        "beats_zero_baseline_mae": mae < baseline_mae,
        "predictions": predictions,
        "caveat": "Historical test performance is not a guarantee; overlapping horizons require purging for rigorous validation.",
    }
