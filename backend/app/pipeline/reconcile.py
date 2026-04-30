"""Reconciliation engine — aggregate, classify, and flag discrepancies.

Reconciliation happens at the (worker_id, billing_period) level.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DiscrepancyType, Priority, ReviewStatus,
    NEAR_MATCH_THRESHOLD, LARGE_DISCREPANCY_THRESHOLD,
    MAX_HOURS_PER_SHIFT
)
from app.core.logging_utils import log_structured
from app.pipeline.rates import resolve_rate, calculate_expected_paise

logger = logging.getLogger(__name__)


# ── Aggregation ──────────────────────────────────────────────

def format_rupees_from_paise(paise: int) -> str:
    """Render a paise integer as a whole-rupee string using Decimal rounding."""
    rupees = (Decimal(str(abs(paise))) / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return str(int(rupees))

async def aggregate_expected(worker_id: str, billing_period: str, workers_df, rates_df, session: AsyncSession) -> int:
    """SUM expected_paise for all non-anomalous shifts for a worker in a period."""
    result = await session.execute(
        text("""
            SELECT log_id, work_date, hours, hours_anomaly, vendor_app
            FROM shift_logs
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
              AND hours_anomaly = FALSE
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    rows = result.fetchall()

    total_expected = 0
    for row in rows:
        rate_info = resolve_rate(worker_id, row.work_date, workers_df, rates_df)
        log_structured(
            logger,
            'rate_resolution',
            log_id=row.log_id,
            worker_id=worker_id,
            work_date=row.work_date,
            rate_row_id=rate_info.get('rate_row_id'),
            rate_paise=rate_info.get('rate_paise'),
            status=rate_info['status'],
        )
        if rate_info['status'] == 'OK' and rate_info['rate_paise'] is not None:
            expected = calculate_expected_paise(row.hours, rate_info['rate_paise'])
            total_expected += expected

    return total_expected


