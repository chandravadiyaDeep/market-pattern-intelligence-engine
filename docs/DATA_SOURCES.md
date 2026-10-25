# Data source policy

Start with small, manually curated datasets or sources whose terms explicitly permit the intended use. Confirm current terms before automated collection, bulk downloading or redistribution.

## Candidate sources

- NSE corporate filings: https://www.nseindia.com/companies-listing/corporate-filings-announcements
- Nifty Indices: https://www.niftyindices.com/
- BSE India: https://www.bseindia.com/
- RBI Database on Indian Economy: https://data.rbi.org.in/
- Company investor-relations pages and published reports.
- A licensed historical OHLCV provider that specifies corporate-action treatment and personal-research rights.
- A licensed news provider or explicitly permitted RSS source.

## Provenance fields

Store source type, title, URL, publication timestamp, first-seen timestamp, retrieval timestamp, content hash and extraction version. Retain article snapshots only where terms permit.

## Data integrity

- Syndicated copies are not independent confirmations.
- Updated articles may contain information that was not available at first publication.
- Normalize timestamps and exchange trading calendars.
- Use historical index constituents for historical universe tests to reduce survivorship bias.
- Never commit API keys, licensed data dumps or credentials.
