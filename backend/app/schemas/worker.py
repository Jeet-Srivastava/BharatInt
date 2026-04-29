"""Pydantic schemas for Worker responses."""

from pydantic import BaseModel
from datetime import date
from typing import Optional


class WorkerBase(BaseModel):
    worker_id: str
    name: str
    phone: str
    state: str
    role: str
    seniority: str
    registered_on: date


class WorkerResponse(WorkerBase):
    class Config:
        from_attributes = True


class WorkerListResponse(BaseModel):
    workers: list[WorkerResponse]
    total: int
