"""Workers API router — list, detail, and audit trail."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from typing import Optional

from app.database import get_db
from app.services.audit import (
    build_confidence_breakdown,
    build_shift_details,
    build_transfer_details,
    fetch_worker_record,
    summarise_identity_confidence,
)

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


@router.get("")
async def list_workers(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db)
):
    """List all workers, searchable by name or phone."""
    where = "1=1"
    params = {}

    if search:
        where = "(LOWER(w.name) LIKE :search OR w.phone LIKE :search)"
        params['search'] = f"%{search.lower()}%"

    offset = (page - 1) * limit

    # Count
    count_result = await session.execute(
        text(f"SELECT COUNT(*) FROM workers w WHERE {where}"),
        params
    )
    total = count_result.scalar()

    # Fetch with review count
    result = await session.execute(
        text(f"""
            SELECT w.worker_id, w.name, w.phone, w.state, w.role, w.seniority,
                   w.registered_on,
                   COALESCE(review_counts.cnt, 0) as review_count
            FROM workers w
            LEFT JOIN (
                SELECT worker_id, COUNT(*) as cnt
                FROM reconciliation
                WHERE needs_manual_review = TRUE AND resolved = FALSE
                GROUP BY worker_id
            ) review_counts ON w.worker_id = review_counts.worker_id
            WHERE {where}
            ORDER BY w.worker_id
            LIMIT :limit OFFSET :offset
        """),
        {**params, 'limit': limit, 'offset': offset}
    )

    workers = []
    for row in result.fetchall():
        workers.append({
            'worker_id': row.worker_id,
            'name': row.name,
            'phone': row.phone,
            'state': row.state,
            'role': row.role,
            'seniority': row.seniority,
            'registered_on': row.registered_on.isoformat() if row.registered_on else None,
            'review_count': row.review_count,
        })

    return {"workers": workers, "total": total, "page": page, "limit": limit}


@router.get("/{worker_id}")
async def get_worker(worker_id: str, session: AsyncSession = Depends(get_db)):
    """Get worker detail."""
    row = await fetch_worker_record(session, worker_id)
    if not row:
        return JSONResponse(status_code=404, content={"error": "Worker not found"})

    return {
        'worker_id': row.worker_id,
        'name': row.name,
        'phone': row.phone,
        'state': row.state,
        'role': row.role,
        'seniority': row.seniority,
        'registered_on': row.registered_on.isoformat() if row.registered_on else None,
    }


@router.get("/{worker_id}/audit-trail")
async def get_worker_audit_trail(worker_id: str, session: AsyncSession = Depends(get_db)):
    """Get complete audit trail: shifts, transfers, reconciliation per period."""

    # Worker info
    worker = await fetch_worker_record(session, worker_id)
    if not worker:
        return JSONResponse(status_code=404, content={"error": "Worker not found"})

    shifts = await build_shift_details(session, worker_id)
    transfers = await build_transfer_details(session, worker_id)
    identity_summary = summarise_identity_confidence(shifts)
    confidence_breakdown = build_confidence_breakdown(shifts)

    # Reconciliation per period
    recon_result = await session.execute(
        text("""
            SELECT id, billing_period, expected_paise, actual_paise,
                   delta_paise, discrepancy_type, needs_manual_review,
                   review_reason, priority, confidence_score, resolved
            FROM reconciliation
            WHERE worker_id = :wid
            ORDER BY billing_period DESC
        """),
        {'wid': worker_id}
    )
    reconciliation = [
        {
            'id': str(r.id),
            'billing_period': r.billing_period,
            'expected_paise': r.expected_paise,
            'actual_paise': r.actual_paise,
            'delta_paise': r.delta_paise,
            'discrepancy_type': r.discrepancy_type,
            'needs_manual_review': r.needs_manual_review,
            'review_reason': r.review_reason,
            'priority': r.priority,
            'confidence_score': float(r.confidence_score) if r.confidence_score else None,
            'resolved': r.resolved,
        }
        for r in recon_result.fetchall()
    ]

    return {
        'worker': {
            'worker_id': worker.worker_id,
            'name': worker.name,
            'phone': worker.phone,
            'state': worker.state,
            'role': worker.role,
            'seniority': worker.seniority,
            'registered_on': worker.registered_on.isoformat() if worker.registered_on else None,
            'identity_confidence': identity_summary['average'],
            'identity_confidence_floor': identity_summary['minimum'],
        },
        'shifts': shifts,
        'transfers': transfers,
        'reconciliation': reconciliation,
        'confidence_breakdown': confidence_breakdown,
    }
