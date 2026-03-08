"""Wallet service: OTP-based add-money (initiate + confirm)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    account_not_active,
    invalid_otp,
    max_otp_attempts,
    not_found,
    otp_expired,
    topup_not_found,
)
from app.common.utils.otp import generate_otp, hash_otp, send_otp_email, verify_otp_hash
from app.config.redis import get_redis
from app.config.bank_rules import ADD_MONEY_MAX_AMOUNT, ADD_MONEY_REDIS_TTL_SECONDS
from app.repository.core.wallet_repository.repository import WalletRepository
from app.repository.models.audit_log import AuditLog
from app.repository.models.otp_verification import OtpVerification
from app.repository.models.user import User

logger = logging.getLogger(__name__)

_OTP_TTL_MINUTES = 5
_REDIS_KEY_PREFIX = "wallet_topup:"

_OTP_SUBJECTS = {
    "ADD_MONEY": "ADX Bank — Add Money OTP",
}


class WalletService:
    def __init__(self, repo: WalletRepository | None = None) -> None:
        self.repo = repo or WalletRepository()

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

    def _redis_key(self, topup_id: UUID) -> str:
        return f"{_REDIS_KEY_PREFIX}{topup_id}"

    # ------------------------------------------------------------------
    # Step 1: initiate add-money
    # ------------------------------------------------------------------

    async def initiate_add_money(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        amount: Decimal,
    ) -> dict:
        """
        Validate the request, store top-up details in Redis, generate and
        send an OTP, and return the topup_id the frontend uses in /confirm.
        """
        if amount > ADD_MONEY_MAX_AMOUNT:
            from app.common.utils.exceptions import payment_limit_exceeded
            raise payment_limit_exceeded()

        # -- Fetch and validate account
        account = await self.repo.get_account_by_user_id(db, user.id)
        if not account:
            raise not_found("Account")
        if account.status != "ACTIVE":
            raise account_not_active()

        # -- Generate topup_id (serves as both the Redis key and OTP reference)
        topup_id = uuid.uuid4()

        # -- Store top-up context in Redis (TTL matches OTP expiry)
        redis = get_redis()
        redis.setex(
            self._redis_key(topup_id),
            ADD_MONEY_REDIS_TTL_SECONDS,
            json.dumps({
                "user_id": str(user.id),
                "account_id": str(account.id),
                "amount": str(amount),
                "currency": "INR",
            }),
        )

        # -- Generate OTP and persist
        otp_plaintext = generate_otp()
        otp_hash_value = hash_otp(otp_plaintext)
        expires_at = datetime.utcnow() + timedelta(minutes=_OTP_TTL_MINUTES)

        otp_record = OtpVerification(
            user_id=user.id,
            otp_hash=otp_hash_value,
            otp_type="ADD_MONEY",
            reference_id=topup_id,
            attempts=0,
            max_attempts=3,
            expires_at=expires_at,
            status="PENDING",
        )
        db.add(otp_record)
        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="ADD_MONEY_INITIATED",
                metadata={
                    "topup_id": str(topup_id),
                    "amount": str(amount),
                },
            )
        )
        await db.commit()

        # -- Send OTP email (best-effort)
        try:
            await send_otp_email(user.email, otp_plaintext, otp_type="ADD_MONEY")
        except Exception:
            logger.exception(
                "Failed to send add-money OTP",
                extra={"user_id": str(user.id), "topup_id": str(topup_id)},
            )

        return {
            "topup_id": str(topup_id),
            "amount": str(amount),
            "message": "OTP sent to your registered email. Valid for 5 minutes.",
        }

    # ------------------------------------------------------------------
    # Step 2: confirm add-money
    # ------------------------------------------------------------------

    async def confirm_add_money(
        self,
        db: AsyncSession,
        *,
        user: User,
        session_id: UUID,
        topup_id: UUID,
        otp: str,
    ) -> dict:
        """
        Verify the OTP, credit the account atomically, create a ledger entry.
        """
        # -- Verify OTP
        now = datetime.utcnow()
        otp_row = await self.repo.get_valid_topup_otp(
            db, user_id=user.id, topup_id=topup_id, now=now
        )
        if otp_row is None:
            raise otp_expired()

        if otp_row.attempts is not None and otp_row.attempts >= otp_row.max_attempts:
            raise max_otp_attempts()

        if not verify_otp_hash(otp, otp_row.otp_hash):
            otp_row = await self.repo.increment_otp_attempts(db, otp_row)
            await db.commit()
            if otp_row.attempts >= otp_row.max_attempts:
                raise max_otp_attempts()
            raise invalid_otp()

        # -- Fetch top-up context from Redis
        redis = get_redis()
        raw = redis.get(self._redis_key(topup_id))
        if raw is None:
            raise topup_not_found()

        ctx = json.loads(raw)
        amount = Decimal(ctx["amount"])
        account_id = UUID(ctx["account_id"])

        # -- Atomic credit (SELECT FOR UPDATE → credit → ledger)
        account = await self.repo.get_account_for_update(db, account_id)
        if account is None:
            raise not_found("Account")

        new_balance = await self.repo.credit_account_balance(db, account_id, amount)

        await self.repo.create_ledger_entry(
            db,
            account_id=account_id,
            entry_type="CREDIT",
            amount=amount,
            balance_after=new_balance,
            reference_type="ADD_MONEY",
            reference_id=topup_id,
            description=f"Wallet top-up of ₹{amount}",
        )

        await self.repo.mark_otp_verified(db, otp_row.id)

        db.add(
            self._audit(
                user_id=user.id,
                session_id=session_id,
                event_type="ADD_MONEY_SUCCESS",
                metadata={
                    "topup_id": str(topup_id),
                    "amount_credited": str(amount),
                    "balance_after": str(new_balance),
                },
            )
        )
        await db.commit()

        # -- Remove Redis key (idempotency guard — can't reuse this topup_id)
        redis.delete(self._redis_key(topup_id))

        return {
            "amount_credited": str(amount),
            "new_balance": str(new_balance),
            "currency": "INR",
        }
