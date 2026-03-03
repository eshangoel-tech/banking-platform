"""Repository for wallet / add-money module DB access (async)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.audit_log import AuditLog
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.payment_order import PaymentOrder


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
    # PaymentOrder CRUD
    # ------------------------------------------------------------------

    async def create_payment_order(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        account_id: UUID,
        razorpay_order_id: str,
        amount_requested: Decimal,
        currency: str = "INR",
    ) -> PaymentOrder:
        order = PaymentOrder(
            user_id=user_id,
            account_id=account_id,
            razorpay_order_id=razorpay_order_id,
            amount_requested=amount_requested,
            currency=currency,
            status="CREATED",
        )
        db.add(order)
        await db.flush()
        return order

    async def get_payment_order_by_razorpay_id(
        self, db: AsyncSession, razorpay_order_id: str
    ) -> Optional[PaymentOrder]:
        res = await db.execute(
            select(PaymentOrder).where(
                PaymentOrder.razorpay_order_id == razorpay_order_id
            )
        )
        return res.scalar_one_or_none()

    async def update_payment_status(
        self,
        db: AsyncSession,
        order_id: UUID,
        status: str,
        *,
        amount_paid: Optional[Decimal] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        values: dict = {"status": status}
        if amount_paid is not None:
            values["amount_paid"] = amount_paid
        if completed_at is not None:
            values["completed_at"] = completed_at
        await db.execute(
            update(PaymentOrder).where(PaymentOrder.id == order_id).values(**values)
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
