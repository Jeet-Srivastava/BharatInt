"""Data ingest module — CSV loading, normalisation, and DB upsert.

Handles loading all 4 CSVs, processing supervisor logs and bank transfers,
and upserting into the database.
"""

import logging
from decimal import Decimal
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BILLING_PERIOD_FORMAT, DATA_DIR
from app.core.constants import MAX_HOURS_PER_SHIFT
from app.pipeline.normalise import normalise_phone, derive_work_date, normalise_timestamp, validate_hours
from app.pipeline.identity import resolve_identity
from app.pipeline.rates import resolve_rate, calculate_expected_paise
from app.pipeline.anomaly import check_precision_bug, check_low_value_transfer

logger = logging.getLogger(__name__)


# ── CSV Loaders ──────────────────────────────────────────────

def validate_csv_schema(df: pd.DataFrame, dataset_name: str, expected_columns: tuple[str, ...]) -> None:
    """Validate that a CSV has the exact expected columns."""
    actual_columns = tuple(df.columns)
    missing = [column for column in expected_columns if column not in actual_columns]
    extra = [column for column in actual_columns if column not in expected_columns]

    if missing or extra:
        raise ValueError(
            f"{dataset_name} schema mismatch. Missing={missing or '[]'} Extra={extra or '[]'}"
        )


def read_validated_csv(path: str, dataset_name: str, expected_columns: tuple[str, ...]) -> pd.DataFrame:
    """Load and validate a CSV before any downstream parsing."""
    df = pd.read_csv(path)
    validate_csv_schema(df, dataset_name, expected_columns)
    return df

def load_workers(path: str = None) -> pd.DataFrame:
    """Load workers.csv — canonical worker registry."""
    path = path or f"{DATA_DIR}/workers.csv"
    expected_cols = ('worker_id', 'name', 'phone', 'state', 'role', 'seniority', 'registered_on')
    df = read_validated_csv(path, 'workers.csv', expected_cols)
    # Ensure phone is 10-digit string
    df['phone'] = df['phone'].astype(str).str.strip()
    return df


def load_wage_rates(path: str = None) -> pd.DataFrame:
    """Load wage_rates.csv — convert hourly_rate_inr to hourly_rate_paise using Decimal."""
    path = path or f"{DATA_DIR}/wage_rates.csv"
    expected_cols = ('role', 'state', 'effective_from', 'effective_to', 'hourly_rate_inr', 'seniority')
    df = read_validated_csv(path, 'wage_rates.csv', expected_cols)

    # Convert dates
    df['effective_from'] = pd.to_datetime(df['effective_from']).dt.date
    df['effective_to_raw'] = pd.to_datetime(df['effective_to'], errors='coerce')

    # Fill NaT effective_to with 9999-12-31 using apply to avoid pandas type coercion issues
    df['effective_to_filled'] = df['effective_to_raw'].apply(
        lambda x: x.date() if pd.notna(x) else date(9999, 12, 31)
    )
    df['effective_to'] = df['effective_to_raw'].apply(
        lambda x: x.date() if pd.notna(x) else None
    )
    df.drop(columns=['effective_to_raw'], inplace=True)

    # Convert INR to paise using Decimal (BUG-04)
    df['hourly_rate_paise'] = df['hourly_rate_inr'].apply(
        lambda r: int(Decimal(str(r)) * 100)
    )

    return df


def load_supervisor_logs(path: str = None) -> pd.DataFrame:
    """Load supervisor_logs.csv — raw DataFrame (normalisation happens later)."""
    path = path or f"{DATA_DIR}/supervisor_logs.csv"
    expected_cols = (
        'log_id', 'worker_name', 'worker_phone', 'supervisor_id',
        'work_date', 'hours', 'vendor_app', 'entered_at',
    )
    return read_validated_csv(path, 'supervisor_logs.csv', expected_cols)


def load_bank_transfers(path: str = None) -> pd.DataFrame:
    """Load bank_transfers.csv — raw DataFrame."""
    path = path or f"{DATA_DIR}/bank_transfers.csv"
    expected_cols = (
        'utr', 'worker_phone', 'worker_name', 'amount_paise',
        'transfer_timestamp', 'account_last4',
    )
    return read_validated_csv(path, 'bank_transfers.csv', expected_cols)


# ── DB Upserters ─────────────────────────────────────────────

