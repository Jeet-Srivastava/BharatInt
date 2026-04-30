# instructions.md
# WAGE PAYOUT RECONCILIATION PLATFORM — BUILD INSTRUCTIONS
#
# HOW TO USE THIS FILE:
# 1. Read this file at the START of every session before writing any code.
# 2. Find the first step that is NOT marked [DONE].
# 3. Work ONLY on that step. Do not jump ahead.
# 4. When a step is fully complete AND tested, change [ ] to [DONE].
# 5. If a step has sub-steps, ALL sub-steps must be [DONE] before the parent is [DONE].
# 6. If you are resuming and unsure where you are, find the last [DONE] line and continue from the next step.
# 7. Never delete or reorder steps. Only add [DONE] markers.

---

## PHASE 0 — PROJECT SCAFFOLDING

- [DONE] STEP-001: Create root directory structure
  - [DONE] STEP-001a: Create /backend directory
  - [DONE] STEP-001b: Create /frontend directory
  - [DONE] STEP-001c: Create /data/samples directory
  - [DONE] STEP-001d: Create /data/outputs directory
  - [DONE] STEP-001e: Place all 4 CSV files in /data/samples/

- [DONE] STEP-002: Create docker-compose.yml with postgres:15, redis:7-alpine, backend, celery, frontend services as specified in the prompt

- [DONE] STEP-003: Create root .env file with all required environment variables (DATABASE_URL, REDIS_URL, SECRET_KEY, NEXT_PUBLIC_API_URL)

- [DONE] STEP-004: Create /backend/requirements.txt with: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pandas, numpy, rapidfuzz, python-levenshtein, celery, redis, pydantic, python-dotenv, pytest, httpx

- [DONE] STEP-005: Create /backend/Dockerfile (python:3.11-slim, install requirements, WORKDIR /app)

- [DONE] STEP-006: Create /frontend/package.json with: next@14, react, react-dom, typescript, tailwindcss, recharts, @tanstack/react-query, axios, next-auth

- [DONE] STEP-007: Create /frontend/Dockerfile (node:20-alpine, npm install, WORKDIR /app)

- [DONE] STEP-008: Verify docker-compose up --build starts all services without errors. All containers must reach healthy state before proceeding.

---

## PHASE 1 — BACKEND FOUNDATION

- [DONE] STEP-009: Create /backend/app/__init__.py (empty)

- [DONE] STEP-010: Create /backend/app/core/config.py
  - [DONE] STEP-010a: Load DATABASE_URL, REDIS_URL, SECRET_KEY from env
  - [DONE] STEP-010b: Add DATA_DIR constant pointing to /data/samples
  - [DONE] STEP-010c: Add BILLING_PERIOD_FORMAT = "%Y-%m"

- [DONE] STEP-011: Create /backend/app/core/constants.py
  - [DONE] STEP-011a: Define DiscrepancyType enum (EXACT_MATCH, NEAR_MATCH, UNDERPAYMENT, OVERPAYMENT, UNMATCHED_WORK, UNMATCHED_PAYMENT, DUPLICATE_PAYMENT)
  - [DONE] STEP-011b: Define Priority enum (P0, P1, P2, P3)
  - [DONE] STEP-011c: Define ReviewStatus enum (AMBIGUOUS_RATE, NO_RATE_FOUND, UNRESOLVABLE_PHONE, TIMEZONE_CORRECTED, IMPOSSIBLE_HOURS, LOW_VALUE_TRANSFER, VENDOR_B_ANOMALY, PRECISION_BUG, LARGE_DISCREPANCY, DUPLICATE_PAYMENT_CANDIDATE)
  - [DONE] STEP-011d: Define MAX_HOURS_PER_SHIFT = 16
  - [DONE] STEP-011e: Define LOW_VALUE_PAISE_THRESHOLD = 50000 (₹500)
  - [DONE] STEP-011f: Define NEAR_MATCH_THRESHOLD = 0.005 (0.5%)
  - [DONE] STEP-011g: Define LARGE_DISCREPANCY_THRESHOLD = 0.05 (5%)

