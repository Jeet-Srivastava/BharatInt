"""Pydantic schemas for Reconciliation responses."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ReconciliationResponse(BaseModel):
    id: str
    worker_id: Optional[str] = None
    worker_name: Optional[str] = None
    billing_period: str
    expected_paise: Optional[int] = None
    actual_paise: Optional[int] = None
    delta_paise: Optional[int] = None
    discrepancy_type: str
    needs_manual_review: bool = False
    review_reason: Optional[str] = None
    priority: Optional[str] = None
    confidence_score: Optional[float] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReconciliationResolveRequest(BaseModel):
    resolved_by: str
    resolution_notes: str


class ReconciliationListResponse(BaseModel):
    records: list[ReconciliationResponse]
    total: int
    page: int
    limit: int


class ReconciliationSummary(BaseModel):
    total_expected_paise: int
    total_actual_paise: int
    net_delta_paise: int
    total_records: int
    review_count: int
    resolved_count: int
