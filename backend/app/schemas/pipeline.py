"""Pydantic schemas for Pipeline responses."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PipelineRunResponse(BaseModel):
    run_id: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    rows_logs: Optional[int] = None
    rows_transfers: Optional[int] = None
    anomalies_found: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class PipelineRunStatusResponse(BaseModel):
    run_id: str
    status: str
    message: str = ""
