"""Pydantic schemas for Dashboard stats."""

from pydantic import BaseModel
from typing import Optional


class DiscrepancyBreakdown(BaseModel):
    type: str
    count: int
    total_delta_paise: int


class ReviewCountByPriority(BaseModel):
    priority: str
    count: int


class DashboardStats(BaseModel):
    total_expected_paise: int
    total_actual_paise: int
    net_delta_paise: int
    review_count_by_priority: list[ReviewCountByPriority]
    discrepancy_breakdown: list[DiscrepancyBreakdown]
    total_workers: int
    total_records: int
    resolved_count: int
    unresolved_count: int