async def aggregate_actual(worker_id: str, billing_period: str, session: AsyncSession) -> int:
    """SUM amount_paise for all transfers for a worker in a period."""
    result = await session.execute(
        text("""
            SELECT COALESCE(SUM(amount_paise), 0) as total
            FROM bank_transfers
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    return int(result.scalar())


# ── Classification ───────────────────────────────────────────

def classify_discrepancy(expected: int, actual: int) -> DiscrepancyType:
    """Classify the discrepancy type based on expected vs actual paise."""
    if expected == 0 and actual == 0:
        return DiscrepancyType.EXACT_MATCH
    if expected > 0 and actual == 0:
        return DiscrepancyType.UNMATCHED_WORK
    if expected == 0 and actual > 0:
        return DiscrepancyType.UNMATCHED_PAYMENT

    delta = actual - expected

    if delta == 0:
        return DiscrepancyType.EXACT_MATCH

    if expected > 0 and abs(delta) / expected < NEAR_MATCH_THRESHOLD:
        return DiscrepancyType.NEAR_MATCH

    if delta < 0:
        return DiscrepancyType.UNDERPAYMENT

    return DiscrepancyType.OVERPAYMENT


async def detect_duplicate_payment(worker_id: str, billing_period: str, session: AsyncSession) -> bool:
    """Check if same worker has 2+ UTRs with identical amounts in same period."""
    result = await session.execute(
        text("""
            SELECT amount_paise, COUNT(*) as cnt
            FROM bank_transfers
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
            GROUP BY amount_paise
            HAVING COUNT(*) >= 2
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    return result.fetchone() is not None


# ── Review Flags ─────────────────────────────────────────────

async def build_review_reasons(
    worker_id: str,
    billing_period: str,
    discrepancy_type: DiscrepancyType,
    delta: int,
    expected: int,
    workers_df,
    rates_df,
    session: AsyncSession
) -> list[str]:
    """Collect all triggered review reasons as a list."""
    reasons = []

    # Discrepancy-based reasons
    if discrepancy_type == DiscrepancyType.UNDERPAYMENT and delta != 0:
        reasons.append(f"UNDERPAYMENT:₹{format_rupees_from_paise(delta)} short")
    elif discrepancy_type == DiscrepancyType.OVERPAYMENT and delta != 0:
        reasons.append(f"OVERPAYMENT:₹{format_rupees_from_paise(delta)} excess")
    elif discrepancy_type == DiscrepancyType.UNMATCHED_WORK:
        reasons.append("UNMATCHED_WORK:shifts with no payment")
    elif discrepancy_type == DiscrepancyType.UNMATCHED_PAYMENT:
        reasons.append("UNMATCHED_PAYMENT:payment with no shifts")

    # Check shift-level flags
    shifts = await session.execute(
        text("""
            SELECT log_id, hours_anomaly, tz_corrected, identity_confidence,
                   vendor_app, work_date, hours
            FROM shift_logs
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    shift_rows = shifts.fetchall()

    has_tz_corrected = False
    has_hours_anomaly = False
    has_low_confidence = False
    has_vendor_b = False

    for s in shift_rows:
        if s.tz_corrected:
            has_tz_corrected = True
        if s.hours_anomaly:
            has_hours_anomaly = True
        if s.identity_confidence is not None and float(s.identity_confidence) < 0.7:
            has_low_confidence = True
        if s.vendor_app and 'vendor_b' in s.vendor_app.lower():
            has_vendor_b = True

        # Check rate status for each shift
        rate_info = resolve_rate(worker_id, s.work_date, workers_df, rates_df)
        if rate_info['status'] == 'AMBIGUOUS_RATE':
            reasons.append(f"AMBIGUOUS_RATE:{workers_df[workers_df['worker_id']==worker_id].iloc[0]['role']} {s.work_date}")

    if has_tz_corrected:
        reasons.append("TIMEZONE_CORRECTED:vendor_b")
    if has_hours_anomaly:
        reasons.append("IMPOSSIBLE_HOURS:excluded from calculation")
    if has_low_confidence:
        reasons.append("LOW_CONFIDENCE:identity confidence < 0.7")
    if has_vendor_b:
        reasons.append("VENDOR_B_ANOMALY:vendor_b integration")

    # Check large discrepancy
    if expected > 0 and abs(delta) / expected > LARGE_DISCREPANCY_THRESHOLD:
        reasons.append(f"LARGE_DISCREPANCY:{abs(delta)/expected*100:.1f}% deviation")

    # Check for duplicate payments
    if await detect_duplicate_payment(worker_id, billing_period, session):
        reasons.append("DUPLICATE_PAYMENT_CANDIDATE:identical amounts in period")

    # Check for precision bugs in transfers
    precision_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM bank_transfers
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
              AND precision_bug = TRUE
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    if precision_result.scalar() > 0:
        reasons.append("PRECISION_BUG:sub-rupee paise in transfer")

    # Check for low-value transfers
    low_val_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM bank_transfers
            WHERE worker_id = :worker_id
              AND billing_period = :billing_period
              AND amount_paise < 50000
        """),
        {'worker_id': worker_id, 'billing_period': billing_period}
    )
    if low_val_result.scalar() > 0:
        reasons.append("LOW_VALUE_TRANSFER:amount below ₹500")

    return reasons


def assign_priority(discrepancy_type: DiscrepancyType, delta: int, rate_status: str = None) -> Priority:
    """Assign priority level based on business rules."""
    if discrepancy_type in (DiscrepancyType.UNMATCHED_WORK, DiscrepancyType.UNMATCHED_PAYMENT):
        return Priority.P0

    if abs(delta) > 100000:  # > ₹1,000
        return Priority.P1

    if rate_status == 'AMBIGUOUS_RATE' and discrepancy_type not in (DiscrepancyType.EXACT_MATCH,):
        return Priority.P2

    return Priority.P3


def compute_confidence_score(identity_conf: float, rate_status: str,
                             tz_corrected: bool, hours_anomaly: bool) -> float:
    """Compute weighted confidence score.

    0.4×identity + 0.3×rate + 0.2×timezone + 0.1×hours
    """
    rate_score = 1.0 if rate_status == 'OK' else 0.3
    tz_score = 0.7 if tz_corrected else 1.0
    hours_score = 0.3 if hours_anomaly else 1.0

    score = (0.4 * identity_conf) + (0.3 * rate_score) + (0.2 * tz_score) + (0.1 * hours_score)
    return round(score, 3)


def set_manual_review_flag(
    confidence_score: float,
    discrepancy_type: DiscrepancyType,
    rate_status: str,
    hours_anomaly: bool,
    phone_status: str,
    tz_corrected: bool,
    delta_ratio: float
) -> bool:
    """Determine if manual review is needed based on rules in prompt."""
    if confidence_score < 0.7:
        return True
    if rate_status == 'AMBIGUOUS_RATE':
        return True
    if discrepancy_type in (
        DiscrepancyType.UNDERPAYMENT, DiscrepancyType.OVERPAYMENT,
        DiscrepancyType.UNMATCHED_WORK, DiscrepancyType.UNMATCHED_PAYMENT,
        DiscrepancyType.DUPLICATE_PAYMENT
    ):
        return True
    if hours_anomaly:
        return True
    if phone_status == 'UNRESOLVABLE_PHONE':
        return True
    if tz_corrected:
        return True
    if delta_ratio > LARGE_DISCREPANCY_THRESHOLD:
        return True
    return False


# ── Full Reconciliation Runner ───────────────────────────────

async def run_reconciliation(pipeline_run_id: str, workers_df, rates_df, session: AsyncSession) -> dict:
    """Run full reconciliation for all (worker_id, billing_period) combinations.

    Returns reconciliation stats for the pipeline run.
    """
    started = perf_counter()
    # Get all (worker_id, billing_period) combinations from shift_logs UNION bank_transfers
    result = await session.execute(
        text("""
            SELECT DISTINCT worker_id, billing_period
            FROM shift_logs
            WHERE worker_id IS NOT NULL
            UNION
            SELECT DISTINCT worker_id, billing_period
            FROM bank_transfers
            WHERE worker_id IS NOT NULL
        """)
    )
    combinations = result.fetchall()

    anomalies_count = 0

    for combo in combinations:
        worker_id = combo.worker_id
        billing_period = combo.billing_period

        # Aggregate expected and actual
        expected = await aggregate_expected(worker_id, billing_period, workers_df, rates_df, session)
        actual = await aggregate_actual(worker_id, billing_period, session)
        delta = actual - expected

        # Classify discrepancy
        disc_type = classify_discrepancy(expected, actual)

        # Check for duplicate payments
        is_duplicate = await detect_duplicate_payment(worker_id, billing_period, session)
        if is_duplicate and disc_type != DiscrepancyType.EXACT_MATCH:
            disc_type = DiscrepancyType.DUPLICATE_PAYMENT

        # Build review reasons
        reasons = await build_review_reasons(
            worker_id, billing_period, disc_type, delta, expected,
            workers_df, rates_df, session
        )

        # Get shift-level metadata for confidence computation
        shift_meta = await session.execute(
            text("""
                SELECT MIN(identity_confidence) as min_confidence,
                       BOOL_OR(tz_corrected) as any_tz_corrected,
                       BOOL_OR(hours_anomaly) as any_hours_anomaly
                FROM shift_logs
                WHERE worker_id = :worker_id
                  AND billing_period = :billing_period
            """),
            {'worker_id': worker_id, 'billing_period': billing_period}
        )
        meta = shift_meta.fetchone()

        identity_conf = float(meta.min_confidence) if meta and meta.min_confidence else 0.5
        tz_corrected = bool(meta.any_tz_corrected) if meta else False
        hours_anomaly = bool(meta.any_hours_anomaly) if meta else False

        # Determine rate status
        rate_status = 'OK'
        if 'AMBIGUOUS_RATE' in ' '.join(reasons):
            rate_status = 'AMBIGUOUS_RATE'
        elif 'NO_RATE_FOUND' in ' '.join(reasons):
            rate_status = 'NO_RATE_FOUND'

        # Compute confidence score
        confidence = compute_confidence_score(identity_conf, rate_status, tz_corrected, hours_anomaly)

        # Determine priority
        priority = assign_priority(disc_type, delta, rate_status)

        # Delta ratio for review flag
        delta_ratio = abs(delta) / expected if expected > 0 else 0.0

        # Determine manual review flag
        needs_review = set_manual_review_flag(
            confidence, disc_type, rate_status, hours_anomaly,
            'OK', tz_corrected, delta_ratio
        )

        review_reason_str = ' | '.join(reasons) if reasons else None

        if needs_review:
            anomalies_count += 1

        # Upsert reconciliation row
        await session.execute(
            text("""
                INSERT INTO reconciliation
                    (id, worker_id, billing_period, expected_paise, actual_paise,
                     delta_paise, discrepancy_type, needs_manual_review,
                     review_reason, priority, confidence_score, resolved,
                     pipeline_run_id)
                VALUES
                    (gen_random_uuid(), :worker_id, :billing_period, :expected,
                     :actual, :delta, :disc_type, :needs_review,
                     :review_reason, :priority, :confidence, FALSE,
                     :pipeline_run_id)
                ON CONFLICT (worker_id, billing_period, pipeline_run_id) DO UPDATE SET
                    expected_paise = EXCLUDED.expected_paise,
                    actual_paise = EXCLUDED.actual_paise,
                    delta_paise = EXCLUDED.delta_paise,
                    discrepancy_type = EXCLUDED.discrepancy_type,
                    needs_manual_review = EXCLUDED.needs_manual_review,
                    review_reason = EXCLUDED.review_reason,
                    priority = EXCLUDED.priority,
                    confidence_score = EXCLUDED.confidence_score,
                    resolved = COALESCE(reconciliation.resolved, FALSE)
            """),
            {
                'worker_id': worker_id,
                'billing_period': billing_period,
                'expected': expected,
                'actual': actual,
                'delta': delta,
                'disc_type': disc_type.value,
                'needs_review': needs_review,
                'review_reason': review_reason_str,
                'priority': priority.value,
                'confidence': confidence,
                'pipeline_run_id': pipeline_run_id,
            }
        )

    await session.commit()
    log_structured(
        logger,
        'pipeline_step',
        step_name='run_reconciliation',
        rows_processed=len(combinations),
        errors_count=anomalies_count,
        duration_ms=round((perf_counter() - started) * 1000, 2),
    )
    return {'processed': len(combinations), 'anomalies': anomalies_count}
