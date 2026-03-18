"""Repository for transfer module DB access (async)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.audit_log import AuditLog
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.otp_verification import OtpVerification
from app.repository.models.transfer import Transfer
from app.repository.models.user import User


class TransferRepository:

    # ------------------------------------------------------------------
    # Account queries
    # ------------------------------------------------------------------

    async def get_account_by_number(
        self, db: AsyncSession, account_number: str
    ) -> Optional[Account]:
        res = await db.execute(
            select(Account).where(Account.account_number == account_number)
        )
        return res.scalar_one_or_none()

    async def get_account_by_phone(
        self, db: AsyncSession, phone: str
    ) -> Optional[Account]:
        """Lookup receiver account via their registered phone number."""
        res = await db.execute(
            select(Account)
            .join(User, Account.user_id == User.id)
            .where(User.phone == phone)
        )
        return res.scalar_one_or_none()

    async def get_user_by_id(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[User]:
        res = await db.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

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
            select(Account)
            .where(Account.id == account_id)
            .with_for_update()
        )
        return res.scalar_one_or_none()

    async def set_account_balance(
        self, db: AsyncSession, account_id: UUID, new_balance: Decimal
    ) -> None:
        """Set sender balance to an exact value (call only after SELECT FOR UPDATE)."""
        await db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(balance=new_balance)
        )
        await db.flush()

    async def credit_account_balance(
        self, db: AsyncSession, account_id: UUID, amount: Decimal
    ) -> Decimal:
        """Atomically add amount to receiver balance; returns the new balance."""
        result = await db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(balance=Account.balance + amount)
            .returning(Account.balance)
        )
        await db.flush()
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Transfer CRUD
    # ------------------------------------------------------------------

    async def create_transfer(
        self,
        db: AsyncSession,
        *,
        sender_account_id: UUID,
        receiver_account_id: UUID,
        amount: Decimal,
    ) -> Transfer:
        transfer = Transfer(
            sender_account_id=sender_account_id,
            receiver_account_id=receiver_account_id,
            amount=amount,
            status="PENDING",
        )
        db.add(transfer)
        await db.flush()
        return transfer

    async def get_transfer_by_id(
        self, db: AsyncSession, transfer_id: UUID
    ) -> Optional[Transfer]:
        res = await db.execute(
            select(Transfer).where(Transfer.id == transfer_id)
        )
        return res.scalar_one_or_none()

    async def update_transfer_status(
        self,
        db: AsyncSession,
        transfer_id: UUID,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> None:
        values: dict = {"status": status}
        if completed_at is not None:
            values["completed_at"] = completed_at
        await db.execute(
            update(Transfer).where(Transfer.id == transfer_id).values(**values)
        )
        await db.flush()

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
    # OTP (transfer-specific)
    # ------------------------------------------------------------------

    async def create_transfer_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        otp_hash: str,
        expires_at: datetime,
        transfer_id: UUID,
        max_attempts: int = 3,
    ) -> OtpVerification:
        """Create a TRANSFER OTP linked to a specific transfer via reference_id."""
        otp = OtpVerification(
            user_id=user_id,
            otp_hash=otp_hash,
            otp_type="TRANSFER",
            attempts=0,
            max_attempts=max_attempts,
            expires_at=expires_at,
            status="PENDING",
            reference_id=transfer_id,
        )
        db.add(otp)
        await db.flush()
        return otp

    async def get_valid_transfer_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        transfer_id: UUID,
        now: datetime,
    ) -> Optional[OtpVerification]:
        """Return the active PENDING OTP for this user+transfer, or None if expired/absent."""
        res = await db.execute(
            select(OtpVerification)
            .where(
                OtpVerification.user_id == user_id,
                OtpVerification.otp_type == "TRANSFER",
                OtpVerification.status == "PENDING",
                OtpVerification.reference_id == transfer_id,
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