async def ingest_workers_to_db(workers_df: pd.DataFrame, session: AsyncSession):
    """Upsert all workers to DB using worker_id as conflict key."""
    for _, row in workers_df.iterrows():
        await session.execute(
            text("""
                INSERT INTO workers (worker_id, name, phone, state, role, seniority, registered_on)
                VALUES (:worker_id, :name, :phone, :state, :role, :seniority, :registered_on)
                ON CONFLICT (worker_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    state = EXCLUDED.state,
                    role = EXCLUDED.role,
                    seniority = EXCLUDED.seniority,
                    registered_on = EXCLUDED.registered_on
            """),
            {
                'worker_id': str(row['worker_id']),
                'name': str(row['name']),
                'phone': str(row['phone']),
                'state': str(row['state']),
                'role': str(row['role']),
                'seniority': str(row['seniority']),
                'registered_on': pd.to_datetime(row['registered_on']).date(),
            }
        )
    await session.commit()
    logger.info(f"Upserted {len(workers_df)} workers")


async def ingest_wage_rates_to_db(rates_df: pd.DataFrame, session: AsyncSession):
    """Upsert all wage rates to DB."""
    # Clear and re-insert (small table)
    await session.execute(text("DELETE FROM wage_rates"))
    for _, row in rates_df.iterrows():
        await session.execute(
            text("""
                INSERT INTO wage_rates (role, state, seniority, effective_from, effective_to, hourly_rate_paise)
                VALUES (:role, :state, :seniority, :effective_from, :effective_to, :hourly_rate_paise)
            """),
            {
                'role': str(row['role']),
                'state': str(row['state']),
                'seniority': str(row['seniority']),
                'effective_from': row['effective_from'],
                'effective_to': row['effective_to'],
                'hourly_rate_paise': int(row['hourly_rate_paise']),
            }
        )
    await session.commit()
    logger.info(f"Inserted {len(rates_df)} wage rates")


async def process_supervisor_logs(
    logs_df: pd.DataFrame,
    workers_df: pd.DataFrame,
    rates_df: pd.DataFrame,
    pipeline_run_id: str,
    session: AsyncSession
) -> dict:
    """Process supervisor logs: normalise → resolve identity → validate hours → upsert.

    Returns stats dict with counts.
    """
    stats = {
        'total': len(logs_df),
        'processed': 0,
        'anomalies': 0,
        'unresolvable_phone': 0,
        'tz_corrected': 0,
        'impossible_hours': 0,
        'vendor_b_count': 0,
    }

    for _, row in logs_df.iterrows():
        log_id = str(row['log_id'])
        raw_phone = str(row['worker_phone'])
        raw_name = str(row['worker_name'])
        vendor_app = str(row['vendor_app'])
        raw_hours = float(row['hours'])
        raw_work_date = str(row['work_date'])
        raw_entered_at = str(row['entered_at'])

        # 1. Identity resolution (phone normalisation + fuzzy name match)
        identity = resolve_identity(raw_phone, raw_name, workers_df)
        worker_id = identity['worker_id']
        identity_confidence = identity['confidence']

        # 2. Timezone normalisation + work_date derivation
        corrected_work_date, tz_corrected = derive_work_date(raw_entered_at, raw_work_date, vendor_app)
        entered_at_ist, _ = normalise_timestamp(raw_entered_at, vendor_app)
        billing_period = corrected_work_date.strftime(BILLING_PERIOD_FORMAT)

        # 3. Hours validation
        validated_hours, hours_anomaly, hours_reason = validate_hours(raw_hours, log_id)

        # If impossible hours, exclude from calculation (set worker_id effect later in recon)
        if hours_reason == 'IMPOSSIBLE_HOURS':
            stats['impossible_hours'] += 1
            stats['anomalies'] += 1

        if tz_corrected:
            stats['tz_corrected'] += 1

        if 'vendor_b' in vendor_app.lower():
            stats['vendor_b_count'] += 1

        if identity['status'] == 'UNRESOLVABLE_PHONE':
            stats['unresolvable_phone'] += 1

        if hours_anomaly:
            stats['anomalies'] += 1

        # 4. Upsert to shift_logs
        await session.execute(
            text("""
                INSERT INTO shift_logs
                    (log_id, worker_id, raw_worker_name, raw_worker_phone,
                     supervisor_id, work_date, billing_period, hours, vendor_app,
                     entered_at_utc, tz_corrected, identity_confidence,
                     hours_anomaly, pipeline_run_id)
                VALUES
                    (:log_id, :worker_id, :raw_name, :raw_phone,
                     :supervisor_id, :work_date, :billing_period, :hours, :vendor_app,
                     :entered_at, :tz_corrected, :confidence,
                     :hours_anomaly, :pipeline_run_id)
                ON CONFLICT (log_id) DO UPDATE SET
                    worker_id = EXCLUDED.worker_id,
                    raw_worker_name = EXCLUDED.raw_worker_name,
                    raw_worker_phone = EXCLUDED.raw_worker_phone,
                    supervisor_id = EXCLUDED.supervisor_id,
                    work_date = EXCLUDED.work_date,
                    billing_period = EXCLUDED.billing_period,
                    hours = EXCLUDED.hours,
                    vendor_app = EXCLUDED.vendor_app,
                    entered_at_utc = EXCLUDED.entered_at_utc,
                    tz_corrected = EXCLUDED.tz_corrected,
                    identity_confidence = EXCLUDED.identity_confidence,
                    hours_anomaly = EXCLUDED.hours_anomaly,
                    pipeline_run_id = EXCLUDED.pipeline_run_id
            """),
            {
                'log_id': log_id,
                'worker_id': worker_id,
                'raw_name': raw_name,
                'raw_phone': raw_phone,
                'supervisor_id': str(row['supervisor_id']),
                'work_date': corrected_work_date,
                'billing_period': billing_period,
                'hours': raw_hours,  # store original hours, use hours_anomaly flag
                'vendor_app': vendor_app,
                'entered_at': entered_at_ist,
                'tz_corrected': tz_corrected,
                'confidence': identity_confidence,
                'hours_anomaly': hours_anomaly,
                'pipeline_run_id': pipeline_run_id,
            }
        )
        stats['processed'] += 1

    await session.commit()
    logger.info(f"Processed {stats['processed']} supervisor logs. Anomalies: {stats['anomalies']}")
    return stats