- [DONE] STEP-012: Create /backend/app/database.py
  - [DONE] STEP-012a: Async SQLAlchemy engine using asyncpg
  - [DONE] STEP-012b: AsyncSession factory
  - [DONE] STEP-012c: get_db() dependency for FastAPI
  - [DONE] STEP-012d: Base = declarative_base()

- [DONE] STEP-013: Create /backend/app/models/__init__.py and all ORM model files
  - [DONE] STEP-013a: models/worker.py — Worker model matching schema exactly
  - [DONE] STEP-013b: models/wage_rate.py — WageRate model, store rate as hourly_rate_paise BIGINT (convert INR → paise on ingest)
  - [DONE] STEP-013c: models/shift_log.py — ShiftLog model with all columns including tz_corrected, hours_anomaly, identity_confidence, pipeline_run_id
  - [DONE] STEP-013d: models/bank_transfer.py — BankTransfer model with billing_period derived field, precision_bug boolean
  - [DONE] STEP-013e: models/reconciliation.py — Reconciliation model with all columns including resolved, resolved_by, resolution_notes
  - [DONE] STEP-013f: models/pipeline_run.py — PipelineRun model

- [DONE] STEP-014: Create Alembic migration for initial schema
  - [DONE] STEP-014a: alembic init alembic
  - [DONE] STEP-014b: Configure alembic/env.py to use async engine and import all models
  - [DONE] STEP-014c: alembic revision --autogenerate -m "initial_schema"
  - [DONE] STEP-014d: alembic upgrade head
  - [DONE] STEP-014e: Verify all tables exist in PostgreSQL with correct column types

- [DONE] STEP-015: Create /backend/app/main.py
  - [DONE] STEP-015a: FastAPI app instance with title, version
  - [DONE] STEP-015b: CORS middleware (allow localhost:3000)
  - [DONE] STEP-015c: Include all routers (to be created later)
  - [DONE] STEP-015d: Startup event creates tables if not exist
  - [DONE] STEP-015e: GET /api/v1/health returns {"status": "ok"}
  - [DONE] STEP-015f: Verify health endpoint returns 200 via curl or httpx

---

## PHASE 2 — DATA PIPELINE: NORMALISATION

- [DONE] STEP-016: Create /backend/app/pipeline/normalise.py — Phone normalisation
  - [DONE] STEP-016a: Implement normalise_phone(raw: str) -> tuple[str | None, str] exactly as specified in the prompt
  - [DONE] STEP-016b: Handle all 6 formats: +91 XXXXXXXXXX, 91-XXXXXXXXXX, 91XXXXXXXXXX, XXXXX XXXXX, 0 XXXXXXXXXX, XXXXXXXXXX
  - [DONE] STEP-016c: Return (10_digit_string, 'OK') or (None, 'UNRESOLVABLE_PHONE')
  - [DONE] STEP-016d: Write unit test test_normalise_phone() testing all 6 formats and edge cases
  - [DONE] STEP-016e: All 6 format tests must pass before proceeding

- [DONE] STEP-017: Create /backend/app/pipeline/normalise.py — Timezone normalisation
  - [DONE] STEP-017a: Implement normalise_timestamp(raw_ts: str, vendor_app: str) -> tuple[datetime, bool]
  - [DONE] STEP-017b: Parse timestamp with timezone awareness (pd.to_datetime with utc=True)
  - [DONE] STEP-017c: Convert to Asia/Kolkata (IST, UTC+05:30)
  - [DONE] STEP-017d: For vendor_b_v1.0: re-derive work_date from IST datetime (not raw work_date column), set tz_corrected=True
  - [DONE] STEP-017e: For vendor_a_v2.3: use raw work_date as-is, tz_corrected=False
  - [DONE] STEP-017f: Write unit test test_timezone_correction(): vendor_b 22:30:00+00:00 on 2025-03-14 → IST date = 2025-03-15, tz_corrected=True
  - [DONE] STEP-017g: Test must pass before proceeding

