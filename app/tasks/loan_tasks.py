"""Celery tasks for the loan module."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from app.config.celery import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="approve_loan_task", bind=True, max_retries=3, default_retry_delay=10)
def approve_loan_task(self, loan_id: str) -> None:
    """
    Auto-approve a pending loan and transition it to ACTIVE.

    Runs as a synchronous Celery task; uses asyncio.run() to invoke async
    SQLAlchemy operations via the existing AsyncSessionLocal factory.

    Retries up to 3 times (10-second backoff) on transient failures.
    """
    try:
        asyncio.run(_do_approve(UUID(loan_id)))
    except Exception as exc:
        logger.exception(
            "approve_loan_task failed — retrying",
            extra={"loan_id": loan_id, "attempt": self.request.retries},
        )
        raise self.retry(exc=exc)


async def _do_approve(loan_id: UUID) -> None:
    """Async inner: mark loan ACTIVE and write audit log."""
    # Deferred imports keep this module importable even before app init
    from app.repository.session import AsyncSessionLocal
    from app.repository.models.audit_log import AuditLog
    from app.repository.models.loan import Loan
    from sqlalchemy import update

    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                update(Loan)
                .where(Loan.id == loan_id, Loan.status == "PENDING")
                .values(status="ACTIVE", approved_at=now, updated_at=now)
                .returning(Loan.id)
            )
            updated = result.scalar_one_or_none()
            if updated is None:
                # Loan already approved / cancelled — idempotent exit
                logger.warning(
                    "approve_loan_task: loan not in PENDING state",
                    extra={"loan_id": str(loan_id)},
                )
                return

            db.add(
                AuditLog(
                    user_id=None,
                    session_id=None,
                    event_type="LOAN_APPROVED",
                    event_metadata={"loan_id": str(loan_id)},
                )
            )

    logger.info("Loan approved", extra={"loan_id": str(loan_id)})