async def process_bank_transfers(
    transfers_df: pd.DataFrame,
    workers_df: pd.DataFrame,
    pipeline_run_id: str,
    session: AsyncSession
) -> dict:
    """Process bank transfers: normalise phone → lookup worker → derive billing_period → upsert.

    Returns stats dict.
    """
    stats = {
        'total': len(transfers_df),
        'processed': 0,
        'precision_bugs': 0,
        'low_value': 0,
        'unresolvable_phone': 0,
    }

    for _, row in transfers_df.iterrows():
        utr = str(row['utr'])
        raw_phone = str(row['worker_phone'])
        raw_name = str(row['worker_name'])
        amount_paise = int(row['amount_paise'])
        raw_timestamp = str(row['transfer_timestamp'])
        account_last4 = str(row['account_last4']) if pd.notna(row.get('account_last4')) else None

        # 1. Phone normalisation → worker lookup
        norm_phone, phone_status = normalise_phone(raw_phone) if not raw_phone.isdigit() or len(raw_phone) != 10 else (raw_phone, 'OK')

        # If phone is already clean 10-digit (bank transfers usually are)
        if phone_status != 'OK':
            norm_phone, phone_status = normalise_phone(raw_phone)

        worker_id = None
        if norm_phone:
            match = workers_df[workers_df['phone'] == norm_phone]
            if not match.empty:
                worker_id = match.iloc[0]['worker_id']

        if phone_status != 'OK':
            stats['unresolvable_phone'] += 1

        # 2. Derive billing_period from transfer_timestamp
        transfer_dt = pd.to_datetime(raw_timestamp)
        transfer_date = transfer_dt.date()
        billing_period = transfer_dt.strftime(BILLING_PERIOD_FORMAT)

        # 3. Precision bug detection (BUG-06)
        precision_bug = check_precision_bug(amount_paise)
        if precision_bug:
            stats['precision_bugs'] += 1

        # 4. Low value detection (BUG-09)
        if check_low_value_transfer(amount_paise):
            stats['low_value'] += 1

        # 5. Upsert to bank_transfers
        await session.execute(
            text("""
                INSERT INTO bank_transfers
                    (utr, worker_id, raw_worker_name, raw_worker_phone,
                     amount_paise, transfer_date, billing_period,
                     account_last4, precision_bug, pipeline_run_id)
                VALUES
                    (:utr, :worker_id, :raw_name, :raw_phone,
                     :amount_paise, :transfer_date, :billing_period,
                     :account_last4, :precision_bug, :pipeline_run_id)
                ON CONFLICT (utr) DO UPDATE SET
                    worker_id = EXCLUDED.worker_id,
                    raw_worker_name = EXCLUDED.raw_worker_name,
                    raw_worker_phone = EXCLUDED.raw_worker_phone,
                    amount_paise = EXCLUDED.amount_paise,
                    transfer_date = EXCLUDED.transfer_date,
                    billing_period = EXCLUDED.billing_period,
                    account_last4 = EXCLUDED.account_last4,
                    precision_bug = EXCLUDED.precision_bug,
                    pipeline_run_id = EXCLUDED.pipeline_run_id
            """),
            {
                'utr': utr,
                'worker_id': worker_id,
                'raw_name': raw_name,
                'raw_phone': raw_phone,
                'amount_paise': amount_paise,
                'transfer_date': transfer_date,
                'billing_period': billing_period,
                'account_last4': account_last4,
                'precision_bug': precision_bug,
                'pipeline_run_id': pipeline_run_id,
            }
        )
        stats['processed'] += 1

    await session.commit()
    logger.info(f"Processed {stats['processed']} bank transfers. Precision bugs: {stats['precision_bugs']}")
    return stats
