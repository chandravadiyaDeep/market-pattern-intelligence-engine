# Research Sources Directory

This is the human-maintained directory of sources for the Market Pattern Intelligence Engine. Add new source links here and in `config/research_sources.yaml` so humans and code share one registry.

## 1. Official exchange and corporate events

| Source | Link | Use |
|---|---|---|
| NSE corporate announcements | https://www.nseindia.com/companies-listing/corporate-filings-announcements | Primary evidence for company disclosures |
| NSE RSS directory | https://www.nseindia.com/static/rss-feed | Official RSS feeds for announcements, financial results, board meetings, corporate actions and circulars |
| NSE latest corporate announcements RSS | https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml | Feed configured for headline ingestion |
| NSE corporate actions RSS | https://nsearchives.nseindia.com/content/RSS/Corporate_action.xml | Feed configured for corporate-action headlines |
| NSE board meetings RSS | https://nsearchives.nseindia.com/content/RSS/Board_Meetings.xml | Feed configured for board-meeting headlines |
| NSE financial results RSS | https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml | Feed configured; confirm URL against the current official RSS directory if it fails |
| NSE all reports | https://www.nseindia.com/all-reports | Daily market reports and exchange files |
| NSE historical reports | https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives | Historical equity and index report discovery |
| NSE Data & Analytics | https://www.nse.in/static/market-data/real-time-data-subscription | Official market-data product and subscription details |
| Nifty Indices historical reports | https://www.niftyindices.com/reports | Index history, index values and related reports |
| BSE India | https://www.bseindia.com/ | Secondary official source for issuer filings and exchange announcements |
| SEBI | https://www.sebi.gov.in/ | Regulations, circulars and enforcement/news releases |
| RBI Database on Indian Economy | https://data.rbi.org.in/ | Macro and financial time series |

## 2. Business and market news

| Source | Link | Intended use |
|---|---|---|
| Business Standard | https://www.business-standard.com/ | Company, market and economy news |
| Economic Times Markets | https://economictimes.indiatimes.com/markets | Market and company coverage |
| Moneycontrol Markets | https://www.moneycontrol.com/news/business/markets/ | Indian market news and company coverage |
| Mint Markets | https://www.livemint.com/market | Market and corporate news |
| Reuters India / Asia markets | https://www.reuters.com/markets/asia/india/ | International wire coverage of Indian markets |
| The Hindu BusinessLine Markets | https://www.thehindubusinessline.com/markets/ | Markets, sectors and corporate developments |
| Financial Express Markets | https://www.financialexpress.com/market/ | Markets, company and economic news |
| Google News | https://news.google.com/ | Broad news discovery; deduplicate syndicated copies |

## 3. Search interest and social discussion

| Source | Link | What it can contribute | Access note |
|---|---|---|---|
| Google Trends | https://trends.google.com/trends/ | Search-interest changes around companies, events and sectors | UI is available; API access is limited alpha—see https://developers.google.com/search/apis/trends |
| X developer platform | https://developer.x.com/en | Public discussion velocity and topic changes | Use official API access and comply with plan and redistribution terms |
| Reddit developer platform | https://developers.reddit.com/ | Discussion volume and community topic changes | Use approved API access; check current terms and rate limits |
| YouTube Data API | https://developers.google.com/youtube/v3 | Public video metadata and engagement indicators | API key, quota and platform terms apply; do not assume all comments are available |
| Stocktwits | https://stocktwits.com/ | Investor discussion and ticker mentions | Verify current API access and terms before integrating |

## 4. Starter RSS ingestion

The code pipeline fetches only URLs in the `feeds` list in `config/research_sources.yaml` with `enabled: true`. At initial setup, enabled feeds include NSE announcements, corporate actions, board meetings and financial results, plus market-specific RSS feeds from Business Standard and The Economic Times. Feed availability and coverage can change; they are not a guaranteed complete Nifty 50 feed.

The NSE RSS directory is listed as a reference-only entry because its page contains links to individual feeds. Open the official directory, choose the exact RSS feed that fits your use, confirm the feed URL and terms, then add that URL as a new feed entry before enabling it. Do not set the directory landing page itself as a feed.

Run a dry run first:

```powershell
market-engine fetch-feeds --dry-run
```

Then persist metadata:

```powershell
market-engine fetch-feeds
```

The pipeline stores the headline, source/article URL, publication timestamp where available, first-seen time, retrieval time, a content hash and a short feed-provided excerpt. It does not download full article pages, automatically classify a headline as a corporate event, or generate a prediction. The Economic Times states its RSS feeds are for personal, non-commercial use and restricts retaining or redistributing feed content; follow its current terms and do not use that feed in a commercial product without permission.

## 5. Data quality rules

1. **Primary sources first:** use exchange filings and issuer releases to verify market-moving claims.
2. **Keep timestamps separate:** publication time is not retrieval time; article updates must not be backdated.
3. **Deduplicate syndicated news:** the same wire story repeated by several outlets is not several independent signals.
4. **Store evidence:** keep the source URL and a short permitted excerpt. Retain full text only if the license permits it.
5. **Separate mention from sentiment:** a ticker mention, a positive headline and a positive price impact are different labels.
6. **Avoid look-ahead:** only data available by a prediction's as-of timestamp may be used as a feature.
7. **Don't scrape by default:** no bypassing login, paywalls, CAPTCHAs, rate limits or technical controls. Confirm current terms before automated access or redistribution.
8. **Treat social data as noisy:** bots, promotions, coordinated posts, sarcasm and duplicated posts can distort mention counts and sentiment.
9. **Record provenance:** every record should be traceable to its source and ingestion time.
10. **No live trading:** pipeline data is for research and paper testing only.

## 6. Roadmap for additional connectors

- **Stage A:** RSS/Atom source ingestion and deduplication (implemented).
- **Stage B:** official exchange announcement feeds with per-company symbol mapping and corrections handling.
- **Stage C:** licensed daily OHLCV and historical Nifty 50 constituent membership.
- **Stage D:** licensed/approved social and search-interest connectors.
- **Stage E:** event extraction with evidence snippets and human review.
- **Stage F:** point-in-time feature joins, walk-forward evaluation and paper forecasts.

Do not treat any website listed here as a live API until its access method, terms, coverage and update cadence have been checked.
