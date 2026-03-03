"""Repository for user module DB access (async)."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.ledger_entry import LedgerEntry
from app.repository.models.user import User


class UserRepository:
    async def get_account_by_user_id(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[Account]:
        res = await db.execute(select(Account).where(Account.user_id == user_id))
        return res.scalar_one_or_none()

    async def get_recent_transactions(
        self,
        db: AsyncSession,
        account_id: UUID,
        limit: int = 5,
    ) -> List[LedgerEntry]:
        res = await db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def get_paginated_transactions(
        self,
        db: AsyncSession,
        account_id: UUID,
        offset: int,
        limit: int,
    ) -> Tuple[int, List[LedgerEntry]]:
        count_res = await db.execute(
            select(func.count(LedgerEntry.id)).where(
                LedgerEntry.account_id == account_id
            )
        )
        total: int = count_res.scalar_one()

        rows_res = await db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return total, list(rows_res.scalars().all())

    async def get_user_by_phone(
        self, db: AsyncSession, phone: str
    ) -> Optional[User]:
        res = await db.execute(select(User).where(User.phone == phone))
        return res.scalar_one_or_none()

    async def update_user_profile(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        phone: Optional[str] = None,
        address: Optional[str] = None,
    ) -> None:
        values: dict = {}
        if phone is not None:
            values["phone"] = phone
        if address is not None:
            values["address"] = address
        if values:
            await db.execute(
                update(User).where(User.id == user_id).values(**values)
            )
            await db.flush()
