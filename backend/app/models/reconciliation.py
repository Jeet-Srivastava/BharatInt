"""Reconciliation model — one row per worker per billing period."""

import uuid
from sqlalchemy import Column, String, BigInteger, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy import UniqueConstraint, func
from app.database import Base


class Reconciliation(Base):
    __tablename__ = "reconciliation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(String(10), nullable=True)
    billing_period = Column(String(7), nullable=False)
    expected_paise = Column(BigInteger, nullable=True)
    actual_paise = Column(BigInteger, nullable=True)
    delta_paise = Column(BigInteger, nullable=True)
    discrepancy_type = Column(String(30), nullable=False)
    needs_manual_review = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    priority = Column(String(5), nullable=True)
    confidence_score = Column(Numeric(4, 3), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    pipeline_run_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("worker_id", "billing_period", "pipeline_run_id"),
    )