- [DONE] STEP-018: Create /backend/app/pipeline/normalise.py — Hours validation
  - [DONE] STEP-018a: Implement validate_hours(hours: float, log_id: str) -> tuple[float | None, bool, str]
  - [DONE] STEP-018b: If hours > MAX_HOURS_PER_SHIFT (16): return (None, True, 'IMPOSSIBLE_HOURS') — exclude from calculation
  - [DONE] STEP-018c: If hours > 14 but <= 16: return (hours, True, 'HIGH_HOURS') — flag but include
  - [DONE] STEP-018d: Otherwise return (hours, False, '')
  - [DONE] STEP-018e: Write unit test: 450h → excluded, 15h → flagged but included, 8h → normal
  - [DONE] STEP-018f: Test must pass before proceeding

---

## PHASE 3 — DATA PIPELINE: IDENTITY RESOLUTION

- [DONE] STEP-019: Create /backend/app/pipeline/identity.py
  - [DONE] STEP-019a: Import rapidfuzz.fuzz
  - [DONE] STEP-019b: Implement resolve_identity(raw_phone, raw_name, workers_df) -> dict exactly as specified in the prompt
  - [DONE] STEP-019c: Confidence scoring: name_score >= 0.85 → 0.95, >= 0.50 → 0.70, >= 0.30 → 0.50, else 0.35
  - [DONE] STEP-019d: Return dict with: worker_id, confidence, name_similarity, status
  - [DONE] STEP-019e: Write unit test test_identity_resolution():
    - Clean match (same phone, same name) → confidence 0.95
    - Clean phone, surname-first name ('Kumar Ramesh' vs 'Ramesh Kumar') → confidence >= 0.70
    - Clean phone, initial only ('R. Kumar' vs 'Ramesh Kumar') → confidence 0.50–0.70
    - Unresolvable phone format → worker_id=None, confidence=0.0
    - Phone not in registry → worker_id=None, confidence=0.0
  - [DONE] STEP-019f: All identity tests must pass before proceeding

---

## PHASE 4 — DATA PIPELINE: RATE RESOLUTION

- [DONE] STEP-020: Create /backend/app/pipeline/rates.py
  - [DONE] STEP-020a: On load, fill NaT effective_to with pd.Timestamp('9999-12-31') — never leave NULL for date comparisons
  - [DONE] STEP-020b: Convert hourly_rate_inr to hourly_rate_paise: multiply by 100, use Decimal to avoid float errors (Decimal(str(rate)) * 100)
  - [DONE] STEP-020c: Implement resolve_rate(worker_id, work_date, workers_df, rates_df) -> dict exactly as specified in the prompt
  - [DONE] STEP-020d: Overlap resolution: sort by effective_from DESC, effective_to ASC, take first. If still ambiguous → AMBIGUOUS_RATE
  - [DONE] STEP-020e: Implement calculate_expected_paise(hours, rate_paise) -> int using Decimal with ROUND_HALF_UP
  - [DONE] STEP-020f: Write unit test test_rate_resolution():
    - Data Entry MH junior on 2025-03-15 → resolves to ₹340 (34000 paise/h), not ₹320
    - Data Entry MH junior on 2025-01-15 → resolves to ₹300 (30000 paise/h)
    - No matching role/state/seniority → NO_RATE_FOUND
  - [DONE] STEP-020g: Write unit test test_decimal_arithmetic():
    - 450.33 INR/h = 45033 paise/h
    - 45033 × 7.5h = 337747.5 → quantize ROUND_HALF_UP = 337748 paise
    - MUST NOT produce 337747 or any float
  - [DONE] STEP-020h: All rate tests must pass before proceeding

---

## PHASE 5 — DATA PIPELINE: INGEST

