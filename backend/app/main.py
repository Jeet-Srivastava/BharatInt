"""FastAPI application — Wage Payout Reconciliation Platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.models import *  # noqa: F401 — import all models for table creation
from app.api.pipeline import router as pipeline_router
from app.api.reconciliation import router as reconciliation_router
from app.api.workers import router as workers_router
from app.api.stats import router as stats_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Wage Payout Reconciliation Platform",
    version="1.0.0",
    description="Bharat Intelligence — Wage reconciliation, anomaly detection, and audit trail",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(pipeline_router)
app.include_router(reconciliation_router)
app.include_router(workers_router)
app.include_router(stats_router)


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "wage-reconciliation-backend"}
