"""Validated domain models. Timestamp fields intentionally remain distinct."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator

EventType = Literal[
    "leadership", "regulatory", "earnings", "governance", "merger_acquisition",
    "capital_allocation", "operations", "other"
]


class SourceDocumentIn(BaseModel):
    """An original source record and its provenance."""
    source_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    url: str | None = None
    published_at: datetime | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str | None = None
    text_excerpt: str | None = Field(default=None, max_length=5000)


class EventIn(BaseModel):
    """A structured event; extracted claims are not automatically confirmed facts."""
    symbol: str = Field(min_length=1, max_length=30)
    event_type: EventType
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=3000)
    event_at: datetime | None = None
    disclosed_at: datetime | None = None
    source_id: int | None = None
    evidence_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    materiality: int = Field(default=1, ge=1, le=5)
    status: Literal["unverified", "corroborated", "official", "retracted"] = "unverified"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        """Normalize symbols for joins while preserving original source text."""
        return value.strip().upper()


class PredictionIn(BaseModel):
    """Forecast definition and probability as produced at a known time."""
    symbol: str = Field(min_length=1, max_length=30)
    target_name: str = Field(min_length=1, max_length=200)
    horizon_sessions: int = Field(ge=1, le=252)
    probability: float = Field(ge=0.0, le=1.0)
    model_name: str = Field(min_length=1, max_length=100)
    model_version: str = Field(default="0.1.0", max_length=50)
    evidence_note: str = Field(default="", max_length=3000)
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaperOrderIn(BaseModel):
    """A simulated order request only; no broker/live order interface exists."""
    symbol: str = Field(min_length=1, max_length=30)
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0)
    reference_price: float = Field(gt=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    strategy_name: str = Field(default="manual-paper", max_length=100)
    signal_time: datetime
    expected_fill_time: datetime
    rationale: str = Field(default="", max_length=2000)

    @field_validator("expected_fill_time")
    @classmethod
    def validate_execution_after_signal(cls, value: datetime, info):
        """Reject simulated fill times before the signal time."""
        signal_time = info.data.get("signal_time")
        if signal_time and value < signal_time:
            raise ValueError("expected_fill_time must be at or after signal_time")
        return value
