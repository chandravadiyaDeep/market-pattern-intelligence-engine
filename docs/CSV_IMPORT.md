# Importing a curated corporate-event CSV

The importer lets you start with a small hand-curated or appropriately licensed event dataset before a news connector is added.

## Required columns

- `symbol`: exchange symbol, normalized to uppercase.
- `event_type`: one of leadership, regulatory, earnings, governance, merger_acquisition, capital_allocation, operations, other.
- `title`: short event title.
- `summary`: concise description with no unsupported inference.

Optional event columns: `event_at`, `disclosed_at`, `evidence_confidence` (0–1), `materiality` (1–5), and `status` (unverified, corroborated, official, retracted). Optional provenance columns: `source_url`, `source_type`, `source_title`, and `source_published_at`. When `source_url` is supplied, the importer stores or reuses a source-document record and links the event to it. Rows without a source URL can still be imported but are counted in `rows_missing_source_url`.

Use ISO 8601 timestamps with a timezone offset whenever possible. `disclosed_at` is the date the information became available to the public, not necessarily the date the underlying event happened.

## Commands

```powershell
# Validate rows without changing the database
market-engine import-events --file .\examples\events_template.csv --dry-run

# Import valid rows
market-engine import-events --file .\your_events.csv
```

The importer skips duplicates matching symbol, event type, title, and disclosure timestamp. Invalid rows are reported in the command output. The example CSV contains synthetic data only and must not be treated as a real HDFC Bank event.
