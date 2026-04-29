"""Rate resolution and wage calculation — always in paise, always Decimal.

Handles BUG-03 (overlapping rate windows) and BUG-04 (fractional rate 450.33).
"""

from decimal import Decimal, ROUND_HALF_UP
import pandas as pd


def resolve_rate(worker_id: str, work_date, workers_df, rates_df) -> dict:
    """Resolve the correct hourly rate for a worker on a given date.

    Overlap resolution: sort by effective_from DESC, effective_to ASC, take first.
    If still ambiguous → flag AMBIGUOUS_RATE.

    Returns dict with: rate_paise, rate_row_id, status
    """
    worker_match = workers_df[workers_df['worker_id'] == worker_id]
    if worker_match.empty:
        return {'rate_paise': None, 'status': 'WORKER_NOT_FOUND'}

    worker = worker_match.iloc[0]

    mask = (
        (rates_df['role'] == worker['role']) &
        (rates_df['state'] == worker['state']) &
        (rates_df['seniority'] == worker['seniority']) &
        (rates_df['effective_from'] <= work_date) &
        (rates_df['effective_to_filled'] >= work_date)
    )
    matches = rates_df[mask].copy()

    if matches.empty:
        return {'rate_paise': None, 'status': 'NO_RATE_FOUND'}

    if len(matches) > 1:
        # Overlap resolution: prefer open-ended (canonical) rates over narrow windows.
        # Sort by: effective_to_filled DESC (open-ended/9999 first), then effective_from DESC (most recent first).
        # This ensures the canonical current rate wins over superseded narrow windows.
        matches = matches.sort_values(
            ['effective_to_filled', 'effective_from'],
            ascending=[False, False]
        )
        # After sort, check if top 2 are truly ambiguous (same dates)
        if len(matches) >= 2:
            top = matches.iloc[0]
            second = matches.iloc[1]
            if (top['effective_from'] == second['effective_from'] and
                    top['effective_to_filled'] == second['effective_to_filled']):
                return {
                    'rate_paise': None,
                    'status': 'AMBIGUOUS_RATE',
                    'candidates': len(matches)
                }

    rate_row = matches.iloc[0]
    return {
        'rate_paise': int(Decimal(str(rate_row['hourly_rate_paise']))),
        'rate_row_id': int(rate_row.name) if hasattr(rate_row, 'name') else None,
        'status': 'OK'
    }


def calculate_expected_paise(hours, rate_paise: int) -> int:
    """Calculate expected wage in paise using Decimal arithmetic.

    NEVER use float. Always Decimal with ROUND_HALF_UP.
    Example: 450.33 INR/h = 45033 paise/h × 7.5h = 337747.5 → 337748 paise
    """
    result = Decimal(str(rate_paise)) * Decimal(str(hours))
    return int(result.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
