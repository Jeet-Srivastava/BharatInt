"""Unit tests for the pipeline modules."""

import pytest
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
import pandas as pd

# ── Tests for normalise.py ────────────────────────────────────


class TestNormalisePhone:
    """Test all 6 phone formats (BUG-05)."""

    def test_format_plus91(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('+91 9627028951')
        assert status == 'OK'
        assert result == '9627028951'

    def test_format_91_dash(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('91-9139005329')
        assert status == 'OK'
        assert result == '9139005329'

    def test_format_91_no_sep(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('919299737631')
        assert status == 'OK'
        assert result == '9299737631'

    def test_format_space_split(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('97010 65133')
        assert status == 'OK'
        assert result == '9701065133'

    def test_format_zero_prefix(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('0 9413435240')
        assert status == 'OK'
        assert result == '9413435240'

    def test_format_plain_10(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('9901476797')
        assert status == 'OK'
        assert result == '9901476797'

    def test_unresolvable(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('12345')
        assert status == 'UNRESOLVABLE_PHONE'
        assert result is None

    def test_unresolvable_starts_with_1(self):
        from app.pipeline.normalise import normalise_phone
        result, status = normalise_phone('1234567890')
        assert status == 'UNRESOLVABLE_PHONE'
        assert result is None


class TestTimezoneCorrection:
    """Test vendor_b UTC → IST conversion (BUG-02)."""

    def test_vendor_b_next_day(self):
        """vendor_b 22:30:00+00:00 on 2025-03-14 → IST date = 2025-03-15."""
        from app.pipeline.normalise import derive_work_date
        corrected_date, tz_corrected = derive_work_date(
            '2025-03-14T22:30:00+00:00', '2025-03-14', 'vendor_b_v1.0'
        )
        assert tz_corrected is True
        assert corrected_date == date(2025, 3, 15)  # next day in IST

    def test_vendor_a_no_correction(self):
        """vendor_a timestamps are already IST, no correction needed."""
        from app.pipeline.normalise import derive_work_date
        corrected_date, tz_corrected = derive_work_date(
            '2025-03-15T19:30:00+05:30', '2025-03-15', 'vendor_a_v2.3'
        )
        assert tz_corrected is False
        assert corrected_date == date(2025, 3, 15)


class TestHoursValidation:
    """Test hours validation (BUG-01)."""

    def test_impossible_hours(self):
        """450h → excluded from calculation."""
        from app.pipeline.normalise import validate_hours
        hours, anomaly, reason = validate_hours(450.0, 'L02617')
        assert hours is None
        assert anomaly is True
        assert reason == 'IMPOSSIBLE_HOURS'

    def test_high_hours(self):
        """15h → flagged but included."""
        from app.pipeline.normalise import validate_hours
        hours, anomaly, reason = validate_hours(15.0, 'L00001')
        assert hours == 15.0
        assert anomaly is True
        assert reason == 'HIGH_HOURS'

    def test_normal_hours(self):
        """8h → normal."""
        from app.pipeline.normalise import validate_hours
        hours, anomaly, reason = validate_hours(8.0, 'L00002')
        assert hours == 8.0
        assert anomaly is False
        assert reason == ''


# ── Tests for identity.py ─────────────────────────────────────

class TestIdentityResolution:
    """Test identity resolution (BUG-07)."""

    @pytest.fixture
    def workers_df(self):
        return pd.DataFrame([
            {'worker_id': 'W0001', 'name': 'Ramesh Kumar', 'phone': '9901476797',
             'state': 'MH', 'role': 'Data Entry', 'seniority': 'junior'},
            {'worker_id': 'W0002', 'name': 'Ramesh Kumar', 'phone': '9104332181',
             'state': 'MH', 'role': 'Data Entry', 'seniority': 'junior'},
        ])

    def test_clean_match(self, workers_df):
        from app.pipeline.identity import resolve_identity
        result = resolve_identity('+91 9901476797', 'Ramesh Kumar', workers_df)
        assert result['worker_id'] == 'W0001'
        assert result['confidence'] == 0.95

    def test_surname_first(self, workers_df):
        from app.pipeline.identity import resolve_identity
        result = resolve_identity('+91 9901476797', 'Kumar Ramesh', workers_df)
        assert result['worker_id'] == 'W0001'
        assert result['confidence'] >= 0.70

    def test_initial_name(self, workers_df):
        """Abbreviated name should still match with lower confidence."""
        from app.pipeline.identity import resolve_identity
        result = resolve_identity('+91 9901476797', 'R. Kumar', workers_df)
        assert result['worker_id'] == 'W0001'
        # Could be 0.50 or 0.70 depending on token_sort_ratio
        assert result['confidence'] >= 0.50

    def test_unresolvable_phone(self, workers_df):
        from app.pipeline.identity import resolve_identity
        result = resolve_identity('12345', 'Ramesh Kumar', workers_df)
        assert result['worker_id'] is None
        assert result['confidence'] == 0.0

    def test_phone_not_in_registry(self, workers_df):
        from app.pipeline.identity import resolve_identity
        result = resolve_identity('+91 9000000000', 'Unknown Person', workers_df)
        assert result['worker_id'] is None
        assert result['confidence'] == 0.0


# ── Tests for rates.py ────────────────────────────────────────

class TestRateResolution:
    """Test rate resolution with overlapping windows (BUG-03) and Decimal arithmetic (BUG-04)."""

    @pytest.fixture
    def workers_df(self):
        return pd.DataFrame([
            {'worker_id': 'W0001', 'name': 'Test Worker', 'phone': '9901476797',
             'state': 'MH', 'role': 'Data Entry', 'seniority': 'junior'},
            {'worker_id': 'W0050', 'name': 'Crop Worker', 'phone': '9111111111',
             'state': 'MH', 'role': 'Crop Inspector', 'seniority': 'junior'},
        ])

    @pytest.fixture
    def rates_df(self):
        df = pd.DataFrame([
            {'role': 'Data Entry', 'state': 'MH', 'seniority': 'junior',
             'effective_from': date(2025, 1, 1), 'effective_to': date(2025, 2, 28),
             'hourly_rate_inr': Decimal('300.00'), 'hourly_rate_paise': 30000},
            {'role': 'Data Entry', 'state': 'MH', 'seniority': 'junior',
             'effective_from': date(2025, 3, 1), 'effective_to': None,
             'hourly_rate_inr': Decimal('340.00'), 'hourly_rate_paise': 34000},
            {'role': 'Data Entry', 'state': 'MH', 'seniority': 'junior',
             'effective_from': date(2025, 3, 10), 'effective_to': date(2025, 3, 20),
             'hourly_rate_inr': Decimal('320.00'), 'hourly_rate_paise': 32000},
            {'role': 'Crop Inspector', 'state': 'MH', 'seniority': 'junior',
             'effective_from': date(2025, 1, 1), 'effective_to': None,
             'hourly_rate_inr': Decimal('450.33'), 'hourly_rate_paise': 45033},
        ])
        # Fill effective_to
        df['effective_to_filled'] = df['effective_to'].apply(
            lambda x: x if x is not None else date(9999, 12, 31)
        )
        return df

    def test_data_entry_march_15(self, workers_df, rates_df):
        """Data Entry MH junior on 2025-03-15 → ₹340 (34000 paise), not ₹320."""
        from app.pipeline.rates import resolve_rate
        result = resolve_rate('W0001', date(2025, 3, 15), workers_df, rates_df)
        assert result['status'] == 'OK'
        assert result['rate_paise'] == 34000  # ₹340, not ₹320

    def test_data_entry_january(self, workers_df, rates_df):
        """Data Entry MH junior on 2025-01-15 → ₹300 (30000 paise)."""
        from app.pipeline.rates import resolve_rate
        result = resolve_rate('W0001', date(2025, 1, 15), workers_df, rates_df)
        assert result['status'] == 'OK'
        assert result['rate_paise'] == 30000

    def test_decimal_arithmetic(self):
        """450.33 INR/h = 45033 paise/h × 7.5h = 337747.5 → 337748 paise."""
        from app.pipeline.rates import calculate_expected_paise
        result = calculate_expected_paise(7.5, 45033)
        assert result == 337748  # ROUND_HALF_UP, not 337747

    def test_no_rate_found(self, workers_df, rates_df):
        """Non-existent combination → NO_RATE_FOUND."""
        workers_df_ext = pd.concat([workers_df, pd.DataFrame([{
            'worker_id': 'W9999', 'name': 'Ghost', 'phone': '9999999999',
            'state': 'KA', 'role': 'Pilot', 'seniority': 'junior'
        }])])
        from app.pipeline.rates import resolve_rate
        result = resolve_rate('W9999', date(2025, 3, 15), workers_df_ext, rates_df)
        assert result['status'] == 'NO_RATE_FOUND'


# ── Tests for anomaly.py ──────────────────────────────────────

class TestAnomaly:
    def test_low_value_transfer(self):
        from app.pipeline.anomaly import check_low_value_transfer
        assert check_low_value_transfer(1700) is True  # ₹17 (BUG-09)
        assert check_low_value_transfer(50000) is False
        assert check_low_value_transfer(49999) is True

    def test_precision_bug(self):
        from app.pipeline.anomaly import check_precision_bug
        assert check_precision_bug(225050) is True   # not divisible by 100
        assert check_precision_bug(225000) is False  # clean rupee amount


# ── Tests for reconcile.py ────────────────────────────────────

class TestReconciliation:
    def test_classify_exact_match(self):
        from app.pipeline.reconcile import classify_discrepancy
        assert classify_discrepancy(100000, 100000).value == 'EXACT_MATCH'

    def test_classify_underpayment(self):
        from app.pipeline.reconcile import classify_discrepancy
        assert classify_discrepancy(100000, 80000).value == 'UNDERPAYMENT'

    def test_classify_overpayment(self):
        from app.pipeline.reconcile import classify_discrepancy
        assert classify_discrepancy(100000, 120000).value == 'OVERPAYMENT'

    def test_classify_unmatched_work(self):
        from app.pipeline.reconcile import classify_discrepancy
        assert classify_discrepancy(100000, 0).value == 'UNMATCHED_WORK'

    def test_classify_unmatched_payment(self):
        from app.pipeline.reconcile import classify_discrepancy
        assert classify_discrepancy(0, 100000).value == 'UNMATCHED_PAYMENT'

    def test_classify_near_match(self):
        """Within 0.5% should be NEAR_MATCH."""
        from app.pipeline.reconcile import classify_discrepancy
        # 0.4% difference
        assert classify_discrepancy(100000, 99600).value == 'NEAR_MATCH'

    def test_priority_p0_unmatched_work(self):
        from app.pipeline.reconcile import assign_priority
        from app.core.constants import DiscrepancyType
        result = assign_priority(DiscrepancyType.UNMATCHED_WORK, -50000)
        assert result.value == 'P0'

    def test_priority_p1_large_delta(self):
        from app.pipeline.reconcile import assign_priority
        from app.core.constants import DiscrepancyType
        result = assign_priority(DiscrepancyType.UNDERPAYMENT, -150000)
        assert result.value == 'P1'

    def test_confidence_score(self):
        from app.pipeline.reconcile import compute_confidence_score
        score = compute_confidence_score(0.95, 'OK', False, False)
        # 0.4*0.95 + 0.3*1.0 + 0.2*1.0 + 0.1*1.0 = 0.38 + 0.3 + 0.2 + 0.1 = 0.98
        assert abs(score - 0.98) < 0.01


class FakeResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar_value


class FakeAsyncSession:
    def __init__(self, handlers):
        self.handlers = handlers
        self.inserted = []
        self.commits = 0

    async def execute(self, query, params=None):
        sql = str(query)

        if 'INSERT INTO reconciliation' in sql:
            self.inserted.append(params)
            return FakeResult()

        for marker, result in self.handlers:
            if marker in sql:
                return result(params, sql) if callable(result) else result

        raise AssertionError(f'Unexpected SQL: {sql}')

    async def commit(self):
        self.commits += 1


def build_worker_and_rate_context(rate_paise: int = 10000):
    workers_df = pd.DataFrame([
        {
            'worker_id': 'W0001',
            'name': 'Ramesh Kumar',
            'phone': '9901476797',
            'state': 'MH',
            'role': 'Data Entry',
            'seniority': 'junior',
        }
    ])
    rates_df = pd.DataFrame([
        {
            'id': 1,
            'role': 'Data Entry',
            'state': 'MH',
            'seniority': 'junior',
            'effective_from': date(2025, 1, 1),
            'effective_to': None,
            'effective_to_filled': date(9999, 12, 31),
            'hourly_rate_paise': rate_paise,
        }
    ]).set_index('id', drop=False)
    return workers_df, rates_df


def build_reconciliation_session(
    *,
    combo_rows,
    expected_shift_rows,
    review_shift_rows,
    actual_total,
    duplicate_rows=None,
    shift_meta=None,
    precision_bug_count=0,
    low_value_count=0,
):
    duplicate_rows = duplicate_rows or []
    shift_meta = shift_meta or SimpleNamespace(
        min_confidence=0.95,
        any_tz_corrected=False,
        any_hours_anomaly=False,
    )

    return FakeAsyncSession([
        ('SELECT DISTINCT worker_id, billing_period', FakeResult(rows=combo_rows)),
        ('SELECT log_id, work_date, hours, hours_anomaly, vendor_app', FakeResult(rows=expected_shift_rows)),
        ('SELECT COALESCE(SUM(amount_paise), 0) as total', FakeResult(scalar_value=actual_total)),
        ('GROUP BY amount_paise', FakeResult(rows=duplicate_rows)),
        ('SELECT log_id, hours_anomaly, tz_corrected, identity_confidence', FakeResult(rows=review_shift_rows)),
        ('SELECT COUNT(*) FROM bank_transfers', lambda params, sql: FakeResult(scalar_value=precision_bug_count if 'precision_bug = TRUE' in sql else low_value_count)),
        ('SELECT MIN(identity_confidence) as min_confidence', FakeResult(rows=[shift_meta])),
    ])


class TestPipelineRuntime:
    @pytest.mark.asyncio
    async def test_impossible_hours(self):
        from app.services.audit import build_shift_details

        session = FakeAsyncSession([
            ('SELECT worker_id, name, phone, state, role, seniority, registered_on', FakeResult(rows=[
                SimpleNamespace(
                    worker_id='W0056',
                    name='A. Nair',
                    phone='9413435240',
                    state='MH',
                    role='Crop Inspector',
                    seniority='junior',
                    registered_on=date(2025, 1, 1),
                )
            ])),
            ('SELECT id, role, state, seniority, effective_from, effective_to, hourly_rate_paise', FakeResult(rows=[
                SimpleNamespace(
                    id=8,
                    role='Crop Inspector',
                    state='MH',
                    seniority='junior',
                    effective_from=date(2025, 1, 1),
                    effective_to=None,
                    hourly_rate_paise=45033,
                )
            ])),
            ('SELECT log_id, work_date, billing_period, hours, vendor_app, supervisor_id', FakeResult(rows=[
                SimpleNamespace(
                    log_id='L02617',
                    work_date=date(2025, 2, 5),
                    billing_period='2025-02',
                    hours=450.0,
                    vendor_app='vendor_a_v2.3',
                    supervisor_id='S104',
                    tz_corrected=False,
                    hours_anomaly=True,
                    identity_confidence=0.7,
                    raw_worker_name='A. Nair',
                    raw_worker_phone='0 9413435240',
                )
            ])),
        ])

        shifts = await build_shift_details(session, 'W0056', '2025-02')
        assert len(shifts) == 1
        assert shifts[0]['hours_anomaly'] is True
        assert shifts[0]['rate_status'] == 'IMPOSSIBLE_HOURS'
        assert shifts[0]['expected_paise'] is None

    @pytest.mark.asyncio
    async def test_reconciliation_full(self):
        from app.pipeline.reconcile import run_reconciliation

        workers_df, rates_df = build_worker_and_rate_context(rate_paise=10000)
        combo_rows = [SimpleNamespace(worker_id='W0001', billing_period='2025-01')]
        expected_shift_rows = [
            SimpleNamespace(log_id='L1', work_date=date(2025, 1, 5), hours=5, hours_anomaly=False, vendor_app='vendor_a_v2.3'),
            SimpleNamespace(log_id='L2', work_date=date(2025, 1, 6), hours=6, hours_anomaly=False, vendor_app='vendor_a_v2.3'),
            SimpleNamespace(log_id='L3', work_date=date(2025, 1, 7), hours=7, hours_anomaly=False, vendor_app='vendor_a_v2.3'),
        ]
        review_shift_rows = [
            SimpleNamespace(log_id='L1', hours_anomaly=False, tz_corrected=False, identity_confidence=0.95, vendor_app='vendor_a_v2.3', work_date=date(2025, 1, 5), hours=5),
            SimpleNamespace(log_id='L2', hours_anomaly=False, tz_corrected=False, identity_confidence=0.95, vendor_app='vendor_a_v2.3', work_date=date(2025, 1, 6), hours=6),
            SimpleNamespace(log_id='L3', hours_anomaly=False, tz_corrected=False, identity_confidence=0.95, vendor_app='vendor_a_v2.3', work_date=date(2025, 1, 7), hours=7),
        ]
        session = build_reconciliation_session(
            combo_rows=combo_rows,
            expected_shift_rows=expected_shift_rows,
            review_shift_rows=review_shift_rows,
            actual_total=160000,
        )

        stats = await run_reconciliation('run-1', workers_df, rates_df, session)

        assert stats == {'processed': 1, 'anomalies': 1}
        assert session.commits == 1
        assert session.inserted[0]['expected'] == 180000
        assert session.inserted[0]['actual'] == 160000
        assert session.inserted[0]['delta'] == -20000
        assert session.inserted[0]['disc_type'] == 'UNDERPAYMENT'
        assert session.inserted[0]['needs_review'] is True

    @pytest.mark.asyncio
    async def test_duplicate_payment_detection(self):
        from app.pipeline.reconcile import run_reconciliation

        workers_df, rates_df = build_worker_and_rate_context(rate_paise=10000)
        combo_rows = [SimpleNamespace(worker_id='W0001', billing_period='2025-01')]
        expected_shift_rows = [
            SimpleNamespace(log_id='L1', work_date=date(2025, 1, 5), hours=10, hours_anomaly=False, vendor_app='vendor_a_v2.3'),
        ]
        review_shift_rows = [
            SimpleNamespace(log_id='L1', hours_anomaly=False, tz_corrected=False, identity_confidence=0.95, vendor_app='vendor_a_v2.3', work_date=date(2025, 1, 5), hours=10),
        ]
        session = build_reconciliation_session(
            combo_rows=combo_rows,
            expected_shift_rows=expected_shift_rows,
            review_shift_rows=review_shift_rows,
            actual_total=150000,
            duplicate_rows=[SimpleNamespace(amount_paise=75000, cnt=2)],
        )

        await run_reconciliation('run-dup', workers_df, rates_df, session)

        assert session.inserted[0]['disc_type'] == 'DUPLICATE_PAYMENT'

    @pytest.mark.asyncio
    async def test_unmatched_work(self):
        from app.pipeline.reconcile import run_reconciliation

        workers_df, rates_df = build_worker_and_rate_context(rate_paise=10000)
        combo_rows = [SimpleNamespace(worker_id='W0001', billing_period='2025-01')]
        expected_shift_rows = [
            SimpleNamespace(log_id='L1', work_date=date(2025, 1, 5), hours=8, hours_anomaly=False, vendor_app='vendor_a_v2.3'),
        ]
        review_shift_rows = [
            SimpleNamespace(log_id='L1', hours_anomaly=False, tz_corrected=False, identity_confidence=0.95, vendor_app='vendor_a_v2.3', work_date=date(2025, 1, 5), hours=8),
        ]
        session = build_reconciliation_session(
            combo_rows=combo_rows,
            expected_shift_rows=expected_shift_rows,
            review_shift_rows=review_shift_rows,
            actual_total=0,
        )

        await run_reconciliation('run-unmatched-work', workers_df, rates_df, session)
        assert session.inserted[0]['disc_type'] == 'UNMATCHED_WORK'

    @pytest.mark.asyncio
    async def test_unmatched_payment(self):
        from app.pipeline.reconcile import run_reconciliation

        workers_df, rates_df = build_worker_and_rate_context(rate_paise=10000)
        combo_rows = [SimpleNamespace(worker_id='W0001', billing_period='2025-01')]
        session = build_reconciliation_session(
            combo_rows=combo_rows,
            expected_shift_rows=[],
            review_shift_rows=[],
            actual_total=50000,
            shift_meta=SimpleNamespace(min_confidence=None, any_tz_corrected=False, any_hours_anomaly=False),
        )

        await run_reconciliation('run-unmatched-payment', workers_df, rates_df, session)
        assert session.inserted[0]['disc_type'] == 'UNMATCHED_PAYMENT'
