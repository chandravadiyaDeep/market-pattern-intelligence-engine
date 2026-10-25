# Data sources and collection policy

This is a planning inventory, not confirmation of API access or permission to scrape or redistribute data. Check current provider terms and rate limits before implementing a connector.

| Category | Starting point | What to capture |
|---|---|---|
| Index constituents and methodology | Nifty Indices | Constituents with effective dates, methodology and index history |
| Corporate announcements | NSE and BSE official filing portals | Disclosure type, timestamp, issuer, link, corrections and amendments |
| Company financials | Exchange filings and issuer investor-relations sites | Results, annual reports, presentations and guidance |
| Prices | A provider with suitable historical-data license | Daily OHLCV, adjusted prices, symbol mappings and corporate actions |
| News | Licensed API or permitted RSS feed | Headline, first-published time, updated time, source, URL and permitted excerpt |
| Macro | RBI public data | Release timestamp, period covered, units and revisions when available |

## Rules

- Do not assume public pages allow high-volume automated collection.
- Never bypass authentication, paywalls, rate limits, or access controls.
- Store links and short metadata rather than full copyrighted articles unless the license permits it.
- Track original release time separately from download time.
- Record corrections and retractions.
- Keep provider credentials in local environment variables, never source control.
- For backtests, preserve historical Nifty 50 constituent membership to reduce survivorship bias.
