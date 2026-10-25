"""Validated API schemas for source-linked events and research forecasts."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


EventType = Literal[
    "leadership", "regulatory", "earnings", "governance",
    "merger_acquisition", "capital_allocation", "operations", "other"
]


class EventCreate(BaseModel):
    """An event as known from a source at a specific time."""
    symbol: str = Field(min_length=1, max_length=24)
    event_type: EventType
    title: str = Field(min_length=3, max_length=500)
    summary: str = Field(default="", max_length=5000)
    event_time: datetime | None = None
    published_at: datetime
    first_seen_at: datetime
    source_url: HttpUrl
    source_name: str = Field(min_length=1, max_length=200)
    confidence: float = Field(default=0.7, ge=0, le=1)
    severity: int = Field(default=1, ge=1, le=5)


class EventRecord(EventCreate):
    """Stored event with database identity."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ForecastCreate(BaseModel):
    """A testable, timestamped probability forecast."""
    symbol: str = Field(min_length=1, max_length=24)
    target: str = Field(min_length=3, max_length=300)
    horizon_days: int = Field(ge=1, le=252)
    probability: float = Field(ge=0, le=1)
    model_version: str = Field(min_length=1, max_length=100)
    evidence: list[int] = Field(default_factory=list)
    created_at: datetime


class ForecastRecord(ForecastCreate):
    id: int
    outcome: int | None = None
    outcome_recorded_at: datetime | None = None


class OutcomeUpdate(BaseModel):
    """Outcome is recorded after its resolution; forecast probability is immutable."""
    outcome: int = Field(ge=0, le=1)
    outcome_recorded_at: datetime
