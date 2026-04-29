"""Pipeline API router — trigger and monitor pipeline runs."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.database import get_db

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.post("/run", status_code=202)
async def trigger_pipeline(session: AsyncSession = Depends(get_db)):
    """Create a PipelineRun record and dispatch Celery task."""
    run_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO pipeline_runs (run_id, status)
            VALUES (:run_id, 'pending')
        """),
        {'run_id': run_id}
    )
    await session.commit()

    # Dispatch Celery task
    from app.worker import run_pipeline_task
    run_pipeline_task.delay(run_id)

    return JSONResponse(
        status_code=202,
        content={"run_id": run_id, "status": "pending", "message": "Pipeline triggered"}
    )


@router.get("/runs")
async def list_pipeline_runs(session: AsyncSession = Depends(get_db)):
    """List all pipeline runs ordered by started_at DESC."""
    result = await session.execute(
        text("""
            SELECT run_id, started_at, completed_at, status,
                   rows_logs, rows_transfers, anomalies_found, error_message
            FROM pipeline_runs
            ORDER BY started_at DESC
        """)
    )
    runs = []
    for row in result.fetchall():
        runs.append({
            'run_id': str(row.run_id),
            'started_at': row.started_at.isoformat() if row.started_at else None,
            'completed_at': row.completed_at.isoformat() if row.completed_at else None,
            'status': row.status,
            'rows_logs': row.rows_logs,
            'rows_transfers': row.rows_transfers,
            'anomalies_found': row.anomalies_found,
            'error_message': row.error_message,
        })
    return {"runs": runs}


@router.get("/runs/{run_id}")
async def get_pipeline_run(run_id: str, session: AsyncSession = Depends(get_db)):
    """Get status of a single pipeline run."""
    result = await session.execute(
        text("""
            SELECT run_id, started_at, completed_at, status,
                   rows_logs, rows_transfers, anomalies_found, error_message
            FROM pipeline_runs
            WHERE run_id = :run_id
        """),
        {'run_id': run_id}
    )
    row = result.fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Run not found"})

    return {
        'run_id': str(row.run_id),
        'started_at': row.started_at.isoformat() if row.started_at else None,
        'completed_at': row.completed_at.isoformat() if row.completed_at else None,
        'status': row.status,
        'rows_logs': row.rows_logs,
        'rows_transfers': row.rows_transfers,
        'anomalies_found': row.anomalies_found,
        'error_message': row.error_message,
    }
