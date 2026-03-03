"""Loan service: eligibility, simulation, booking, confirmation, and repayment."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    AppException,
    insufficient_balance,
    invalid_otp,
    max_otp_attempts,
    not_found,
    otp_expired,
)
from app.common.utils.otp import generate_otp, hash_otp, send_otp_email
from app.config.redis import get_redis
from app.repository.core.loan_repository.repository import LoanRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOAN_INTEREST_RATE = Decimal("12.00")   # annual %
_LOAN_MAX_TENURE = 24                    # months
_BOOKING_TTL_SECONDS = 300               # 5 minutes


def _booking_key(booking_id: str) -> str:
    return f"loan_booking:{booking_id}"


def _calculate_emi(
    principal: Decimal, annual_rate: Decimal, tenure_months: int
) -> Decimal:
    """
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = annual_rate / 12 / 100 (monthly interest rate).
    """
    r = annual_rate / Decimal("12") / Decimal("100")
    if r == 0:
        return (principal / tenure_months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    factor = (1 + r) ** tenure_months
    emi = principal * r * factor / (factor - 1)
    return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _max_eligible(salary) -> Decimal:
    return Decimal(str(salary)) * 12


class LoanService:
    def __init__(self, repo: LoanRepository | None = None) -> None:
        self.repo = repo or LoanRepository()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        *,
        user_id: Optional[UUID],
        session_id: Optional[UUID],
        event_type: str,
        metadata: dict,
    ) -> AuditLog:
        return AuditLog(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_metadata=metadata,
        )

    def _check_eligibility(self, user: User, amount: Decimal | None = None) -> Decimal:
        """
        Validate salary > 0 and, optionally, that amount <= max_eligible.
        Returns max_eligible amount.
        Raises AppException(400) if not eligible.
        """
        if not user.salary or Decimal(str(user.salary)) <= 0:
            raise AppException(
                code="LOAN_NOT_ELIGIBLE",
                message="You are not eligible for a loan. Please update your salary information.",
                http_status=400,
            )
        max_amt = _max_eligible(user.salary)
        if amount is not None and amount > max_amt:
            raise AppException(
                code="LOAN_AMOUNT_EXCEEDS_ELIGIBLE",
                message=f"Requested amount exceeds your maximum eligible loan amount of INR {max_amt}.",
                http_status=400,
            )
        return max_amt

    # ------------------------------------------------------------------
    # GET /loan/eligibility
    # ------------------------------------------------------------------

    async def get_eligibility(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
    ) -> dict:
        max_amt = self._check_eligibility(user)
        return {
            "max_eligible_amount": str(max_amt.quantize(Decimal("0.01"))),
            "interest_rate": str(_LOAN_INTEREST_RATE),
            "max_tenure_months": _LOAN_MAX_TENURE,
        }

    # ------------------------------------------------------------------
    # POST /loan/simulate
    # ------------------------------------------------------------------

    async def simulate(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        amount: Decimal,
        tenure_months: int,
    ) -> dict:
        self._check_eligibility(user, amount)
        emi = _calculate_emi(amount, _LOAN_INTEREST_RATE, tenure_months)
        total_payable = (emi * tenure_months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        async with db.begin():
            await self.repo.create_loan_simulation(
                db,
                user_id=user.id,
                session_id=session_id,
                tested_amount=amount,
                tested_tenure=tenure_months,
                calculated_emi=emi,
            )

        return {
            "amount": str(amount),
            "tenure_months": tenure_months,
            "interest_rate": str(_LOAN_INTEREST_RATE),
            "emi_amount": str(emi),
            "total_payable": str(total_payable),
        }

    # ------------------------------------------------------------------
    # POST /loan/book
    # ------------------------------------------------------------------

    async def book_loan(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        amount: Decimal,
        tenure_months: int,
    ) -> dict:
        self._check_eligibility(user, amount)

        # Fetch account to store account_id in Redis booking
        account = await self.repo.get_account_by_user_id(db, user.id)
        if account is None:
            raise not_found("Account")

        emi = _calculate_emi(amount, _LOAN_INTEREST_RATE, tenure_months)
        booking_id = str(uuid.uuid4())

        booking_data = json.dumps({
            "user_id": str(user.id),
            "account_id": str(account.id),
            "amount": str(amount),
            "tenure_months": tenure_months,
            "emi_amount": str(emi),
        })

        # Persist booking in Redis with TTL
        redis = get_redis()
        await asyncio.to_thread(
            lambda: redis.set(_booking_key(booking_id), booking_data, ex=_BOOKING_TTL_SECONDS)
        )

        # Generate OTP and persist in DB
        otp_plain = generate_otp()
        otp_hash = hash_otp(otp_plain)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        async with db.begin():
            await self.repo.create_loan_otp(
                db,
                user_id=user.id,
                otp_hash=otp_hash,
                expires_at=expires_at,
                booking_id=UUID(booking_id),
            )
            db.add(
                self._audit(
                    user_id=user.id,
                    session_id=session_id,
                    event_type="LOAN_BOOK_INITIATED",
                    metadata={
                        "booking_id": booking_id,
                        "amount": str(amount),
                        "tenure_months": tenure_months,
                    },
                )
            )

        # Send OTP (best-effort)
        try:
            await send_otp_email(user.email, otp_plain, otp_type="LOAN_BOOK")
        except Exception:
            logger.exception(
                "Failed to send loan booking OTP email",
                extra={"user_id": str(user.id)},
            )

        return {
            "booking_id": booking_id,
            "message": "OTP sent to your registered email. Please confirm within 5 minutes.",
        }

    # ------------------------------------------------------------------
    # POST /loan/confirm
    # ------------------------------------------------------------------

    async def confirm_loan(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        booking_id: str,
        otp: str,
    ) -> dict:
        # Retrieve booking from Redis
        redis = get_redis()
        raw = await asyncio.to_thread(redis.get, _booking_key(booking_id))
        if raw is None:
            raise AppException(
                code="LOAN_BOOKING_EXPIRED",
                message="Loan booking has expired. Please start a new booking.",
                http_status=410,
            )
        booking = json.loads(raw)

        # Ownership check
        if booking["user_id"] != str(user.id):
            raise not_found("Loan booking")

        booking_uuid = UUID(booking_id)
        now = datetime.utcnow()

        # Validate OTP
        otp_record = await self.repo.get_valid_loan_otp(
            db, user_id=user.id, booking_id=booking_uuid, now=now
        )
        if otp_record is None:
            raise otp_expired()

        if otp_record.otp_hash != hash_otp(otp):
            otp_record = await self.repo.increment_otp_attempts(db, otp_record)
            if otp_record.status == "FAILED":
                raise max_otp_attempts()
            raise invalid_otp()

        # Atomically create loan + mark OTP verified + audit
        async with db.begin():
            loan = await self.repo.create_loan(
                db,
                user_id=user.id,
                account_id=UUID(booking["account_id"]),
                principal_amount=Decimal(booking["amount"]),
                interest_rate=_LOAN_INTEREST_RATE,
                tenure_months=int(booking["tenure_months"]),
                emi_amount=Decimal(booking["emi_amount"]),
            )
            await self.repo.mark_otp_verified(db, otp_record.id)
            db.add(
                self._audit(
                    user_id=user.id,
                    session_id=session_id,
                    event_type="LOAN_CONFIRMED",
                    metadata={
                        "loan_id": str(loan.id),
                        "booking_id": booking_id,
                        "amount": booking["amount"],
                        "tenure_months": booking["tenure_months"],
                    },
                )
            )

        # Clean up booking key
        await asyncio.to_thread(redis.delete, _booking_key(booking_id))

        # Dispatch background approval task
        from app.tasks.loan_tasks import approve_loan_task
        approve_loan_task.delay(str(loan.id))

        return {
            "loan_id": str(loan.id),
            "principal_amount": str(loan.principal_amount),
            "emi_amount": str(loan.emi_amount),
            "tenure_months": loan.tenure_months,
            "status": loan.status,
            "message": "Loan application submitted successfully. Approval is in progress.",
        }

    # ------------------------------------------------------------------
    # GET /loan/list
    # ------------------------------------------------------------------

    async def get_loans(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict:
        loans = await self.repo.get_loans_by_user_id(db, user_id)
        items = [
            {
                "id": str(loan.id),
                "principal_amount": str(loan.principal_amount),
                "emi_amount": str(loan.emi_amount),
                "outstanding_amount": str(loan.outstanding_amount),
                "interest_rate": str(loan.interest_rate),
                "tenure_months": loan.tenure_months,
                "status": loan.status,
                "created_at": loan.created_at.isoformat(),
                "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
            }
            for loan in loans
        ]
        return {"loans": items}

    # ------------------------------------------------------------------
    # POST /loan/{loan_id}/pay
    # ------------------------------------------------------------------

    async def pay_loan(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        loan_id: UUID,
    ) -> dict:
        loan = await self.repo.get_loan_by_id(db, loan_id)
        if loan is None or loan.user_id != user.id:
            raise not_found("Loan")

        if loan.status != "ACTIVE":
            raise AppException(
                code="LOAN_NOT_ACTIVE",
                message="Loan is not active and cannot accept payments.",
                http_status=400,
            )

        # Pay the smaller of EMI or remaining outstanding
        payment_amount = min(loan.emi_amount, loan.outstanding_amount)

        async with db.begin():
            # Lock the account row
            account = await self.repo.get_account_for_update(db, loan.account_id)
            if account is None:
                raise not_found("Account")

            if account.balance < payment_amount:
                raise insufficient_balance(
                    "Insufficient wallet balance to pay loan EMI. Please add money first."
                )

            # Atomic debit + new balance via RETURNING
            new_balance = await self.repo.debit_account_balance(
                db, account.id, payment_amount
            )

            # Update loan outstanding; close if fully repaid
            new_outstanding = loan.outstanding_amount - payment_amount
            new_status = "CLOSED" if new_outstanding <= 0 else "ACTIVE"
            await self.repo.update_loan_outstanding(
                db, loan.id, new_outstanding, status=new_status
            )

            # Ledger entry
            await self.repo.create_ledger_entry(
                db,
                account_id=account.id,
                entry_type="DEBIT",
                amount=payment_amount,
                balance_after=new_balance,
                reference_type="LOAN_PAYMENT",
                reference_id=loan.id,
                description=f"EMI payment for loan {loan.id}",
            )

            db.add(
                self._audit(
                    user_id=user.id,
                    session_id=session_id,
                    event_type="LOAN_PAYMENT_MADE",
                    metadata={
                        "loan_id": str(loan.id),
                        "amount_paid": str(payment_amount),
                        "outstanding_after": str(new_outstanding),
                        "loan_status": new_status,
                    },
                )
            )

        return {
            "loan_id": str(loan.id),
            "amount_paid": str(payment_amount),
            "outstanding_after": str(new_outstanding),
            "loan_status": new_status,
        }