- [DONE] STEP-021: Create /backend/app/pipeline/ingest.py
  - [DONE] STEP-021a: Implement load_workers(path) → loads workers.csv, returns clean DataFrame with phone as 10-digit string
  - [DONE] STEP-021b: Implement load_wage_rates(path) → loads wage_rates.csv, converts hourly_rate_inr to hourly_rate_paise using Decimal, fills NaT effective_to with 9999-12-31
  - [DONE] STEP-021c: Implement load_supervisor_logs(path) → loads supervisor_logs.csv, returns raw DataFrame (normalisation happens in next step)
  - [DONE] STEP-021d: Implement load_bank_transfers(path) → loads bank_transfers.csv, returns raw DataFrame
  - [DONE] STEP-021e: Implement ingest_workers_to_db(workers_df, session) → upsert all workers to DB using worker_id as conflict key
  - [DONE] STEP-021f: Implement ingest_wage_rates_to_db(rates_df, session) → upsert all rates
  - [DONE] STEP-021g: Add validation: log warning if any column expected is missing from CSV

- [DONE] STEP-022: Create /backend/app/pipeline/ingest.py — Supervisor log processing
  - [DONE] STEP-022a: For each log row: normalise phone → resolve identity → normalise timestamp → validate hours
  - [DONE] STEP-022b: Build ShiftLog record with all fields: worker_id (from identity), tz_corrected, hours_anomaly, identity_confidence, pipeline_run_id
  - [DONE] STEP-022c: If hours_anomaly = True (impossible hours): set worker_id to None if hours > MAX, log exclusion
  - [DONE] STEP-022d: Flag vendor_b entries with VENDOR_B_ANOMALY review reason
  - [DONE] STEP-022e: Upsert to shift_logs table using log_id as conflict key

- [DONE] STEP-023: Create /backend/app/pipeline/ingest.py — Bank transfer processing
  - [DONE] STEP-023a: Normalise phone → look up worker_id from workers table
  - [DONE] STEP-023b: Derive billing_period from transfer_timestamp (format: YYYY-MM)
  - [DONE] STEP-023c: Set precision_bug = True if amount_paise % 100 != 0
  - [DONE] STEP-023d: Upsert to bank_transfers table using utr as conflict key

---

## PHASE 6 — DATA PIPELINE: RECONCILIATION ENGINE

- [DONE] STEP-024: Create /backend/app/pipeline/reconcile.py
  - [DONE] STEP-024a: Implement aggregate_expected(worker_id, billing_period, session) → SUM(expected_paise) for all non-anomalous shifts for that worker in that period
  - [DONE] STEP-024b: Implement aggregate_actual(worker_id, billing_period, session) → SUM(amount_paise) for all transfers for that worker in that period
  - [DONE] STEP-024c: Implement classify_discrepancy(expected, actual) -> DiscrepancyType:
    - expected=0 and actual=0 → EXACT_MATCH
    - expected>0 and actual=0 → UNMATCHED_WORK
    - expected=0 and actual>0 → UNMATCHED_PAYMENT
    - delta==0 → EXACT_MATCH
    - |delta|/expected < NEAR_MATCH_THRESHOLD → NEAR_MATCH
    - delta < 0 → UNDERPAYMENT
    - delta > 0 → OVERPAYMENT
  - [DONE] STEP-024d: Implement detect_duplicate_payment(worker_id, billing_period, session) -> bool — check if same worker has 2+ UTRs with identical amounts in same period
  - [DONE] STEP-024e: Write unit test test_reconciliation_aggregation(): 3 shifts (₹500+₹600+₹700 expected) + 2 UTRs (₹1200+₹400 actual) → delta = 1600000 - 1800000 = -200000 paise (underpayment)

