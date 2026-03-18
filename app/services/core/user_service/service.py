"""User service: dashboard, account details, transactions, and profile management."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import not_found, user_already_exists
from app.repository.core.user_repository.repository import UserRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.user import User

logger = logging.getLogger(__name__)

_MAX_LIMIT = 50


def _mask(account_number: str) -> str:
    """Return account number with all but the last 4 digits replaced by '*'."""
    if len(account_number) <= 4:
        return account_number
    return "*" * (len(account_number) - 4) + account_number[-4:]


def _dec(value) -> str:
    return str(value) if value is not None else "0.00"


def _dt(dt) -> str:
    return dt.isoformat() if dt else ""


class UserService:
    def __init__(self, repo: UserRepository | None = None) -> None:
        self.repo = repo or UserRepository()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        event_type: str,
        metadata: dict,
    ) -> AuditLog:
        return AuditLog(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    async def get_dashboard_summary(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
    ) -> dict:
        account = await self.repo.get_account_by_user_id(db, user.id)
        if not account:
            raise not_found("Account")

        transactions = await self.repo.get_recent_transactions(
            db, account.id, limit=5
        )

        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="DASHBOARD_VIEWED",
                metadata={},
            )
        )
        await db.commit()

        return {
            "user": {
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
            },
            "account": {
                "account_number_masked": _mask(account.account_number),
                "balance": _dec(account.balance),
                "account_type": account.account_type,
                "currency": account.currency,
                "status": account.status,
            },
            "recent_transactions": [
                {
                    "id": str(t.id),
                    "entry_type": t.entry_type,
                    "amount": _dec(t.amount),
                    "balance_after": _dec(t.balance_after),
                    "reference_type": t.reference_type,
                    "description": t.description,
                    "created_at": _dt(t.created_at),
                }
                for t in transactions
            ],
        }

    # ------------------------------------------------------------------
    # Account details
    # ------------------------------------------------------------------

    async def get_account_details(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> dict:
        account = await self.repo.get_account_by_user_id(db, user_id)
        if not account:
            raise not_found("Account")

        db.add(
            self._audit(
                user_id=user_id,
                session_id=session_id,
                event_type="ACCOUNT_DETAILS_VIEWED",
                metadata={"account_id": str(account.id)},
            )
        )
        await db.commit()

        return {
            "account_number": account.account_number,
            "account_type": account.account_type,
            "balance": _dec(account.balance),
            "currency": account.currency,
            "status": account.status,
            "created_at": _dt(account.created_at),
        }

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    async def get_transactions(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        session_id: UUID,
        page: int,
        limit: int,
    ) -> dict:
        limit = min(limit, _MAX_LIMIT)
        offset = (page - 1) * limit

        account = await self.repo.get_account_by_user_id(db, user_id)
        if not account:
            raise not_found("Account")

        total, rows = await self.repo.get_paginated_transactions(
            db, account.id, offset=offset, limit=limit
        )

        db.add(
            self._audit(
                user_id=user_id,
                session_id=session_id,
                event_type="TRANSACTIONS_VIEWED",
                metadata={"page": page, "limit": limit},
            )
        )
        await db.commit()

        return {
            "total_records": total,
            "page": page,
            "limit": limit,
            "transactions": [
                {
                    "id": str(t.id),
                    "entry_type": t.entry_type,
                    "amount": _dec(t.amount),
                    "balance_after": _dec(t.balance_after),
                    "reference_type": t.reference_type,
                    "description": t.description,
                    "created_at": _dt(t.created_at),
                }
                for t in rows
            ],
        }

    # ------------------------------------------------------------------
    # Profile update
    # ------------------------------------------------------------------

    async def get_profile(self, user: User) -> dict:
        return {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "salary": str(user.salary) if user.salary else None,
            "kyc_status": user.kyc_status,
            "address": user.address,  # already a dict (JSONB)
        }

    async def update_profile(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        phone: Optional[str],
        address: Optional[dict],
    ) -> None:
        phone_changed = phone is not None and phone != user.phone
        address_changed = address is not None

        if phone_changed:
            existing = await self.repo.get_user_by_phone(db, phone)  # type: ignore[arg-type]
            if existing is not None and existing.id != user.id:
                raise user_already_exists("Phone number already in use")

        await self.repo.update_user_profile(
            db,
            user.id,
            phone=phone if phone_changed else None,
            address=address if address_changed else None,
        )
        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="PROFILE_UPDATED",
                metadata={
                    "phone_changed": phone_changed,
                    "address_changed": address_changed,
                },
            )
        )
        await db.commit()
