"""Application configuration — loads from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/reconciliation_db"
)

DATABASE_URL_SYNC: str = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://user:password@localhost:5432/reconciliation_db"
)

# Redis
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Security
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")

# Data paths
DATA_DIR: str = os.getenv("DATA_DIR", "/data/samples")

# Billing period format
BILLING_PERIOD_FORMAT: str = "%Y-%m"
