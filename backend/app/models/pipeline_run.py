"""PipelineRun model — audit trail for pipeline executions."""

import uuid
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy import func
from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    status = Column(String(20), default="pending")
    rows_logs = Column(Integer, nullable=True)
    rows_transfers = Column(Integer, nullable=True)
    anomalies_found = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
