"""Worker model — canonical worker registry."""

from sqlalchemy import Column, String, Date
from app.database import Base


class Worker(Base):
    __tablename__ = "workers"

    worker_id = Column(String(10), primary_key=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(10), nullable=False, unique=True)
    state = Column(String(5), nullable=False)
    role = Column(String(50), nullable=False)
    seniority = Column(String(10), nullable=False)
    registered_on = Column(Date, nullable=False)
