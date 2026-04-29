# MASTER BUILD PROMPT — Wage Payout Reconciliation Platform
# Paste this entire prompt into Cursor / Windsurf / Codeium as your first message.
# Do NOT split it. Do NOT summarise it. Feed it whole.

---

You are a senior full-stack engineer and data engineer.

Your task is to build a **production-grade Wage Payout Reconciliation Platform** end-to-end.

You have an `instructions.md` file in the root of this project. It contains every build step in sequential order. You MUST:
- Read `instructions.md` at the start of every session
- Find the first step that is NOT marked `[DONE]`
- Work ONLY on that step until it is complete and tested
- Mark it `[DONE]` before moving to the next step
- Never skip steps. Never reorder steps.
- If you are unsure which step you are on, re-read `instructions.md` and look for the last `[DONE]` line.

---

## TECH STACK

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI |
| Data processing | pandas, numpy, python-Levenshtein, rapidfuzz |
| Arithmetic | Python `decimal.Decimal` (NEVER float for money) |
| Database | PostgreSQL 15 (via SQLAlchemy 2.0 + asyncpg) |
| Migrations | Alembic |
| Task queue | Celery + Redis (for pipeline runs) |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Charts | Recharts |
| Auth | NextAuth.js (email/password, single tenant) |
| Testing | pytest (backend), Jest + React Testing Library (frontend) |
| Containerisation | Docker + docker-compose |

---

## PROJECT STRUCTURE

```
/
├── instructions.md          ← ALWAYS READ THIS FIRST
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/          ← SQLAlchemy ORM models
│   │   ├── schemas/         ← Pydantic schemas
│   │   ├── api/             ← FastAPI routers
│   │   ├── pipeline/        ← ETL + reconciliation engine
│   │   │   ├── ingest.py
│   │   │   ├── normalise.py
│   │   │   ├── identity.py
│   │   │   ├── rates.py
│   │   │   ├── reconcile.py
│   │   │   └── anomaly.py
│   │   └── core/
│   │       ├── config.py
│   │       └── constants.py
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx         ← Dashboard home
│   │   ├── workers/[id]/    ← Worker drilldown
│   │   └── review/          ← Review queue
│   ├── components/
│   ├── lib/
│   └── package.json
└── data/
    └── samples/             ← Put the 4 CSV files here
```

---

## DOMAIN KNOWLEDGE — READ THIS OR YOU WILL BUILD IT WRONG

### The 4 datasets and what they represent

**supervisor_logs.csv** — Work performed. One row = one shift.
- Columns: log_id, worker_name, worker_phone, supervisor_id, work_date, hours, vendor_app, entered_at
- Problems: 6 phone formats, free-text names, vendor_b uses UTC (all others IST), one entry has 450 hours (data corruption)

**bank_transfers.csv** — Money paid. One row = one batch payment.
- Columns: utr, worker_phone, worker_name, amount_paise, transfer_timestamp, account_last4
- Problems: 246 transfers have sub-rupee paise (float arithmetic bug in source), payments are batched (one UTR ≠ one shift)

**wage_rates.csv** — Hourly rates by role+state+seniority, effective-dated.
- Columns: role, state, effective_from, effective_to, hourly_rate_inr, seniority
- Problems: One rate is 450.33 (fractional), one combination has 3 overlapping rows

**workers.csv** — Canonical worker registry (current snapshot only, NOT historical).
- Columns: worker_id, name, phone, state, role, seniority, registered_on
- Problems: 10 duplicate names (different worker_ids), phones are clean 10-digit integers

### Critical bugs you must handle — these are NOT edge cases, they are the core problem

**BUG-01 IMPOSSIBLE HOURS:** log L02617 has hours=450. Cap validation at 16h. Flag as DATA_CORRUPTION. Exclude from wage calculation. Do not silently include it.

