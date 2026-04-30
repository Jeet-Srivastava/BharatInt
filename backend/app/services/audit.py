"""Audit/detail enrichment helpers shared by worker and review APIs."""

from __future__ import annotations

from datetime import date
from statistics import mean

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_HOURS_PER_SHIFT
from app.pipeline.anomaly import check_low_value_transfer
from app.pipeline.rates import calculate_expected_paise, resolve_rate
from app.pipeline.reconcile import compute_confidence_score


async def fetch_worker_record(session: AsyncSession, worker_id: str):
    """Fetch a canonical worker row for a worker_id."""
    result = await session.execute(
        text("""
            SELECT worker_id, name, phone, state, role, seniority, registered_on
            FROM workers
            WHERE worker_id = :worker_id
        """),
        {"worker_id": worker_id},
    )
    return result.fetchone()


async def get_latest_completed_run_id(session: AsyncSession):
    """Return the most recent completed pipeline run id."""
    result = await session.execute(
        text("""
            SELECT run_id
            FROM pipeline_runs
            WHERE status = 'completed'
            ORDER BY started_at DESC
            LIMIT 1
        """)
    )
    return result.scalar()


async def build_rate_context(session: AsyncSession, worker_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build worker/rate dataframes compatible with the pipeline rate resolver."""
    worker = await fetch_worker_record(session, worker_id)
    if not worker:
        return pd.DataFrame(), pd.DataFrame()

    workers_df = pd.DataFrame(
        [
            {
                "worker_id": worker.worker_id,
                "name": worker.name,
                "phone": worker.phone,
                "state": worker.state,
                "role": worker.role,
                "seniority": worker.seniority,
                "registered_on": worker.registered_on,
            }
        ]
    )

    rates_result = await session.execute(
        text("""
            SELECT id, role, state, seniority, effective_from, effective_to, hourly_rate_paise
            FROM wage_rates
            WHERE role = :role
              AND state = :state
              AND seniority = :seniority
            ORDER BY effective_from
        """),
        {
            "role": worker.role,
            "state": worker.state,
            "seniority": worker.seniority,
        },
    )

    rate_rows = [
        {
            "id": row.id,
            "role": row.role,
            "state": row.state,
            "seniority": row.seniority,
            "effective_from": row.effective_from,
            "effective_to": row.effective_to,
            "effective_to_filled": row.effective_to or date(9999, 12, 31),
            "hourly_rate_paise": row.hourly_rate_paise,
        }
        for row in rates_result.fetchall()
    ]

    if not rate_rows:
        return workers_df, pd.DataFrame()

    rates_df = pd.DataFrame(rate_rows).set_index("id", drop=False)
    return workers_df, rates_df


async def build_shift_details(
    session: AsyncSession,
    worker_id: str,
    billing_period: str | None = None,
) -> list[dict]:
    """Return shifts enriched with rate resolution and expected paise."""
    workers_df, rates_df = await build_rate_context(session, worker_id)

    where_period = ""
    params: dict[str, str] = {"worker_id": worker_id}
    if billing_period:
        where_period = "AND billing_period = :billing_period"
        params["billing_period"] = billing_period

    result = await session.execute(
        text(f"""
            SELECT log_id, work_date, billing_period, hours, vendor_app, supervisor_id,
                   tz_corrected, hours_anomaly, identity_confidence,
                   raw_worker_name, raw_worker_phone
            FROM shift_logs
            WHERE worker_id = :worker_id
            {where_period}
            ORDER BY work_date DESC, log_id DESC
        """),
        params,
    )

    shifts: list[dict] = []
    for row in result.fetchall():
        hours = float(row.hours) if row.hours is not None else None
        rate_info = {"status": "WORKER_NOT_FOUND", "rate_paise": None, "rate_row_id": None}

        if not workers_df.empty and rates_df.empty and hours is not None and hours <= MAX_HOURS_PER_SHIFT:
            rate_info = {"status": "NO_RATE_FOUND", "rate_paise": None, "rate_row_id": None}
        elif not workers_df.empty and not rates_df.empty and hours is not None and hours <= MAX_HOURS_PER_SHIFT:
            rate_info = resolve_rate(worker_id, row.work_date, workers_df, rates_df)
        elif hours is not None and hours > MAX_HOURS_PER_SHIFT:
            rate_info = {"status": "IMPOSSIBLE_HOURS", "rate_paise": None, "rate_row_id": None}

        expected_paise = None
        if rate_info["status"] == "OK" and hours is not None:
            expected_paise = calculate_expected_paise(hours, int(rate_info["rate_paise"]))

        shifts.append(
            {
                "log_id": row.log_id,
                "work_date": row.work_date.isoformat() if row.work_date else None,
                "hours": hours,
                "vendor_app": row.vendor_app,
                "supervisor_id": row.supervisor_id,
                "tz_corrected": row.tz_corrected,
                "hours_anomaly": row.hours_anomaly,
                "identity_confidence": float(row.identity_confidence) if row.identity_confidence is not None else None,
                "raw_worker_name": row.raw_worker_name,
                "raw_worker_phone": row.raw_worker_phone,
                "rate_paise": int(rate_info["rate_paise"]) if rate_info.get("rate_paise") is not None else None,
                "rate_row_id": rate_info.get("rate_row_id"),
                "rate_status": rate_info["status"],
                "expected_paise": expected_paise,
            }
        )

    return shifts


async def build_transfer_details(
    session: AsyncSession,
    worker_id: str,
    billing_period: str | None = None,
) -> list[dict]:
    """Return transfers enriched with low-value flags."""
    where_period = ""
    params: dict[str, str] = {"worker_id": worker_id}
    if billing_period:
        where_period = "AND billing_period = :billing_period"
        params["billing_period"] = billing_period

    result = await session.execute(
        text(f"""
            SELECT utr, amount_paise, transfer_date, billing_period,
                   precision_bug, account_last4
            FROM bank_transfers
            WHERE worker_id = :worker_id
            {where_period}
            ORDER BY transfer_date DESC, utr DESC
        """),
        params,
    )

    return [
        {
            "utr": row.utr,
            "amount_paise": row.amount_paise,
            "transfer_date": row.transfer_date.isoformat() if row.transfer_date else None,
            "billing_period": row.billing_period,
            "precision_bug": row.precision_bug,
            "account_last4": row.account_last4,
            "low_value": check_low_value_transfer(row.amount_paise),
        }
        for row in result.fetchall()
    ]


def summarise_identity_confidence(shifts: list[dict]) -> dict:
    """Summarise identity confidence across a worker's linked shifts."""
    values = [shift["identity_confidence"] for shift in shifts if shift["identity_confidence"] is not None]
    if not values:
        return {"average": None, "minimum": None}

    return {
        "average": round(mean(values), 3),
        "minimum": round(min(values), 3),
    }


def build_confidence_breakdown(shifts: list[dict]) -> dict:
    """Compute confidence score components using the reconciliation weighting."""
    values = [shift["identity_confidence"] for shift in shifts if shift["identity_confidence"] is not None]
    identity_score = min(values) if values else 0.5

    rate_status = "OK"
    for shift in shifts:
        if shift["rate_status"] == "AMBIGUOUS_RATE":
            rate_status = "AMBIGUOUS_RATE"
            break
        if shift["rate_status"] == "NO_RATE_FOUND":
            rate_status = "NO_RATE_FOUND"

    tz_corrected = any(shift["tz_corrected"] for shift in shifts)
    hours_anomaly = any(shift["hours_anomaly"] for shift in shifts)
    rate_score = 1.0 if rate_status == "OK" else 0.3
    timezone_score = 0.7 if tz_corrected else 1.0
    hours_score = 0.3 if hours_anomaly else 1.0
    overall = compute_confidence_score(identity_score, rate_status, tz_corrected, hours_anomaly)

    return {
        "overall": overall,
        "identity_score": round(identity_score, 3),
        "rate_score": rate_score,
        "timezone_score": timezone_score,
        "hours_score": hours_score,
        "rate_status": rate_status,
        "tz_corrected": tz_corrected,
        "hours_anomaly": hours_anomaly,
        "weights": {
            "identity": 0.4,
            "rate": 0.3,
            "timezone": 0.2,
            "hours": 0.1,
        },
        "weighted_components": {
            "identity": round(identity_score * 0.4, 3),
            "rate": round(rate_score * 0.3, 3),
            "timezone": round(timezone_score * 0.2, 3),
            "hours": round(hours_score * 0.1, 3),
        },
    }
