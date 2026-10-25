"""Command-line helpers for local database setup."""
import argparse
from market_engine.db import init_db
from market_engine.forecasting import estimate_event_probability


def main() -> None:
    """Run supported CLI commands."""
    parser = argparse.ArgumentParser(description="Market Pattern Intelligence Engine")
    parser.add_argument("command", choices=["init-db", "demo"])
    args = parser.parse_args()
    if args.command == "init-db":
        init_db()
        print("Database initialized.")
    elif args.command == "demo":
        estimate = estimate_event_probability([0, 1, 0, 0, 1, 0])
        print("DEMO ONLY — synthetic labels, not a market forecast.")
        print(f"Smoothed historical event frequency: {estimate.probability:.3f}")
        print(f"Sample size: {estimate.observations}")


if __name__ == "__main__":
    main()
