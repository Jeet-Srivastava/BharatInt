"""Database hardening helpers for indexes, derived columns, and constraints."""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def ensure_schema_hardening(conn) -> None:
    """Apply additive schema hardening needed by the live application."""
    statements = [
        """
        ALTER TABLE shift_logs
        ADD COLUMN IF NOT EXISTS billing_period VARCHAR(7)
        """,
        """
        UPDATE shift_logs
        SET billing_period = TO_CHAR(work_date, 'YYYY-MM')
        WHERE billing_period IS NULL
        """,
        """
        ALTER TABLE shift_logs
        ALTER COLUMN billing_period SET NOT NULL
        """,
        """
        UPDATE reconciliation
        SET resolved = FALSE
        WHERE resolved IS NULL
        """,
        """
        ALTER TABLE reconciliation
        ALTER COLUMN resolved SET DEFAULT FALSE
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_shift_logs_worker_work_date
        ON shift_logs (worker_id, work_date)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_shift_logs_billing_period
        ON shift_logs (billing_period)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_bank_transfers_worker_billing_period
        ON bank_transfers (worker_id, billing_period)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_reconciliation_review_priority
        ON reconciliation (needs_manual_review, priority)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_reconciliation_worker_billing_period
        ON reconciliation (worker_id, billing_period)
        """,
    ]

    for statement in statements:
        await conn.execute(text(statement))

    constraint_blocks = [
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_wage_rates_effective_from'
            ) THEN
                ALTER TABLE wage_rates
                ADD CONSTRAINT uq_wage_rates_effective_from
                UNIQUE (role, state, seniority, effective_from);
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_shift_logs_hours_valid'
            ) THEN
                ALTER TABLE shift_logs
                ADD CONSTRAINT ck_shift_logs_hours_valid
                CHECK (hours > 0 AND (hours <= 16 OR hours_anomaly = TRUE));
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_bank_transfers_amount_positive'
            ) THEN
                ALTER TABLE bank_transfers
                ADD CONSTRAINT ck_bank_transfers_amount_positive
                CHECK (amount_paise > 0);
            END IF;
        END $$;
        """,
    ]

    for block in constraint_blocks:
        await conn.execute(text(block))

    logger.info("Schema hardening applied")