- [DONE] STEP-025: Create /backend/app/pipeline/reconcile.py — Review flag generation
  - [DONE] STEP-025a: Implement build_review_reasons(shift_records, transfer_records, discrepancy_type, rate_status, identity_confidence, tz_corrected, delta, expected) -> list[str]
  - [DONE] STEP-025b: Collect all triggered reasons as list, join with ' | ' separator
  - [DONE] STEP-025c: Implement assign_priority(discrepancy_type, delta, rate_status) -> Priority
  - [DONE] STEP-025d: Implement compute_confidence_score(identity_conf, rate_status, tz_corrected, hours_anomaly) -> float using weighted formula: 0.4×identity + 0.3×rate + 0.2×timezone + 0.1×hours
  - [DONE] STEP-025e: Implement set_manual_review_flag(confidence_score, discrepancy_type, rate_status, hours_anomaly, phone_status, tz_corrected, delta_ratio) -> bool per the rules in the prompt

- [DONE] STEP-026: Create /backend/app/pipeline/reconcile.py — Full reconciliation runner
  - [DONE] STEP-026a: Implement run_reconciliation(pipeline_run_id, session):
    - Get all (worker_id, billing_period) combinations from shift_logs UNION bank_transfers
    - For each combination: aggregate expected + actual, classify discrepancy, check duplicate payment, build review reasons, compute confidence, set review flag
    - Upsert into reconciliation table using (worker_id, billing_period, pipeline_run_id) as conflict key
  - [DONE] STEP-026b: Update pipeline_run record with completed_at, status='completed', anomalies_found count

---

## PHASE 7 — ANOMALY DETECTION

- [DONE] STEP-027: Create /backend/app/pipeline/anomaly.py
  - [DONE] STEP-027a: Implement check_low_value_transfer(amount_paise) -> bool: amount_paise < LOW_VALUE_PAISE_THRESHOLD
  - [DONE] STEP-027b: Implement check_late_entry(work_date, entered_at) -> bool: entered_at IST date > work_date + 30 days
  - [DONE] STEP-027c: Implement check_hours_zscore(hours_series, hours_value) -> bool: |z-score| > 3 (after excluding impossible hours)
  - [DONE] STEP-027d: Implement check_payment_zscore(payment_series, payment_value, cohort_key) -> bool: per (role, state, seniority) cohort, |z-score| > 2
  - [DONE] STEP-027e: All anomaly detectors used during ingest and reconciliation phases — integrate calls into ingest.py and reconcile.py where appropriate

---

## PHASE 8 — CELERY WORKER

- [DONE] STEP-028: Create /backend/app/worker.py
  - [DONE] STEP-028a: Celery app instance connected to Redis
  - [DONE] STEP-028b: Implement run_pipeline_task(run_id: str) Celery task:
    1. Update PipelineRun status to 'running'
    2. Call load_workers, load_wage_rates, load_supervisor_logs, load_bank_transfers
    3. Call ingest_workers_to_db, ingest_wage_rates_to_db
    4. Call supervisor log processing (step 022)
    5. Call bank transfer processing (step 023)
    6. Call run_reconciliation
    7. Update PipelineRun status to 'completed' or 'failed' with error_message
  - [DONE] STEP-028c: Task must be idempotent — re-running with same run_id must produce identical output (UPSERT everywhere, not INSERT)

---

## PHASE 9 — FASTAPI ROUTES

- [DONE] STEP-029: Create /backend/app/schemas/ directory with Pydantic models
  - [DONE] STEP-029a: schemas/worker.py — WorkerBase, WorkerResponse
  - [DONE] STEP-029b: schemas/reconciliation.py — ReconciliationResponse, ReconciliationResolveRequest, ReconciliationSummary
  - [DONE] STEP-029c: schemas/pipeline.py — PipelineRunResponse, PipelineRunStatusResponse
  - [DONE] STEP-029d: schemas/stats.py — DashboardStats, DiscrepancyBreakdown