**BUG-02 TIMEZONE:** vendor_b_v1.0 timestamps end in +00:00 (UTC). vendor_a_v2.3 ends in +05:30 (IST). You MUST convert all timestamps to IST before deriving work_date. A 22:30 UTC entry is 04:00 IST the NEXT day — the work_date column for vendor_b is wrong and must be recomputed.

**BUG-03 RATE OVERLAP:** Data Entry + MH + junior has THREE rate rows where two overlap (2025-03-01 to open at ₹340, AND 2025-03-10 to 2025-03-20 at ₹320). Resolution rule: sort by effective_from DESC, effective_to ASC, take first. If still ambiguous → flag AMBIGUOUS_RATE, needs_manual_review=true.

**BUG-04 FRACTIONAL RATE:** Crop Inspector + MH + junior rate is 450.33 INR/h. Multiplying by hours with float produces sub-paise fractions. You MUST use Python `Decimal` for ALL wage arithmetic. Rounding rule: ROUND_HALF_UP to nearest integer paise.

**BUG-05 PHONE FORMAT:** Supervisor logs store phones in 6 formats. Normalisation rule (apply in this order):
1. Strip all non-digits
2. If starts with '91' and length == 12 → drop first 2 digits
3. If starts with '0' and length == 11 → drop first digit
4. If length == 10 and first digit in {6,7,8,9} → accept
5. Else → flag UNRESOLVABLE_PHONE, needs_manual_review=true

**BUG-06 PAISE PRECISION:** 10.9% of transfers have amount_paise % 100 != 0. Store as-is. Flag with PRECISION_BUG review reason. Do not round the transfer amounts — record them exactly and let the discrepancy surface in the delta.

**BUG-07 DUPLICATE NAMES:** workers.csv has pairs like (W0001, Ramesh Kumar) and (W0002, Ramesh Kumar). Name alone cannot identify a worker. Phone is the primary key for identity resolution.

**BUG-08 VENDOR_B INTEGRATION:** Only 8 supervisor_log entries from vendor_b across 2 supervisors (S201, S202). Flag all 8 as VENDOR_B_ANOMALY in addition to other flags.

**BUG-09 GHOST PAYMENT:** One transfer of ₹17.00 (1700 paise). Minimum possible wage is 4h × ₹280 = ₹1,120. Flag as LOW_VALUE_TRANSFER.

### Money rules — non-negotiable
- ALL monetary values are stored as BIGINT in paise (1 INR = 100 paise)
- NO float columns anywhere in the database or calculation engine
- Use `from decimal import Decimal, ROUND_HALF_UP` for every calculation
- Convert: `expected_paise = int((Decimal(str(rate)) * Decimal(str(hours)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))`

### Reconciliation logic
Reconciliation happens at the **(worker_id, billing_period)** level, NOT at the row level.
- billing_period = calendar month (format: YYYY-MM)
- Group all shifts for a worker in a month → sum expected_paise
- Group all bank transfers for a worker in a month → sum actual_paise
- delta = actual_paise - expected_paise
- Positive delta = overpayment. Negative delta = underpayment.

### Discrepancy types (store as enum)
```
EXACT_MATCH         — delta == 0
NEAR_MATCH          — |delta| / expected < 0.005 (rounding noise)
UNDERPAYMENT        — delta < 0
OVERPAYMENT         — delta > 0
UNMATCHED_WORK      — shifts exist, no payment in period
UNMATCHED_PAYMENT   — payment exists, no shifts in period
DUPLICATE_PAYMENT   — same worker, same period, 2+ UTRs with identical amounts
```

### needs_manual_review = true when ANY of:
- Identity confidence < 0.7
- Rate resolution = AMBIGUOUS_RATE
- discrepancy_type in [UNDERPAYMENT, OVERPAYMENT, UNMATCHED_WORK, UNMATCHED_PAYMENT, DUPLICATE_PAYMENT]
- Hours flagged anomalous
- Phone was unresolvable
- Timezone correction applied (vendor_b)
- |delta| / expected > 0.05

