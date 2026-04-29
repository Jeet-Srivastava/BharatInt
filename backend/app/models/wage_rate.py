"""WageRate model — effective-dated hourly rates stored in paise."""

from sqlalchemy import Column, Integer, String, Date, BigInteger
from app.database import Base


class WageRate(Base):
    __tablename__ = "wage_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(50), nullable=False)
    state = Column(String(5), nullable=False)
    seniority = Column(String(10), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)  # NULL = open-ended (treat as 9999-12-31)
    hourly_rate_paise = Column(BigInteger, nullable=False)  # stored in paise, not INR
