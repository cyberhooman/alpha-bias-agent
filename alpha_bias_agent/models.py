"""Shared response / timeline models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TimelineEntry(BaseModel):
    step: str
    method: str
    path: str
    status: int
    latency_ms: int
    summary: Any = None
    error: Optional[str] = None


class RankedTicker(BaseModel):
    rank: int
    symbol: str
    company_name: str
    score: float
    why: str
    risks: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class BiasResponse(BaseModel):
    query: str
    subsector: str
    mode: str  # "mock" | "live"
    tickers: list[RankedTicker]
    timeline: list[TimelineEntry]
    disclaimer: str = (
        "Research bias only — not trade advice. No orders are placed."
    )
