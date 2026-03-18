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
    """Async inner: mark loan ACTIVE, disburse amount to account, write ledger + audit."""
    # Deferred imports keep this module importable even before app init
    from sqlalchemy import select, update

    from app.repository.models.account import Account
    from app.repository.models.audit_log import AuditLog
    from app.repository.models.ledger_entry import LedgerEntry
    from app.repository.models.loan import Loan
    from app.repository.session import AsyncSessionLocal

    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # 1. Fetch loan (must be PENDING)
            res = await db.execute(select(Loan).where(Loan.id == loan_id))
            loan = res.scalar_one_or_none()

            if loan is None or loan.status != "PENDING":
                logger.warning(
                    "approve_loan_task: loan not in PENDING state",
                    extra={"loan_id": str(loan_id)},
                )
                return

            # 2. Mark loan ACTIVE
            await db.execute(
                update(Loan)
                .where(Loan.id == loan_id)
                .values(status="ACTIVE", approved_at=now, updated_at=now)
            )

            # 3. Credit principal amount to account (atomic)
            result = await db.execute(
                update(Account)
                .where(Account.id == loan.account_id)
                .values(balance=Account.balance + loan.principal_amount)
                .returning(Account.balance, Account.user_id)
            )
            row = result.one()
            new_balance = row[0]
            user_id = row[1]

            # 4. Ledger entry — CREDIT for loan disbursement
            db.add(LedgerEntry(
                account_id=loan.account_id,
                entry_type="CREDIT",
                amount=loan.principal_amount,
                balance_after=new_balance,
                reference_type="LOAN_DISBURSEMENT",
                reference_id=loan.id,
                description=f"Loan disbursement — principal ₹{loan.principal_amount}",
            ))

            # 5. Audit log
            db.add(AuditLog(
                user_id=user_id,
                session_id=None,
                event_type="LOAN_APPROVED",
                event_metadata={
                    "loan_id": str(loan_id),
                    "principal_amount": str(loan.principal_amount),
                    "account_id": str(loan.account_id),
                    "new_balance": str(new_balance),
                },
            ))

    logger.info(
        "Loan approved and disbursed",
        extra={"loan_id": str(loan_id), "amount": str(loan.principal_amount)},
    )
