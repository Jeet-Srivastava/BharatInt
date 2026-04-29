"""Celery worker — async pipeline orchestration."""

import logging
import uuid
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import REDIS_URL, DATABASE_URL_SYNC, DATA_DIR

logger = logging.getLogger(__name__)

celery_app = Celery('worker', broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Kolkata',
    enable_utc=True,
)

# Synchronous engine for Celery tasks
sync_engine = create_engine(DATABASE_URL_SYNC)
SyncSession = sessionmaker(bind=sync_engine)


@celery_app.task(name='run_pipeline', bind=True, max_retries=0)
def run_pipeline_task(self, run_id: str):
    """Run the full data pipeline synchronously in a Celery worker.

    Steps:
    1. Update PipelineRun status to 'running'
    2. Load all 4 CSVs
    3. Ingest workers and wage rates
    4. Process supervisor logs
    5. Process bank transfers
    6. Run reconciliation
    7. Update PipelineRun status to 'completed' or 'failed'
    """
    import asyncio
    from app.pipeline.ingest import (
        load_workers, load_wage_rates, load_supervisor_logs, load_bank_transfers,
        ingest_workers_to_db, ingest_wage_rates_to_db,
        process_supervisor_logs, process_bank_transfers
    )
    from app.pipeline.reconcile import run_reconciliation
    from app.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as session:
            try:
                # 1. Update status to running
                await session.execute(
                    text("UPDATE pipeline_runs SET status = 'running' WHERE run_id = :run_id"),
                    {'run_id': run_id}
                )
                await session.commit()

                logger.info(f"Pipeline {run_id}: Loading CSVs...")

                # 2. Load CSVs
                workers_df = load_workers()
                rates_df = load_wage_rates()
                logs_df = load_supervisor_logs()
                transfers_df = load_bank_transfers()

                # 3. Ingest workers and rates
                logger.info(f"Pipeline {run_id}: Ingesting workers and rates...")
                await ingest_workers_to_db(workers_df, session)
                await ingest_wage_rates_to_db(rates_df, session)

                # 4. Process supervisor logs
                logger.info(f"Pipeline {run_id}: Processing supervisor logs...")
                log_stats = await process_supervisor_logs(
                    logs_df, workers_df, rates_df, run_id, session
                )

                # 5. Process bank transfers
                logger.info(f"Pipeline {run_id}: Processing bank transfers...")
                transfer_stats = await process_bank_transfers(
                    transfers_df, workers_df, run_id, session
                )

                # 6. Run reconciliation
                logger.info(f"Pipeline {run_id}: Running reconciliation...")
                anomalies = await run_reconciliation(run_id, workers_df, rates_df, session)

                # 7. Update pipeline run as completed
                await session.execute(
                    text("""
                        UPDATE pipeline_runs SET
                            status = 'completed',
                            completed_at = NOW(),
                            rows_logs = :rows_logs,
                            rows_transfers = :rows_transfers,
                            anomalies_found = :anomalies
                        WHERE run_id = :run_id
                    """),
                    {
                        'run_id': run_id,
                        'rows_logs': log_stats['processed'],
                        'rows_transfers': transfer_stats['processed'],
                        'anomalies': anomalies,
                    }
                )
                await session.commit()

                logger.info(f"Pipeline {run_id}: COMPLETED. Logs={log_stats['processed']}, "
                           f"Transfers={transfer_stats['processed']}, Anomalies={anomalies}")

            except Exception as e:
                logger.error(f"Pipeline {run_id}: FAILED — {str(e)}")
                await session.rollback()
                await session.execute(
                    text("""
                        UPDATE pipeline_runs SET
                            status = 'failed',
                            completed_at = NOW(),
                            error_message = :error
                        WHERE run_id = :run_id
                    """),
                    {'run_id': run_id, 'error': str(e)}
                )
                await session.commit()
                raise

    asyncio.run(_run())
    return {'run_id': run_id, 'status': 'completed'}
