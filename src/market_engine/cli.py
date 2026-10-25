"""Command-line tools for local setup and a synthetic demo."""
import argparse
from .db import init_db
from .forecasting import estimate_event_probability
from .evaluation import evaluate_binary_probabilities


def run_demo() -> None:
    """Print synthetic examples; no real market data is loaded."""
    outcomes = [0, 0, 1, 0, 0, 1, 0, 0, 0, 1]
    estimate = estimate_event_probability(outcomes, prior_probability=0.1, prior_strength=5)
    metrics = evaluate_binary_probabilities([estimate.probability] * len(outcomes), outcomes)
    print("SYNTHETIC DEMO ONLY — not Nifty 50 data and not a trading signal")
    print(f"Observations: {estimate.observations}; positives: {estimate.positives}")
    print(f"Smoothed baseline event probability: {estimate.probability:.3f}")
    print(f"In-sample illustrative Brier score: {metrics.brier_score:.3f}")
    print("Do not treat this demonstration as model validation.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Market Pattern Intelligence Engine")
    parser.add_argument("command", choices=["init-db", "demo"])
    args = parser.parse_args()
    if args.command == "init-db":
        init_db()
        print("Database initialized.")
    else:
        run_demo()


if __name__ == "__main__":
    main()
