"""ShiftLog model — normalised supervisor log entries."""

from sqlalchemy import Column, String, Date, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.database import Base


class ShiftLog(Base):
    __tablename__ = "shift_logs"

    log_id = Column(String(10), primary_key=True)
    worker_id = Column(String(10), nullable=True)  # FK to workers, nullable for unresolvable
    raw_worker_name = Column(String(255), nullable=True)
    raw_worker_phone = Column(String(30), nullable=True)
    supervisor_id = Column(String(10), nullable=True)
    work_date = Column(Date, nullable=False)
    hours = Column(Numeric(5, 2), nullable=False)
    vendor_app = Column(String(30), nullable=True)
    entered_at_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    tz_corrected = Column(Boolean, default=False)
    identity_confidence = Column(Numeric(4, 3), nullable=True)
    hours_anomaly = Column(Boolean, default=False)
    pipeline_run_id = Column(UUID(as_uuid=True), nullable=False)
