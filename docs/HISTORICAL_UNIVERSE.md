# Historical index-universe membership

The engine now stores dated constituent intervals so a research run can select the companies that were members on a historical date instead of assuming today's index membership applied in the past.

## CSV format

Required columns:

- `symbol`: exchange/vendor symbol used by your price dataset
- `company_name`: issuer name
- `start_date`: first membership date, `YYYY-MM-DD`

Optional columns:

- `end_date`: last membership date, `YYYY-MM-DD`; leave blank for an interval still active in the source's latest record
- `source_name`: provenance label; defaults to the CLI `--source` value

Example structure (replace with source-verified records; do not use these placeholders as actual index history):

```csv
symbol,company_name,start_date,end_date,source_name
EXAMPLE_A,Example Company A,2020-04-01,2022-03-31,official-source-name
EXAMPLE_A,Example Company A,2024-04-01,,official-source-name
```

## Import on Windows PowerShell

```powershell
# Validate first without writing records
market-engine import-constituents --file .\data\nifty_constituents_history.csv --source official-or-authorized-source --dry-run

# Import after checking the validation report
market-engine import-constituents --file .\data\nifty_constituents_history.csv --source official-or-authorized-source
```

## Query the universe

- `GET /universe/constituents?as_of=2022-06-01`
- `GET /universe/constituents?as_of=2025-01-01`

The endpoint returns intervals active on the requested date. The API does not download membership history or certify that the CSV is official. Record the source URL, retrieval date, methodology and any corrections alongside the dataset. Ensure membership start/end dates match the chosen provider's convention and do not silently forward-fill missing membership.

## Research safeguards

- Use point-in-time membership for historical universe backtests to reduce survivorship bias.
- Do not infer that a company belonged to Nifty 50 merely because it is in the current index.
- Preserve delisted, renamed, merged and removed constituents when the source provides them.
- Check for conflicting intervals and ticker changes before running universe-wide evaluations.
- This importer checks date formats and interval order; it does not certify official coverage or resolve conflicting source records.