- [DONE] STEP-030: Create /backend/app/api/pipeline.py router
  - [DONE] STEP-030a: POST /api/v1/pipeline/run — create PipelineRun record, dispatch Celery task, return run_id
  - [DONE] STEP-030b: GET /api/v1/pipeline/runs — list all pipeline runs, ordered by started_at DESC
  - [DONE] STEP-030c: GET /api/v1/pipeline/runs/{run_id} — single run with status

- [DONE] STEP-031: Create /backend/app/api/reconciliation.py router
  - [DONE] STEP-031a: GET /api/v1/reconciliation — paginated list with filters: period, priority, type, needs_review
  - [DONE] STEP-031b: GET /api/v1/reconciliation/{id} — single record with full detail
  - [DONE] STEP-031c: PATCH /api/v1/reconciliation/{id}/resolve — update resolved=true, set resolved_by and resolution_notes

- [DONE] STEP-032: Create /backend/app/api/workers.py router
  - [DONE] STEP-032a: GET /api/v1/workers — list all workers (paginated, searchable by name)
  - [DONE] STEP-032b: GET /api/v1/workers/{worker_id} — worker detail
  - [DONE] STEP-032c: GET /api/v1/workers/{worker_id}/audit-trail — all shifts with rate used, all transfers, per-period reconciliation

- [DONE] STEP-033: Create /backend/app/api/stats.py router
  - [DONE] STEP-033a: GET /api/v1/stats/summary?period= — return total_expected_paise, total_actual_paise, net_delta_paise, review_count by priority, discrepancy_type breakdown

- [DONE] STEP-034: Register all routers in main.py with /api/v1 prefix

- [DONE] STEP-035: API smoke tests — run all endpoints against real ingested data
  - [DONE] STEP-035a: POST /pipeline/run returns 202 with run_id
  - [DONE] STEP-035b: GET /pipeline/runs/{run_id} eventually shows status='completed'
  - [DONE] STEP-035c: GET /reconciliation?needs_review=true returns records
  - [DONE] STEP-035d: GET /stats/summary?period=2025-01 returns numeric values
  - [DONE] STEP-035e: GET /workers/W0001/audit-trail returns shifts and transfers

---

## PHASE 10 — FRONTEND: SETUP

- [DONE] STEP-036: Initialise Next.js 14 app with App Router, TypeScript, Tailwind CSS in /frontend