### review_reason format
Pipe-delimited string of all triggered conditions. Example:
`"UNDERPAYMENT:₹342 short | AMBIGUOUS_RATE:Data Entry MH junior 2025-03-15 | TIMEZONE_CORRECTED:vendor_b"`

### Priority levels
- P0 CRITICAL — UNMATCHED_WORK or UNMATCHED_PAYMENT
- P1 HIGH — |delta| > 100000 paise (₹1,000)
- P2 MEDIUM — AMBIGUOUS_RATE + any discrepancy
- P3 LOW — NEAR_MATCH, PRECISION_BUG only

---

## DATABASE SCHEMA

```sql
-- workers (canonical registry)
CREATE TABLE workers (
  worker_id     VARCHAR(10) PRIMARY KEY,
  name          VARCHAR(255) NOT NULL,
  phone         VARCHAR(10) NOT NULL UNIQUE,
  state         VARCHAR(5) NOT NULL,
  role          VARCHAR(50) NOT NULL,
  seniority     VARCHAR(10) NOT NULL,
  registered_on DATE NOT NULL
);

-- wage_rates (effective-dated, overlaps disallowed)
CREATE TABLE wage_rates (
  id              SERIAL PRIMARY KEY,
  role            VARCHAR(50) NOT NULL,
  state           VARCHAR(5) NOT NULL,
  seniority       VARCHAR(10) NOT NULL,
  effective_from  DATE NOT NULL,
  effective_to    DATE,  -- NULL = open-ended (treat as 9999-12-31)
  hourly_rate_paise BIGINT NOT NULL  -- stored in paise, not INR
);

-- shift_logs (normalised supervisor logs)
CREATE TABLE shift_logs (
  log_id              VARCHAR(10) PRIMARY KEY,
  worker_id           VARCHAR(10) REFERENCES workers(worker_id),
  raw_worker_name     VARCHAR(255),
  raw_worker_phone    VARCHAR(30),
  supervisor_id       VARCHAR(10),
  work_date           DATE NOT NULL,
  hours               NUMERIC(5,2) NOT NULL,
  vendor_app          VARCHAR(30),
  entered_at_utc      TIMESTAMPTZ,
  tz_corrected        BOOLEAN DEFAULT FALSE,
  identity_confidence NUMERIC(4,3),
  hours_anomaly       BOOLEAN DEFAULT FALSE,
  pipeline_run_id     UUID NOT NULL
);

-- bank_transfers (normalised payments)
CREATE TABLE bank_transfers (
  utr               VARCHAR(20) PRIMARY KEY,
  worker_id         VARCHAR(10) REFERENCES workers(worker_id),
  raw_worker_name   VARCHAR(255),
  raw_worker_phone  VARCHAR(15),
  amount_paise      BIGINT NOT NULL,
  transfer_date     DATE NOT NULL,
  billing_period    VARCHAR(7) NOT NULL,  -- YYYY-MM
  account_last4     VARCHAR(4),
  precision_bug     BOOLEAN DEFAULT FALSE,
  pipeline_run_id   UUID NOT NULL
);

-- reconciliation (one row per worker per billing period)
CREATE TABLE reconciliation (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_id           VARCHAR(10) REFERENCES workers(worker_id),
  billing_period      VARCHAR(7) NOT NULL,
  expected_paise      BIGINT,
  actual_paise        BIGINT,
  delta_paise         BIGINT,
  discrepancy_type    VARCHAR(30) NOT NULL,
  needs_manual_review BOOLEAN DEFAULT FALSE,
  review_reason       TEXT,
  priority            VARCHAR(5),
  confidence_score    NUMERIC(4,3),
  resolved            BOOLEAN DEFAULT FALSE,
  resolved_by         VARCHAR(100),
  resolved_at         TIMESTAMPTZ,
  resolution_notes    TEXT,
  pipeline_run_id     UUID NOT NULL,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (worker_id, billing_period, pipeline_run_id)
);

-- pipeline_runs (audit trail)
CREATE TABLE pipeline_runs (
  run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at      TIMESTAMPTZ DEFAULT NOW(),
  completed_at    TIMESTAMPTZ,
  status          VARCHAR(20) DEFAULT 'running',
  rows_logs       INT,
  rows_transfers  INT,
  anomalies_found INT,
  error_message   TEXT
);
```

