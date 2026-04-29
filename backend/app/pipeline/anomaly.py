"""Anomaly detection module.

Handles BUG-06 (precision bug), BUG-09 (ghost payment/low value transfer).
"""

import numpy as np
from datetime import date, timedelta

from app.core.constants import LOW_VALUE_PAISE_THRESHOLD


def check_low_value_transfer(amount_paise: int) -> bool:
    """BUG-09: Flag transfers below ₹500 (50000 paise)."""
    return amount_paise < LOW_VALUE_PAISE_THRESHOLD


def check_late_entry(work_date: date, entered_at: date) -> bool:
    """Flag if entry was made more than 30 days after work_date."""
    if work_date is None or entered_at is None:
        return False
    return (entered_at - work_date) > timedelta(days=30)


def check_hours_zscore(hours_series, hours_value: float) -> bool:
    """Flag if hours z-score > 3 (after excluding impossible hours)."""
    if hours_series is None or len(hours_series) < 2:
        return False
    clean = [h for h in hours_series if h <= 16]
    if len(clean) < 2:
        return False
    mean = np.mean(clean)
    std = np.std(clean)
    if std == 0:
        return False
    z = abs((hours_value - mean) / std)
    return z > 3


def check_payment_zscore(payment_series, payment_value: int, cohort_key: str = None) -> bool:
    """Flag if payment z-score > 2 within cohort (role, state, seniority)."""
    if payment_series is None or len(payment_series) < 2:
        return False
    mean = np.mean(payment_series)
    std = np.std(payment_series)
    if std == 0:
        return False
    z = abs((payment_value - mean) / std)
    return z > 2


def check_precision_bug(amount_paise: int) -> bool:
    """BUG-06: Flag transfers with sub-rupee paise (not divisible by 100)."""
    return amount_paise % 100 != 0
