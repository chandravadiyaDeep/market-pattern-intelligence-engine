# Importing a curated corporate-event CSV

The importer lets you start with a small hand-curated or appropriately licensed event dataset before a news connector is added.

## Required columns

- `symbol`: exchange symbol, normalized to uppercase.
- `event_type`: one of leadership, regulatory, earnings, governance, merger_acquisition, capital_allocation, operations, other.
- `title`: short event title.
- `summary`: concise description with no unsupported inference.

Optional columns: `event_at`, `disclosed_at`, `evidence_confidence` (0–1), `materiality` (1–5), and `status` (unverified, corroborated, official, retracted).

Use ISO 8601 timestamps with a timezone offset whenever possible. `disclosed_at` is the date the information became available to the public, not necessarily the date the underlying event happened.

## Commands

```powershell
# Validate rows without changing the database
market-engine import-events --file .\examples\events_template.csv --dry-run

# Import valid rows
market-engine import-events --file .\your_events.csv
```

The importer skips duplicates matching symbol, event type, title, and disclosure timestamp. Invalid rows are reported in the command output. The example CSV contains synthetic data only and must not be treated as a real HDFC Bank event.