- [DONE] STEP-037: Configure Tailwind with custom colours: primary blue (#1F3864), accent orange (#FF8C00), success green (#375623)

- [DONE] STEP-038: Create /frontend/lib/api.ts — axios instance with baseURL from NEXT_PUBLIC_API_URL, typed API functions for every endpoint

- [DONE] STEP-039: Create /frontend/lib/formatters.ts — formatPaise(paise: number) → '₹X,XXX.XX', formatDelta(delta: number) → coloured string, formatPeriod, formatConfidence

- [DONE] STEP-040: Create /frontend/components/layout/ — Sidebar, Header, PageWrapper with consistent navigation to Dashboard, Review Queue, Workers

---

## PHASE 11 — FRONTEND: DASHBOARD PAGE

- [DONE] STEP-041: Create /frontend/app/page.tsx — Dashboard
  - [DONE] STEP-041a: 4 summary cards: Total Expected, Total Actual, Net Delta (coloured red/green), Open Reviews
  - [DONE] STEP-041b: Bar chart (Recharts BarChart): Expected vs Actual paise per billing period — data from GET /stats/summary for each month
  - [DONE] STEP-041c: Donut chart (Recharts PieChart): discrepancy_type breakdown with colour coding
  - [DONE] STEP-041d: Review queue quick-view: top 5 P0/P1 items as clickable rows linking to /review
  - [DONE] STEP-041e: "Run Pipeline" button → POST /pipeline/run → show toast with run_id → poll status every 3s → show completion toast

---

## PHASE 12 — FRONTEND: REVIEW QUEUE PAGE

- [DONE] STEP-042: Create /frontend/app/review/page.tsx — Review Queue
  - [DONE] STEP-042a: Filter bar: Period (dropdown), Priority (P0/P1/P2/P3/All), Type (dropdown), Status (Resolved/Unresolved/All)
  - [DONE] STEP-042b: Table with columns: Worker Name, Period, Expected (₹), Actual (₹), Delta (coloured), Type (badge), Priority (badge), Review Reason (truncated), Status
  - [DONE] STEP-042c: Pagination (50 rows per page)
  - [DONE] STEP-042d: Row click → opens right-side drawer/panel with full record detail
  - [DONE] STEP-042e: Drawer shows: worker info, all review reasons, all contributing shifts (with rate used), all matching UTRs, confidence score breakdown
  - [DONE] STEP-042f: "Mark Resolved" button in drawer → text area for notes → PATCH /reconciliation/{id}/resolve → row updates in place

---

## PHASE 13 — FRONTEND: WORKER PAGES

- [DONE] STEP-043: Create /frontend/app/workers/page.tsx — Worker List
  - [DONE] STEP-043a: Search bar filtering by name or phone
  - [DONE] STEP-043b: Table: worker_id, name, phone, role, state, seniority, # of review items
  - [DONE] STEP-043c: Each row links to /workers/[id]

- [DONE] STEP-044: Create /frontend/app/workers/[id]/page.tsx — Worker Drilldown
  - [DONE] STEP-044a: Identity card: name, phone, role, state, seniority, registered date, identity confidence
  - [DONE] STEP-044b: Shift timeline table: work_date, hours, supervisor, vendor, rate applied, expected_paise, anomaly flags, tz_corrected indicator
  - [DONE] STEP-044c: Transfers table: UTR, date, amount_paise, precision_bug indicator
  - [DONE] STEP-044d: Per-period reconciliation summary: billing_period, expected, actual, delta (coloured), discrepancy_type badge, review link

---

## PHASE 14 — INTEGRATION & END-TO-END TEST

- [DONE] STEP-045: End-to-end integration test
  - [DONE] STEP-045a: Upload all 4 CSVs to /data/samples
  - [DONE] STEP-045b: Trigger pipeline via POST /api/v1/pipeline/run
  - [DONE] STEP-045c: Wait for status = 'completed'
  - [DONE] STEP-045d: Verify: 100 workers in DB
  - [DONE] STEP-045e: Verify: 2617 shift_log rows in DB (including the 450h anomaly row, flagged)
  - [DONE] STEP-045f: Verify: 2255 bank_transfer rows in DB
  - [DONE] STEP-045g: Verify: reconciliation table has rows for every (worker, period) combination
  - [DONE] STEP-045h: Verify: log L02617 (450h shift) is marked hours_anomaly=True and excluded from expected_paise
  - [DONE] STEP-045i: Verify: all 8 vendor_b entries have tz_corrected=True
  - [DONE] STEP-045j: Verify: Data Entry MH junior shifts on 2025-03-15 use rate 340 INR/h (not 320)
  - [DONE] STEP-045k: Verify: Crop Inspector MH junior 7.5h shift → expected_paise = 337748 (not 337747)
  - [DONE] STEP-045l: Verify: GET /api/v1/stats/summary?period=2025-01 returns non-zero values
  - [DONE] STEP-045m: Verify: GET /api/v1/reconciliation?needs_review=true returns records
  - [DONE] STEP-045n: Open browser to localhost:3000 — dashboard loads with data
  - [DONE] STEP-045o: Review queue shows flagged records
  - [DONE] STEP-045p: Worker drilldown for W0001 shows shifts and transfers

---

## PHASE 15 — HARDENING

- [DONE] STEP-046: Add database indexes
  - [DONE] STEP-046a: Index on shift_logs(worker_id, work_date)
  - [DONE] STEP-046b: Index on shift_logs(billing_period) — add derived billing_period column
  - [DONE] STEP-046c: Index on bank_transfers(worker_id, billing_period)
  - [DONE] STEP-046d: Index on reconciliation(needs_manual_review, priority)
  - [DONE] STEP-046e: Index on reconciliation(worker_id, billing_period)

- [DONE] STEP-047: Add data contract enforcement
  - [DONE] STEP-047a: On ingest, validate CSV schema (column names, no extra/missing columns) — halt if validation fails
  - [DONE] STEP-047b: Add DB constraint: wage_rates uniqueness — prevent duplicate (role, state, seniority, effective_from) rows
  - [DONE] STEP-047c: Add DB CHECK constraint: shift_logs.hours > 0 AND shift_logs.hours <= 16 (allow anomaly rows via separate flag, not by allowing 450)
  - [DONE] STEP-047d: Add DB CHECK constraint: bank_transfers.amount_paise > 0

- [DONE] STEP-048: Add structured logging
  - [DONE] STEP-048a: Every pipeline step logs: step_name, rows_processed, errors_count, duration_ms
  - [DONE] STEP-048b: Every identity resolution logs: log_id, raw_phone, normalised_phone, worker_id, confidence
  - [DONE] STEP-048c: Every rate resolution logs: log_id, worker_id, work_date, rate_row_id, rate_paise, status

- [DONE] STEP-049: Write remaining backend unit tests
  - [DONE] STEP-049a: test_impossible_hours: log with 450h → excluded from expected, flagged
  - [DONE] STEP-049b: test_reconciliation_full: end-to-end reconciliation with known inputs and expected outputs
  - [DONE] STEP-049c: test_duplicate_payment_detection: same worker, same period, same amount twice → DUPLICATE_PAYMENT flag
  - [DONE] STEP-049d: test_unmatched_work: shifts with no transfers → UNMATCHED_WORK
  - [DONE] STEP-049e: test_unmatched_payment: transfer with no shifts → UNMATCHED_PAYMENT
  - [DONE] STEP-049f: pytest must pass with 0 failures before this step is DONE

- [DONE] STEP-050: Final review — read through every file, check for float usage in monetary calculations
  - [DONE] STEP-050a: Grep entire codebase for "float" near monetary fields — must be zero occurrences
  - [DONE] STEP-050b: Grep for "amount" or "paise" or "rate" — all must use Decimal or int, never float
  - [DONE] STEP-050c: Confirm all money columns in DB are BIGINT (not NUMERIC, not FLOAT)

---

## COMPLETION CHECKLIST

- [ ] All 50 steps marked [DONE]
- [ ] docker-compose up starts cleanly with no errors
- [ ] pytest passes with 0 failures
- [ ] Pipeline processes all 4 CSVs without exception
- [ ] All 9 known bugs are correctly handled (see BUG-01 through BUG-09 in CURSOR_PROMPT.md)
- [ ] Dashboard loads at localhost:3000 with real data
- [ ] Review queue shows all needs_manual_review records
- [ ] Worker drilldown traces every rupee from shift → rate → expected → transfer → delta

---

## QUICK REFERENCE — KNOWN BUGS TO HANDLE

| Bug ID | What | Where to handle |
|--------|------|-----------------|
| BUG-01 | 450h shift (log L02617) | normalise.py validate_hours() |
| BUG-02 | vendor_b is UTC not IST | normalise.py normalise_timestamp() |
| BUG-03 | Overlapping rate window Data Entry MH junior | rates.py resolve_rate() |
| BUG-04 | Rate 450.33 causes float paise | rates.py calculate_expected_paise() with Decimal |
| BUG-05 | 6 phone formats in supervisor_logs | normalise.py normalise_phone() |
| BUG-06 | 246 transfers not divisible by 100 paise | ingest.py bank transfer processing |
| BUG-07 | 10 duplicate names in workers.csv | identity.py — use phone, not name, as primary key |
| BUG-08 | Only 8 vendor_b entries | ingest.py — flag VENDOR_B_ANOMALY |
| BUG-09 | ₹17.00 transfer (1700 paise) | anomaly.py check_low_value_transfer() |
