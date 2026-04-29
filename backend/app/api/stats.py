"""Stats API router — dashboard summary data."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/summary")
async def get_summary(
    period: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    """Dashboard summary: totals, review counts by priority, discrepancy breakdown."""
    where = "1=1"
    params = {}
    if period:
        where = "r.billing_period = :period"
        params['period'] = period

    # Totals
    totals_result = await session.execute(
        text(f"""
            SELECT
                COALESCE(SUM(r.expected_paise), 0) as total_expected,
                COALESCE(SUM(r.actual_paise), 0) as total_actual,
                COALESCE(SUM(r.delta_paise), 0) as net_delta,
                COUNT(*) as total_records,
                COUNT(*) FILTER (WHERE r.resolved = TRUE) as resolved_count,
                COUNT(*) FILTER (WHERE r.needs_manual_review = TRUE AND r.resolved = FALSE) as unresolved_count
            FROM reconciliation r
            WHERE {where}
        """),
        params
    )
    totals = totals_result.fetchone()

    # Review count by priority
    priority_result = await session.execute(
        text(f"""
            SELECT r.priority, COUNT(*) as cnt
            FROM reconciliation r
            WHERE {where} AND r.needs_manual_review = TRUE AND r.resolved = FALSE
            GROUP BY r.priority
            ORDER BY r.priority
        """),
        params
    )
    review_by_priority = [
        {'priority': row.priority, 'count': row.cnt}
        for row in priority_result.fetchall()
    ]

    # Discrepancy type breakdown
    disc_result = await session.execute(
        text(f"""
            SELECT r.discrepancy_type as type, COUNT(*) as count,
                   COALESCE(SUM(ABS(r.delta_paise)), 0) as total_delta_paise
            FROM reconciliation r
            WHERE {where}
            GROUP BY r.discrepancy_type
            ORDER BY count DESC
        """),
        params
    )
    discrepancy_breakdown = [
        {'type': row.type, 'count': row.count, 'total_delta_paise': int(row.total_delta_paise)}
        for row in disc_result.fetchall()
    ]

    # Total workers
    workers_result = await session.execute(text("SELECT COUNT(*) FROM workers"))
    total_workers = workers_result.scalar()

    # Per-period breakdown for charts
    period_result = await session.execute(
        text("""
            SELECT r.billing_period,
                   COALESCE(SUM(r.expected_paise), 0) as expected,
                   COALESCE(SUM(r.actual_paise), 0) as actual,
                   COALESCE(SUM(r.delta_paise), 0) as delta
            FROM reconciliation r
            GROUP BY r.billing_period
            ORDER BY r.billing_period
        """)
    )
    period_breakdown = [
        {
            'period': row.billing_period,
            'expected_paise': int(row.expected),
            'actual_paise': int(row.actual),
            'delta_paise': int(row.delta),
        }
        for row in period_result.fetchall()
    ]

    return {
        'total_expected_paise': int(totals.total_expected),
        'total_actual_paise': int(totals.total_actual),
        'net_delta_paise': int(totals.net_delta),
        'total_records': totals.total_records,
        'resolved_count': totals.resolved_count,
        'unresolved_count': totals.unresolved_count,
        'total_workers': total_workers,
        'review_count_by_priority': review_by_priority,
        'discrepancy_breakdown': discrepancy_breakdown,
        'period_breakdown': period_breakdown,
    }