---

## API ENDPOINTS

```
GET  /api/v1/health
POST /api/v1/pipeline/run                         — trigger reconciliation (async, returns run_id)
GET  /api/v1/pipeline/runs                        — list all pipeline runs
GET  /api/v1/pipeline/runs/{run_id}               — status of a run

GET  /api/v1/reconciliation                       — list all records (paginated)
     ?period=YYYY-MM&priority=P0&type=UNDERPAYMENT&needs_review=true&page=1&limit=50
GET  /api/v1/reconciliation/{id}                  — single record with full audit trail
PATCH /api/v1/reconciliation/{id}/resolve         — mark resolved {resolved_by, notes}

GET  /api/v1/workers                              — list workers
GET  /api/v1/workers/{worker_id}                  — worker detail
GET  /api/v1/workers/{worker_id}/audit-trail      — all shifts, rates, payments, deltas

GET  /api/v1/stats/summary?period=YYYY-MM         — dashboard numbers
     returns: {total_expected, total_actual, net_delta, review_count_by_priority, discrepancy_breakdown}
```

---

## FRONTEND PAGES

### / (Dashboard)
- Summary cards: Total Expected Wages, Total Actual Paid, Net Delta, Open Reviews
- Bar chart: Expected vs Actual per billing period
- Donut chart: Discrepancy type breakdown
- Quick links to P0/P1 review items

### /review (Review Queue)
- Table of all needs_manual_review=true records
- Columns: Worker, Period, Expected, Actual, Delta, Type, Priority, Reason, Status
- Filters: period, priority, discrepancy_type, resolved
- Row click → opens side panel with full audit trail
- "Mark Resolved" button with notes field

### /workers (Worker List)
- Searchable table of all 100 workers
- Click → /workers/[id]

### /workers/[id] (Worker Drilldown)
- Worker identity card (name, phone, role, state, seniority, confidence score)
- Timeline of all shifts with: date, hours, rate applied, expected paise, anomaly flags
- All UTRs received with amounts
- Per-period reconciliation summary with delta

---

## IDENTITY RESOLUTION IMPLEMENTATION

```python
# In backend/app/pipeline/identity.py

import re
from rapidfuzz import fuzz

def normalise_phone(raw: str) -> tuple[str | None, str]:
    """Returns (normalised_10_digit, status)"""
    digits = re.sub(r'\D', '', str(raw).strip())
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in '6789':
        return digits, 'OK'
    return None, 'UNRESOLVABLE_PHONE'

def resolve_identity(raw_phone: str, raw_name: str, workers_df) -> dict:
    norm_phone, phone_status = normalise_phone(raw_phone)
    if phone_status != 'OK':
        return {'worker_id': None, 'confidence': 0.0, 'status': 'UNRESOLVABLE_PHONE'}
    
    match = workers_df[workers_df['phone'] == norm_phone]
    if match.empty:
        return {'worker_id': None, 'confidence': 0.0, 'status': 'PHONE_NOT_IN_REGISTRY'}
    
    worker = match.iloc[0]
    # Name similarity as secondary validation
    name_score = fuzz.token_sort_ratio(
        raw_name.lower().strip(), 
        worker['name'].lower().strip()
    ) / 100.0
    
    if name_score >= 0.85:
        confidence = 0.95
    elif name_score >= 0.50:
        confidence = 0.70
    elif name_score >= 0.30:
        confidence = 0.50  # possible phone reassignment
    else:
        confidence = 0.35
    
    return {
        'worker_id': worker['worker_id'],
        'confidence': round(confidence, 3),
        'name_similarity': round(name_score, 3),
        'status': 'RESOLVED' if confidence >= 0.7 else 'LOW_CONFIDENCE'
    }
```

