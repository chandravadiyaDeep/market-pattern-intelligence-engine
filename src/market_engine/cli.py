"""Command-line tools for local setup, event import, RSS ingestion and synthetic demo."""
import argparse
import json

from .db import init_db
from .forecasting import estimate_event_probability
from .evaluation import evaluate_binary_probabilities
from .importers import import_events_csv
from .feed_pipeline import ingest_feeds
from .market_data_importer import import_prices_csv
from .event_candidates import classify_source_documents


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
    parser.add_argument(
        "command",
        choices=["init-db", "demo", "import-events", "fetch-feeds", "import-prices", "classify-news"],
    )
    parser.add_argument("--file", help="CSV path required for import-events and import-prices")
    parser.add_argument("--source", default="manual_csv", help="Price-data source label for import-prices")
    parser.add_argument("--aliases", default="config/company_aliases.yaml", help="Company alias YAML used by classify-news")
    parser.add_argument(
        "--config",
        default="config/research_sources.yaml",
        help="YAML research source registry (default: config/research_sources.yaml)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate/fetch without database writes")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
        print("Database initialized.")
    elif args.command == "demo":
        run_demo()
    elif args.command == "import-events":
        if not args.file:
            parser.error("--file is required when command is import-events")
        init_db()
        result = import_events_csv(args.file, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    elif args.command == "fetch-feeds":
        init_db()
        result = ingest_feeds(config_path=args.config, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        if result["feeds_failed"]:
            raise SystemExit(1)
    elif args.command == "classify-news":
        init_db()
        result = classify_source_documents(aliases_path=args.aliases, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    elif args.command == "import-prices":
        if not args.file:
            parser.error("--file is required when command is import-prices")
        init_db()
        result = import_prices_csv(args.file, source_name=args.source, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        if result["invalid_rows"]:
            raise SystemExit(1)
    else:
        if not args.file:
            parser.error("--file is required when command is import-constituents")
        init_db()
        result = import_constituents_csv(args.file, source_name=args.source, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        if result["invalid_rows"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
