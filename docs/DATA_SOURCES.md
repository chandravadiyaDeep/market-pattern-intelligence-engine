# Data sources and collection policy

The maintained link directory is [Research Sources](../resources/RESEARCH_SOURCES.md); the machine-readable registry is [config/research_sources.yaml](../config/research_sources.yaml).

This page summarizes data requirements. Listing a source does not confirm API access, a right to scrape it, or permission to redistribute its data. Check current provider terms and rate limits before automating collection.

| Category | Starting point | What to capture |
|---|---|---|
| Index constituents and methodology | [Nifty Indices](https://www.niftyindices.com/reports) | Constituents with effective dates, methodology and index history |
| Corporate announcements | [NSE filings](https://www.nseindia.com/companies-listing/corporate-filings-announcements) and [BSE](https://www.bseindia.com/) | Disclosure type, timestamp, issuer, link, corrections and amendments |
| Exchange RSS | [NSE RSS directory](https://www.nseindia.com/static/rss-feed) | Official feed URLs for announcements, financial results, board meetings and circulars |
| Prices | [NSE Data & Analytics](https://www.nse.in/static/market-data/real-time-data-subscription) or an authorized vendor | Daily OHLCV, adjusted prices, symbol mappings and corporate actions |
| News | Licensed API or permitted RSS feed | Headline, first-published time, updated time, source, URL and permitted excerpt |
| Macro | [RBI Database on Indian Economy](https://data.rbi.org.in/) | Release timestamp, period covered, units and revisions when available |
| Search and social signals | Google Trends and platform APIs | Time-bucketed search interest, post volume and engagement with source/time provenance |

## Current pipeline

The RSS/Atom pipeline reads only configured feeds with enabled set to true in config/research_sources.yaml. It fetches the feed document—not each linked article—then normalizes headline, URL and publication time, stores retrieval/first-seen times, hashes the record, and skips duplicates in SQLite.

Start with a dry run:

    market-engine fetch-feeds --dry-run

Persist source metadata after reviewing the dry-run summary:

    market-engine fetch-feeds

The initial enabled feeds are general Business Standard and Economic Times feeds. They are useful for proving the pipeline but are not a guaranteed, complete or event-classified Nifty 50 feed. The NSE RSS page is reference-only until an exact official RSS URL is selected and reviewed.

## Rules

- Do not assume public pages allow high-volume automated collection.
- Never bypass authentication, paywalls, rate limits, CAPTCHAs or access controls.
- Store links and short metadata rather than full copyrighted articles unless the license permits it.
- Track original release time separately from download time.
- Record corrections and retractions; do not silently overwrite historical snapshots.
- Keep provider credentials in local environment variables, never source control.
- For backtests, preserve historical Nifty 50 constituent membership to reduce survivorship bias.
- Social volume and sentiment are noisy features, not verified facts or reliable trading signals by themselves.
