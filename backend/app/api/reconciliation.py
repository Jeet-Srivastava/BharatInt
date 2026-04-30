"""Reconciliation API router — list, detail, and resolve discrepancies."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from typing import Optional

from app.database import get_db
from app.schemas.reconciliation import ReconciliationResolveRequest
from app.services.audit import (
    build_confidence_breakdown,
    build_shift_details,
    build_transfer_details,
    get_latest_completed_run_id,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


@router.get("")
async def list_reconciliation(
    period: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    needs_review: Optional[bool] = Query(None),
    resolved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db)
):
    """List reconciliation records with filters and pagination."""
    latest_run_id = await get_latest_completed_run_id(session)
    where_clauses = ["1=1"]
    params = {'latest_run_id': latest_run_id}

    where_clauses.append("r.pipeline_run_id = :latest_run_id")

    if period:
        where_clauses.append("r.billing_period = :period")
        params['period'] = period
    if priority:
        where_clauses.append("r.priority = :priority")
        params['priority'] = priority
    if type:
        where_clauses.append("r.discrepancy_type = :type")
        params['type'] = type
    if needs_review is not None:
        where_clauses.append("r.needs_manual_review = :needs_review")
        params['needs_review'] = needs_review
    if resolved is not None:
        where_clauses.append("COALESCE(r.resolved, FALSE) = :resolved")
        params['resolved'] = resolved

    where = " AND ".join(where_clauses)
    offset = (page - 1) * limit

    # Count total
    count_result = await session.execute(
        text(f"SELECT COUNT(*) FROM reconciliation r WHERE {where}"),
        params
    )
    total = count_result.scalar()

    # Fetch page with worker name join
    result = await session.execute(
        text(f"""
            SELECT r.id, r.worker_id, w.name as worker_name, r.billing_period,
                   r.expected_paise, r.actual_paise, r.delta_paise,
                   r.discrepancy_type, r.needs_manual_review, r.review_reason,
                   r.priority, r.confidence_score, r.resolved, r.resolved_by,
                   r.resolved_at, r.resolution_notes, r.created_at
            FROM reconciliation r
            LEFT JOIN workers w ON r.worker_id = w.worker_id
            WHERE {where}
            ORDER BY
                CASE r.priority
                    WHEN 'P0' THEN 0 WHEN 'P1' THEN 1
                    WHEN 'P2' THEN 2 ELSE 3
                END,
                ABS(r.delta_paise) DESC
            LIMIT :limit OFFSET :offset
        """),
        {**params, 'limit': limit, 'offset': offset}
    )

    records = []
    for row in result.fetchall():
        records.append({
            'id': str(row.id),
            'worker_id': row.worker_id,
            'worker_name': row.worker_name,
            'billing_period': row.billing_period,
            'expected_paise': row.expected_paise,
            'actual_paise': row.actual_paise,
            'delta_paise': row.delta_paise,
            'discrepancy_type': row.discrepancy_type,
            'needs_manual_review': row.needs_manual_review,
            'review_reason': row.review_reason,
            'priority': row.priority,
            'confidence_score': float(row.confidence_score) if row.confidence_score else None,
            'resolved': bool(row.resolved),
            'resolved_by': row.resolved_by,
            'resolved_at': row.resolved_at.isoformat() if row.resolved_at else None,
            'resolution_notes': row.resolution_notes,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })

    return {"records": records, "total": total, "page": page, "limit": limit}


@router.get("/{record_id}")
async def get_reconciliation(record_id: str, session: AsyncSession = Depends(get_db)):
    """Get single reconciliation record with full detail."""
    result = await session.execute(
        text("""
            SELECT r.*, w.name as worker_name, w.phone as worker_phone,
                   w.role, w.state, w.seniority
            FROM reconciliation r
            LEFT JOIN workers w ON r.worker_id = w.worker_id
            WHERE r.id = :id
        """),
        {'id': record_id}
    )
    row = result.fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Record not found"})

    shifts = await build_shift_details(session, row.worker_id, row.billing_period)
    transfers = await build_transfer_details(session, row.worker_id, row.billing_period)
    confidence_breakdown = build_confidence_breakdown(shifts)

    return {
        'id': str(row.id),
        'worker_id': row.worker_id,
        'worker_name': row.worker_name,
        'worker_phone': row.worker_phone,
        'role': row.role,
        'state': row.state,
        'seniority': row.seniority,
        'billing_period': row.billing_period,
        'expected_paise': row.expected_paise,
        'actual_paise': row.actual_paise,
        'delta_paise': row.delta_paise,
        'discrepancy_type': row.discrepancy_type,
        'needs_manual_review': row.needs_manual_review,
        'review_reason': row.review_reason,
        'priority': row.priority,
        'confidence_score': float(row.confidence_score) if row.confidence_score else None,
        'resolved': bool(row.resolved),
        'resolved_by': row.resolved_by,
        'resolution_notes': row.resolution_notes,
        'shifts': shifts,
        'transfers': transfers,
        'confidence_breakdown': confidence_breakdown,
    }


@router.patch("/{record_id}/resolve")
async def resolve_reconciliation(
    record_id: str,
    body: ReconciliationResolveRequest,
    session: AsyncSession = Depends(get_db)
):
    """Mark a reconciliation record as resolved."""
    await session.execute(
        text("""
            UPDATE reconciliation SET
                resolved = TRUE,
                resolved_by = :resolved_by,
                resolution_notes = :notes,
                resolved_at = NOW()
            WHERE id = :id
        """),
        {
            'id': record_id,
            'resolved_by': body.resolved_by,
            'notes': body.resolution_notes,
        }
    )
    await session.commit()
    return {"message": "Record marked as resolved", "id": record_id}
