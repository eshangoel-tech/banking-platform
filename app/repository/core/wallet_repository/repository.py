"""Repository for wallet / add-money module DB access (async)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.otp_verification import OtpVerification


class WalletRepository:

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

    async def credit_account_balance(
        self, db: AsyncSession, account_id: UUID, amount: Decimal
    ) -> Decimal:
        """Atomically add amount to balance; returns the new balance via RETURNING."""
        result = await db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(balance=Account.balance + amount)
            .returning(Account.balance)
        )
        await db.flush()
        return result.scalar_one()

    # ------------------------------------------------------------------
    # OTP helpers (for ADD_MONEY flow)
    # ------------------------------------------------------------------

    async def get_valid_topup_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        topup_id: UUID,
        now: datetime,
    ) -> Optional[OtpVerification]:
        """Fetch a PENDING ADD_MONEY OTP matching user + topup reference."""
        res = await db.execute(
            select(OtpVerification)
            .where(
                OtpVerification.user_id == user_id,
                OtpVerification.otp_type == "ADD_MONEY",
                OtpVerification.reference_id == topup_id,
                OtpVerification.status == "PENDING",
            )
            .order_by(OtpVerification.created_at.desc())
        )
        otp = res.scalar_one_or_none()
        if not otp:
            return None
        if otp.expires_at < now:
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
