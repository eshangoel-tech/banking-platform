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
from app.config.bank_rules.bank_rules import (
    LOAN_ALLOWED_TENURES,
    LOAN_BOOKING_REDIS_TTL_SECONDS,
    LOAN_INTEREST_RATE_PA,
    LOAN_MIN_AMOUNT,
    LOAN_MIN_SALARY,
    LOAN_PROCESSING_FEE_PERCENT,
)
from app.config.redis import get_redis
from app.repository.core.loan_repository.repository import LoanRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (sourced from bank_rules.json via bank_rules.py)
# ---------------------------------------------------------------------------

_LOAN_INTEREST_RATE = Decimal(str(LOAN_INTEREST_RATE_PA * 100))  # 0.12 → 12.00 annual %
_LOAN_ALLOWED_TENURES = LOAN_ALLOWED_TENURES
_LOAN_MIN_AMOUNT = Decimal(str(LOAN_MIN_AMOUNT))
_LOAN_MIN_SALARY = Decimal(str(LOAN_MIN_SALARY))
_BOOKING_TTL_SECONDS = LOAN_BOOKING_REDIS_TTL_SECONDS


def _booking_key(booking_id: str) -> str:
    return f"loan_booking:{booking_id}"


def _pay_key(pay_id: str) -> str:
    return f"loan_pay:{pay_id}"


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

    def _check_salary_eligible(self, user: User) -> Decimal:
        """Validate salary >= min_salary. Returns max_eligible amount."""
        if not user.salary or Decimal(str(user.salary)) < _LOAN_MIN_SALARY:
            raise AppException(
                code="LOAN_NOT_ELIGIBLE",
                message=f"You are not eligible for a loan. Minimum monthly salary required is INR {_LOAN_MIN_SALARY}.",
                http_status=400,
            )
        return _max_eligible(user.salary)

    async def _check_eligibility(
        self, db: AsyncSession, user: User, amount: Decimal | None = None
    ) -> tuple[Decimal, Decimal]:
        """
        Validate salary and existing loans. Returns (max_eligible, available_amount).
        available_amount = max_eligible - total_outstanding_on_active_loans.
        Raises AppException(400) if not eligible or amount not feasible.
        """
        max_amt = self._check_salary_eligible(user)
        total_outstanding = await self.repo.get_total_outstanding_by_user(db, user.id)
        available = max(Decimal("0"), max_amt - total_outstanding)

        if amount is not None:
            if amount < _LOAN_MIN_AMOUNT:
                raise AppException(
                    code="LOAN_AMOUNT_TOO_LOW",
                    message=f"Minimum loan amount is INR {_LOAN_MIN_AMOUNT}.",
                    http_status=400,
                )
            if amount > available:
                raise AppException(
                    code="LOAN_AMOUNT_EXCEEDS_ELIGIBLE",
                    message=(
                        f"Requested amount exceeds your available loan limit of INR {available}. "
                        f"You have INR {total_outstanding} outstanding across existing loans."
                    ),
                    http_status=400,
                )
        return max_amt, available

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
        max_amt, available = await self._check_eligibility(db, user)
        total_outstanding = max_amt - available  # = sum of active+pending loans
        return {
            "min_loan_amount": str(_LOAN_MIN_AMOUNT),
            "max_eligible_amount": str(max_amt.quantize(Decimal("0.01"))),
            "existing_loan_outstanding": str(total_outstanding.quantize(Decimal("0.01"))),
            "available_loan_amount": str(available.quantize(Decimal("0.01"))),
            "allowed_tenures": _LOAN_ALLOWED_TENURES,
            "interest_rate": str(_LOAN_INTEREST_RATE),
            "processing_fee_percent": LOAN_PROCESSING_FEE_PERCENT,
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
        await self._check_eligibility(db, user, amount)
        emi = _calculate_emi(amount, _LOAN_INTEREST_RATE, tenure_months)
        total_payable = (emi * tenure_months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        await self.repo.create_loan_simulation(
            db,
            user_id=user.id,
            session_id=session_id,
            tested_amount=amount,
            tested_tenure=tenure_months,
            calculated_emi=emi,
        )
        await db.commit()

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
        await self._check_eligibility(db, user, amount)

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
        await db.commit()

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
        await db.commit()

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
    # POST /loan/{loan_id}/pay/initiate  (Step 1)
    # ------------------------------------------------------------------

    async def initiate_pay_loan(
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

        payment_amount = min(loan.emi_amount, loan.outstanding_amount)

        # Pre-flight balance check (no lock — just informational)
        account = await self.repo.get_account_by_user_id(db, user.id)
        if account is None:
            raise not_found("Account")
        if account.balance < payment_amount:
            raise insufficient_balance(
                "Insufficient wallet balance to pay loan EMI. Please add money first."
            )

        # Store pay session in Redis (5-min TTL)
        pay_id = str(uuid.uuid4())
        pay_data = json.dumps({
            "user_id": str(user.id),
            "loan_id": str(loan_id),
            "account_id": str(loan.account_id),
            "payment_amount": str(payment_amount),
        })
        redis = get_redis()
        await asyncio.to_thread(
            lambda: redis.set(_pay_key(pay_id), pay_data, ex=_BOOKING_TTL_SECONDS)
        )

        # Generate OTP
        otp_plain = generate_otp()
        otp_hash = hash_otp(otp_plain)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        await self.repo.create_emi_pay_otp(
            db,
            user_id=user.id,
            otp_hash=otp_hash,
            expires_at=expires_at,
            pay_id=UUID(pay_id),
        )
        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="LOAN_PAY_INITIATED",
                metadata={
                    "pay_id": pay_id,
                    "loan_id": str(loan_id),
                    "payment_amount": str(payment_amount),
                },
            )
        )
        await db.commit()

        # Send OTP email (best-effort)
        try:
            await send_otp_email(user.email, otp_plain, otp_type="LOAN_PAY")
        except Exception:
            logger.exception(
                "Failed to send EMI pay OTP email",
                extra={"user_id": str(user.id)},
            )

        return {
            "pay_id": pay_id,
            "emi_amount": str(payment_amount),
            "outstanding_amount": str(loan.outstanding_amount),
            "message": "OTP sent to your registered email. Please confirm within 5 minutes.",
        }

    # ------------------------------------------------------------------
    # POST /loan/{loan_id}/pay/confirm  (Step 2)
    # ------------------------------------------------------------------

    async def confirm_pay_loan(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        loan_id: UUID,
        pay_id: str,
        otp: str,
    ) -> dict:
        # Retrieve pay session from Redis
        redis = get_redis()
        raw = await asyncio.to_thread(redis.get, _pay_key(pay_id))
        if raw is None:
            raise AppException(
                code="LOAN_PAY_EXPIRED",
                message="Payment session has expired. Please initiate a new EMI payment.",
                http_status=410,
            )
        pay_data = json.loads(raw)

        if pay_data["user_id"] != str(user.id) or pay_data["loan_id"] != str(loan_id):
            raise not_found("Payment session")

        pay_uuid = UUID(pay_id)
        now = datetime.utcnow()

        # Validate OTP
        otp_record = await self.repo.get_valid_emi_pay_otp(
            db, user_id=user.id, pay_id=pay_uuid, now=now
        )
        if otp_record is None:
            raise otp_expired()

        if otp_record.otp_hash != hash_otp(otp):
            otp_record = await self.repo.increment_otp_attempts(db, otp_record)
            if otp_record.status == "FAILED":
                raise max_otp_attempts()
            raise invalid_otp()

        payment_amount = Decimal(pay_data["payment_amount"])
        account_id = UUID(pay_data["account_id"])

        # Lock account row for atomic debit
        account = await self.repo.get_account_for_update(db, account_id)
        if account is None:
            raise not_found("Account")
        if account.balance < payment_amount:
            raise insufficient_balance(
                "Insufficient wallet balance to pay loan EMI. Please add money first."
            )

        # Atomic debit
        new_balance = await self.repo.debit_account_balance(db, account_id, payment_amount)

        # Fetch current loan outstanding
        loan = await self.repo.get_loan_by_id(db, loan_id)
        new_outstanding = loan.outstanding_amount - payment_amount
        new_status = "CLOSED" if new_outstanding <= 0 else "ACTIVE"

        await self.repo.update_loan_outstanding(db, loan_id, new_outstanding, status=new_status)

        await self.repo.create_ledger_entry(
            db,
            account_id=account_id,
            entry_type="DEBIT",
            amount=payment_amount,
            balance_after=new_balance,
            reference_type="LOAN_PAYMENT",
            reference_id=loan_id,
            description=f"EMI payment for loan {loan_id}",
        )

        await self.repo.mark_otp_verified(db, otp_record.id)

        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="LOAN_PAYMENT_MADE",
                metadata={
                    "loan_id": str(loan_id),
                    "pay_id": pay_id,
                    "amount_paid": str(payment_amount),
                    "outstanding_after": str(new_outstanding),
                    "loan_status": new_status,
                },
            )
        )
        await db.commit()

        # Clean up Redis session
        await asyncio.to_thread(redis.delete, _pay_key(pay_id))

        return {
            "loan_id": str(loan_id),
            "amount_paid": str(payment_amount),
            "outstanding_after": str(new_outstanding),
            "loan_status": new_status,
        }