---

## WAGE CALCULATION IMPLEMENTATION

```python
# In backend/app/pipeline/rates.py

from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

def resolve_rate(worker_id: str, work_date, workers_df, rates_df) -> dict:
    worker = workers_df[workers_df['worker_id'] == worker_id].iloc[0]
    
    mask = (
        (rates_df['role'] == worker['role']) &
        (rates_df['state'] == worker['state']) &
        (rates_df['seniority'] == worker['seniority']) &
        (rates_df['effective_from'] <= work_date) &
        (rates_df['effective_to_filled'] >= work_date)  # NaT filled with 9999-12-31
    )
    matches = rates_df[mask].copy()
    
    if matches.empty:
        return {'rate_paise': None, 'status': 'NO_RATE_FOUND'}
    
    if len(matches) > 1:
        matches = matches.sort_values(
            ['effective_from', 'effective_to_filled'],
            ascending=[False, True]
        )
        if len(matches) > 1:
            # Still ambiguous after sort
            return {'rate_paise': None, 'status': 'AMBIGUOUS_RATE', 'candidates': matches.to_dict('records')}
    
    rate_row = matches.iloc[0]
    return {
        'rate_paise': int(Decimal(str(rate_row['hourly_rate_paise']))),
        'rate_row_id': int(rate_row.name),
        'status': 'OK'
    }

def calculate_expected_paise(hours: float, rate_paise: int) -> int:
    """Always use Decimal. Never float."""
    result = Decimal(str(rate_paise)) * Decimal(str(hours))
    return int(result.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
```

---

## ENVIRONMENT VARIABLES (.env)

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/reconciliation_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## DOCKER COMPOSE

```yaml
version: '3.9'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: reconciliation_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis]
    volumes: [./backend:/app, ./data:/data]

  celery:
    build: ./backend
    command: celery -A app.worker worker --loglevel=info
    env_file: .env
    depends_on: [postgres, redis]
    volumes: [./backend:/app, ./data:/data]

  frontend:
    build: ./frontend
    command: npm run dev
    ports: ["3000:3000"]
    env_file: .env
    depends_on: [backend]
    volumes: [./frontend:/app]

volumes:
  pgdata:
```

---

## TESTING REQUIREMENTS

Every pipeline module must have unit tests:
- `test_normalise_phone`: test all 6 phone formats → correct 10-digit output
- `test_timezone_correction`: vendor_b 22:30 UTC → 04:00 IST next day → date shifts
- `test_rate_resolution`: overlapping window → correct rate selected by recency sort
- `test_decimal_arithmetic`: 450.33 × 7.5h = 337748 paise (not 337747 or 337747.5)
- `test_reconciliation_aggregation`: 3 shifts + 2 UTRs in same period → correct delta
- `test_impossible_hours`: 450h shift → excluded from calculation, flagged

---

## WHAT SUCCESS LOOKS LIKE

The platform is complete when:
1. All 4 CSVs can be ingested via the pipeline trigger API
2. Every supervisor log maps to a worker_id with confidence score
3. Every shift has a deterministically resolved wage rate in paise
4. Per-worker, per-period expected vs actual delta is computed and stored
5. The review queue surfaces all anomalies with human-readable reasons
6. The dashboard shows total expected, total actual, net delta
7. A worker drilldown shows their complete forensic trail

---

## REMEMBER

- Read `instructions.md` first. Every session. No exceptions.
- Mark steps `[DONE]` as you complete them.
- Never use float for money. Ever.
- Paise is the unit of all monetary storage and arithmetic.
- Phone normalisation is not optional — it is the entire identity layer.
- Timezone correction for vendor_b is not optional — it changes work dates.
- The overlapping rate window is a real bug — your engine must resolve it deterministically.

Begin with Step 1 in `instructions.md`.