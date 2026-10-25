"""Data-source connector contracts; provider access must be authorized."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawRecord:
    """Normalized record returned by a future connector."""
    provider: str
    title: str
    url: str | None
    published_at: datetime | None
    retrieved_at: datetime
    body: str | None = None
    content_hash: str | None = None


class DataSource(Protocol):
    """Contract for authorized news, filing or market-data connectors."""
    def fetch_since(self, since: datetime) -> list[RawRecord]:
        """Fetch authorized records available since a given timestamp."""
        ...


SOURCE_CATALOG = {
    "nse_filings": "Official NSE corporate announcements; verify current automation terms.",
    "bse_filings": "Official BSE filings for cross-checking disclosures; verify current terms.",
    "nifty_indices": "Nifty Indices methodology, constituents and index history; verify usage rights.",
    "company_ir": "Issuer investor-relations pages, earnings releases and annual reports.",
    "market_prices": "A market-data provider with explicit historical data usage rights.",
    "news": "A licensed provider or permitted RSS sources; do not scrape by default.",
}
