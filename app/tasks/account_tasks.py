"""Celery tasks for account on-boarding: joining bonus and salary credit."""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from uuid import UUID

from app.config.celery import celery_app

logger = logging.getLogger(__name__)

_JOINING_BONUS = Decimal("500.00")


# ---------------------------------------------------------------------------
# Task 1: triggered immediately after email verification
# ---------------------------------------------------------------------------

@celery_app.task(
    name="on_email_verified_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def on_email_verified_task(self, user_id: str, account_id: str) -> None:
    """
    Credit ₹500 joining bonus, send a welcome email, then schedule the
    salary-credit task to fire 2 minutes later.
    """
    try:
        asyncio.run(_do_joining_bonus(UUID(user_id), UUID(account_id)))
    except Exception as exc:
        logger.exception(
            "on_email_verified_task failed — retrying",
            extra={"user_id": user_id, "attempt": self.request.retries},
        )
        raise self.retry(exc=exc)

    # Schedule salary credit 2 minutes later (120 s)
    credit_monthly_salary_task.apply_async(
        args=[user_id, account_id],
        countdown=120,
    )


async def _do_joining_bonus(user_id: UUID, account_id: UUID) -> None:
    """Credit joining bonus, create ledger entry, write audit log, send welcome email."""
    from sqlalchemy import select, update
    from app.repository.session import AsyncSessionLocal
    from app.repository.models.account import Account
    from app.repository.models.audit_log import AuditLog
    from app.repository.models.ledger_entry import LedgerEntry
    from app.repository.models.user import User
    from app.common.utils.otp import send_welcome_email

    # Capture plain Python values inside the session before it closes
    user_email: str | None = None
    user_full_name: str | None = None
    account_number: str | None = None

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Lock account row
            res = await db.execute(
                select(Account).where(Account.id == account_id).with_for_update()
            )
            account = res.scalar_one_or_none()
            if account is None:
                logger.error(
                    "on_email_verified_task: account not found",
                    extra={"account_id": str(account_id)},
                )
                return

            # Read account_number while session is open
            account_number = account.account_number

            # Credit bonus
            result = await db.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(balance=Account.balance + _JOINING_BONUS)
                .returning(Account.balance)
            )
            new_balance = result.scalar_one()

            # Ledger entry
            db.add(
                LedgerEntry(
                    account_id=account_id,
                    entry_type="CREDIT",
                    amount=_JOINING_BONUS,
                    balance_after=new_balance,
                    reference_type="JOINING_BONUS",
                    reference_id=account_id,
                    description="Welcome joining bonus — ₹500 credited to your account",
                )
            )

            # Audit log
            db.add(
                AuditLog(
                    user_id=user_id,
                    session_id=None,
                    event_type="JOINING_BONUS_CREDITED",
                    event_metadata={
                        "amount": str(_JOINING_BONUS),
                        "account_id": str(account_id),
                        "balance_after": str(new_balance),
                    },
                )
            )

            # Load user for email — capture values as primitives before session closes
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()
            if user is not None:
                user_email = user.email
                user_full_name = user.full_name
        # session committed and closed here — do NOT access ORM objects below

    logger.info(
        "Joining bonus credited",
        extra={"user_id": str(user_id), "amount": str(_JOINING_BONUS)},
    )

    # Send welcome email outside transaction (best-effort) using captured primitives
    if user_email and user_full_name and account_number:
        try:
            await send_welcome_email(
                to_email=user_email,
                full_name=user_full_name,
                account_number=account_number,
                bonus_amount=_JOINING_BONUS,
            )
        except Exception:
            logger.exception(
                "Failed to send welcome email",
                extra={"user_id": str(user_id)},
            )


# ---------------------------------------------------------------------------
# Task 2: fires 2 minutes after Task 1
# ---------------------------------------------------------------------------

@celery_app.task(
    name="credit_monthly_salary_task",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def credit_monthly_salary_task(self, user_id: str, account_id: str) -> None:
    """
    Credit the user's declared monthly salary to their account and send
    a congratulatory email.
    """
    try:
        asyncio.run(_do_salary_credit(UUID(user_id), UUID(account_id)))
    except Exception as exc:
        logger.exception(
            "credit_monthly_salary_task failed — retrying",
            extra={"user_id": user_id, "attempt": self.request.retries},
        )
        raise self.retry(exc=exc)


async def _do_salary_credit(user_id: UUID, account_id: UUID) -> None:
    """Credit user's salary, create ledger entry, write audit log, send email."""
    from sqlalchemy import select, update
    from app.repository.session import AsyncSessionLocal
    from app.repository.models.account import Account
    from app.repository.models.audit_log import AuditLog
    from app.repository.models.ledger_entry import LedgerEntry
    from app.repository.models.user import User
    from app.common.utils.otp import send_salary_credit_email

    # Capture plain Python values inside the session before it closes
    user_email: str | None = None
    user_full_name: str | None = None
    salary: Decimal | None = None

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Load user to get salary + email — capture as primitives
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()
            if user is None:
                logger.error(
                    "credit_monthly_salary_task: user not found",
                    extra={"user_id": str(user_id)},
                )
                return

            if not user.salary or user.salary <= 0:
                logger.info(
                    "credit_monthly_salary_task: no salary on record — skipping",
                    extra={"user_id": str(user_id)},
                )
                return

            # Capture primitives before commit expires the ORM object
            user_email = user.email
            user_full_name = user.full_name
            salary = Decimal(str(user.salary))

            # Lock account
            res = await db.execute(
                select(Account).where(Account.id == account_id).with_for_update()
            )
            account = res.scalar_one_or_none()
            if account is None:
                logger.error(
                    "credit_monthly_salary_task: account not found",
                    extra={"account_id": str(account_id)},
                )
                return

            # Credit salary
            result = await db.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(balance=Account.balance + salary)
                .returning(Account.balance)
            )
            new_balance = result.scalar_one()

            # Ledger entry
            db.add(
                LedgerEntry(
                    account_id=account_id,
                    entry_type="CREDIT",
                    amount=salary,
                    balance_after=new_balance,
                    reference_type="SALARY_CREDIT",
                    reference_id=account_id,
                    description=f"Monthly salary credit — ₹{salary}",
                )
            )

            # Audit log
            db.add(
                AuditLog(
                    user_id=user_id,
                    session_id=None,
                    event_type="SALARY_CREDITED",
                    event_metadata={
                        "amount": str(salary),
                        "account_id": str(account_id),
                        "balance_after": str(new_balance),
                    },
                )
            )
        # session committed and closed here — do NOT access ORM objects below

    logger.info(
        "Salary credited",
        extra={"user_id": str(user_id), "amount": str(salary)},
    )

    # Send congratulations email (best-effort) using captured primitives
    if user_email and user_full_name and salary:
        try:
            await send_salary_credit_email(
                to_email=user_email,
                full_name=user_full_name,
                salary_amount=salary,
            )
        except Exception:
            logger.exception(
                "Failed to send salary credit email",
                extra={"user_id": str(user_id)},
            )
