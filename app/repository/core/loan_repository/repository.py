"""Repository for loan module DB access (async)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.loan import Loan
from app.repository.models.loan_simulation import LoanSimulation
from app.repository.models.otp_verification import OtpVerification


class LoanRepository:

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def get_account_by_user_id(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[Account]:
        res = await db.execute(
            select(Account).where(Account.user_id == user_id)
        )
        return res.scalar_one_or_none()

    async def get_account_for_update(
        self, db: AsyncSession, account_id: UUID
    ) -> Optional[Account]:
        """SELECT … FOR UPDATE — locks the row for the duration of the transaction."""
        res = await db.execute(
            select(Account).where(Account.id == account_id).with_for_update()
        )
        return res.scalar_one_or_none()

    async def debit_account_balance(
        self, db: AsyncSession, account_id: UUID, amount: Decimal
    ) -> Decimal:
        """Atomically subtract amount from balance; returns the new balance via RETURNING."""
        result = await db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(balance=Account.balance - amount)
            .returning(Account.balance)
        )
        await db.flush()
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Loan CRUD
    # ------------------------------------------------------------------

    async def create_loan(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        account_id: UUID,
        principal_amount: Decimal,
        interest_rate: Decimal,
        tenure_months: int,
        emi_amount: Decimal,
    ) -> Loan:
        loan = Loan(
            user_id=user_id,
            account_id=account_id,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            tenure_months=tenure_months,
            emi_amount=emi_amount,
            outstanding_amount=principal_amount,
            status="PENDING",
        )
        db.add(loan)
        await db.flush()
        return loan

    async def get_loan_by_id(
        self, db: AsyncSession, loan_id: UUID
    ) -> Optional[Loan]:
        res = await db.execute(select(Loan).where(Loan.id == loan_id))
        return res.scalar_one_or_none()

    async def get_loans_by_user_id(
        self, db: AsyncSession, user_id: UUID
    ) -> List[Loan]:
        res = await db.execute(
            select(Loan)
            .where(Loan.user_id == user_id)
            .order_by(Loan.created_at.desc())
        )
        return list(res.scalars().all())

    async def update_loan_outstanding(
        self,
        db: AsyncSession,
        loan_id: UUID,
        new_outstanding: Decimal,
        *,
        status: Optional[str] = None,
    ) -> None:
        values: dict = {"outstanding_amount": new_outstanding}
        if status is not None:
            values["status"] = status
        await db.execute(
            update(Loan).where(Loan.id == loan_id).values(**values)
        )
        await db.flush()

    # ------------------------------------------------------------------
    # Loan simulation
    # ------------------------------------------------------------------

    async def create_loan_simulation(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        session_id: UUID,
        tested_amount: Decimal,
        tested_tenure: int,
        calculated_emi: Decimal,
    ) -> LoanSimulation:
        sim = LoanSimulation(
            user_id=user_id,
            session_id=session_id,
            tested_amount=tested_amount,
            tested_tenure=tested_tenure,
            calculated_emi=calculated_emi,
        )
        db.add(sim)
        await db.flush()
        return sim

    # ------------------------------------------------------------------
    # Ledger
    # ------------------------------------------------------------------

    async def create_ledger_entry(
        self,
        db: AsyncSession,
        *,
        account_id: UUID,
        entry_type: str,
        amount: Decimal,
        balance_after: Decimal,
        reference_type: str,
        reference_id: UUID,
        description: str,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            account_id=account_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=balance_after,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )
        db.add(entry)
        await db.flush()
        return entry

    # ------------------------------------------------------------------
    # OTP (loan-booking specific)
    # ------------------------------------------------------------------

    async def create_loan_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        otp_hash: str,
        expires_at: datetime,
        booking_id: UUID,
        max_attempts: int = 3,
    ) -> OtpVerification:
        """Create a LOAN_BOOK OTP linked to a booking via reference_id."""
        otp = OtpVerification(
            user_id=user_id,
            otp_hash=otp_hash,
            otp_type="LOAN_BOOK",
            attempts=0,
            max_attempts=max_attempts,
            expires_at=expires_at,
            status="PENDING",
            reference_id=booking_id,
        )
        db.add(otp)
        await db.flush()
        return otp

    async def get_valid_loan_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        booking_id: UUID,
        now: datetime,
    ) -> Optional[OtpVerification]:
        """Return active PENDING OTP for this user+booking, or None if absent/expired."""
        res = await db.execute(
            select(OtpVerification)
            .where(
                OtpVerification.user_id == user_id,
                OtpVerification.otp_type == "LOAN_BOOK",
                OtpVerification.status == "PENDING",
                OtpVerification.reference_id == booking_id,
            )
            .order_by(OtpVerification.created_at.desc())
        )
        otp = res.scalar_one_or_none()
        if otp is None or otp.expires_at < now:
            return None
        return otp

    async def increment_otp_attempts(
        self, db: AsyncSession, otp: OtpVerification
    ) -> OtpVerification:
        otp.attempts = (otp.attempts or 0) + 1
        if otp.attempts >= (otp.max_attempts or 3):
            otp.status = "FAILED"
        await db.flush()
        return otp

    async def mark_otp_verified(self, db: AsyncSession, otp_id: UUID) -> None:
        await db.execute(
            update(OtpVerification)
            .where(OtpVerification.id == otp_id)
            .values(status="VERIFIED")
        )
        await db.flush()
