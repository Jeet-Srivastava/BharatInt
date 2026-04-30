"""BankTransfer model — normalised payment records."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, Index, String
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from app.database import Base


class BankTransfer(Base):
    __tablename__ = "bank_transfers"

    utr = Column(String(20), primary_key=True)
    worker_id = Column(String(10), nullable=True)  # FK to workers
    raw_worker_name = Column(String(255), nullable=True)
    raw_worker_phone = Column(String(15), nullable=True)
    amount_paise = Column(BigInteger, nullable=False)
    transfer_date = Column(Date, nullable=False)
    billing_period = Column(String(7), nullable=False)  # YYYY-MM
    account_last4 = Column(String(4), nullable=True)
    precision_bug = Column(Boolean, default=False)
    pipeline_run_id = Column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_bank_transfers_amount_positive"),
        Index("ix_bank_transfers_worker_billing_period", "worker_id", "billing_period"),
    )
