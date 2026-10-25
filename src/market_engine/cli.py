"""Command-line tools for local setup, CSV import, and a synthetic demo."""
import argparse
import json
from .db import init_db
from .forecasting import estimate_event_probability
from .evaluation import evaluate_binary_probabilities
from .importers import import_events_csv


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
    parser.add_argument("command", choices=["init-db", "demo", "import-events"])
    parser.add_argument("--file", help="CSV path required for import-events")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV without writing rows")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
        print("Database initialized.")
    elif args.command == "demo":
        run_demo()
    else:
        if not args.file:
            parser.error("--file is required when command is import-events")
        init_db()
        result = import_events_csv(args.file, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
