"""Normalisation module — phone, timestamp, and hours validation.

Handles BUG-01 (impossible hours), BUG-02 (vendor_b timezone), BUG-05 (phone formats).
"""

import re
from datetime import datetime, date
import pandas as pd
from zoneinfo import ZoneInfo

from app.core.constants import MAX_HOURS_PER_SHIFT

IST = ZoneInfo("Asia/Kolkata")


# ── Phone normalisation (BUG-05) ──────────────────────────────
def normalise_phone(raw: str) -> tuple[str | None, str]:
    """Normalise raw phone to 10-digit Indian mobile number.

    Returns (normalised_10_digit, status).
    Handles 6 formats: +91 XXXXXXXXXX, 91-XXXXXXXXXX, 91XXXXXXXXXX,
                        XXXXX XXXXX, 0 XXXXXXXXXX, XXXXXXXXXX
    """
    digits = re.sub(r'\D', '', str(raw).strip())

    # Strip country code prefix
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]

    # Validate: 10 digits, starts with 6/7/8/9
    if len(digits) == 10 and digits[0] in '6789':
        return digits, 'OK'

    return None, 'UNRESOLVABLE_PHONE'


# ── Timestamp normalisation (BUG-02) ──────────────────────────
def normalise_timestamp(raw_ts: str, vendor_app: str) -> tuple[datetime, bool]:
    """Convert raw timestamp to IST datetime.

    For vendor_b_v1.0: timestamps are UTC (+00:00), must convert to IST.
    For vendor_a_v2.3: timestamps are already IST (+05:30).

    Returns (ist_datetime, tz_corrected).
    """
    dt = pd.to_datetime(raw_ts, utc=True)
    ist_dt = dt.astimezone(IST)

    tz_corrected = 'vendor_b' in str(vendor_app).lower()

    return ist_dt, tz_corrected


def derive_work_date(raw_ts: str, raw_work_date: str, vendor_app: str) -> tuple[date, bool]:
    """Derive the correct work_date from timestamp.

    For vendor_b: re-derive from IST timestamp (the raw work_date is wrong).
    For vendor_a: use raw work_date as-is.

    Returns (corrected_work_date, tz_corrected).
    """
    if 'vendor_b' in str(vendor_app).lower():
        ist_dt, tz_corrected = normalise_timestamp(raw_ts, vendor_app)
        return ist_dt.date(), True
    else:
        return pd.to_datetime(raw_work_date).date(), False


# ── Hours validation (BUG-01) ─────────────────────────────────
def validate_hours(hours: float, log_id: str) -> tuple[float | None, bool, str]:
    """Validate shift hours against business rules.

    Returns (hours_or_none, is_anomaly, reason).
    - hours > MAX_HOURS_PER_SHIFT (16): excluded from calculation (IMPOSSIBLE_HOURS)
    - hours > 14 but <= 16: flagged but included (HIGH_HOURS)
    - otherwise: normal
    """
    if hours > MAX_HOURS_PER_SHIFT:
        return None, True, 'IMPOSSIBLE_HOURS'
    elif hours > 14:
        return hours, True, 'HIGH_HOURS'
    else:
        return hours, False, ''
