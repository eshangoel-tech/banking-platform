"""Repository for auth module DB access (async)."""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.models.account import Account
from app.repository.models.otp_verification import OtpVerification
from app.repository.models.user import User


class AuthRepository:
    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        res = await db.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    async def get_user_by_phone(self, db: AsyncSession, phone: str) -> Optional[User]:
        res = await db.execute(select(User).where(User.phone == phone))
        return res.scalar_one_or_none()

    async def create_user(
        self,
        db: AsyncSession,
        *,
        full_name: str,
        email: str,
        phone: str,
        password_hash: str,
        customer_id: str,
        salary=None,
    ) -> User:
        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            customer_id=customer_id,
            salary=salary,
            status="INACTIVE",
            kyc_status="PENDING",
        )
        db.add(user)
        await db.flush()
        return user

    async def activate_user(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(status="ACTIVE", kyc_status="VERIFIED")
        )

    async def create_account(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        account_number: str,
    ) -> Account:
        account = Account(
            user_id=user_id,
            account_number=account_number,
            account_type="CURRENT",
            balance=0,
            currency="INR",
            status="ACTIVE",
        )
        db.add(account)
        await db.flush()
        return account

    async def create_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        otp_hash: str,
        otp_type: str,
        expires_at: datetime,
        max_attempts: int = 3,
    ) -> OtpVerification:
        otp = OtpVerification(
            user_id=user_id,
            otp_hash=otp_hash,
            otp_type=otp_type,
            attempts=0,
            max_attempts=max_attempts,
            expires_at=expires_at,
            status="PENDING",
        )
        db.add(otp)
        await db.flush()
        return otp

    async def get_valid_otp(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        otp_type: str,
        now: datetime,
    ) -> Optional[OtpVerification]:
        res = await db.execute(
            select(OtpVerification)
            .where(
                OtpVerification.user_id == user_id,
                OtpVerification.otp_type == otp_type,
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

    async def mark_otp_verified(self, db: AsyncSession, otp_id: UUID) -> None:
        await db.execute(
            update(OtpVerification)
            .where(OtpVerification.id == otp_id)
            .values(status="VERIFIED")
        )

    async def increment_otp_attempts(self, db: AsyncSession, otp: OtpVerification) -> OtpVerification:
        otp.attempts = (otp.attempts or 0) + 1
        if otp.attempts >= (otp.max_attempts or 3):
            otp.status = "FAILED"
        await db.flush()
        return otp

    async def customer_id_exists(self, db: AsyncSession, customer_id: str) -> bool:
        res = await db.execute(select(User.id).where(User.customer_id == customer_id))
        return res.first() is not None

    async def account_number_exists(self, db: AsyncSession, account_number: str) -> bool:
        res = await db.execute(select(Account.id).where(Account.account_number == account_number))
        return res.first() is not None

    async def generate_unique_customer_id(self, db: AsyncSession, length: int = 12) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            candidate = "".join(random.choices(alphabet, k=length))
            if not await self.customer_id_exists(db, candidate):
                return candidate

    async def generate_unique_account_number(self, db: AsyncSession, length: int = 12) -> str:
        alphabet = string.digits
        while True:
            candidate = "".join(random.choices(alphabet, k=length))
            if not await self.account_number_exists(db, candidate):
                return candidate


    # -----------------------------------------------------------------------
    # Login helpers
    # -----------------------------------------------------------------------

    async def get_user_by_identifier(self, db: AsyncSession, identifier: str) -> Optional[User]:
        """Find a user by email, phone, or customer_id (whichever matches)."""
        from sqlalchemy import or_
        res = await db.execute(
            select(User).where(
                or_(
                    User.email == identifier,
                    User.phone == identifier,
                    User.customer_id == identifier,
                )
            )
        )
        return res.scalar_one_or_none()

    async def increment_failed_attempts(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(failed_login_attempts=User.failed_login_attempts + 1)
        )

    async def reset_failed_attempts(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(User).where(User.id == user_id).values(failed_login_attempts=0)
        )

    async def block_user(self, db: AsyncSession, user_id: UUID, blocked_until: datetime) -> None:
        await db.execute(
            update(User).where(User.id == user_id).values(blocked_until=blocked_until)
        )

    async def update_last_login(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(User).where(User.id == user_id).values(last_login_at=datetime.utcnow())
        )

    # -----------------------------------------------------------------------
    # Session helpers
    # -----------------------------------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        expires_at: datetime,
        session_meta: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        from app.repository.models.auth_session import Session
        session = Session(
            user_id=user_id,
            session_meta=session_meta,
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()
        return session

    async def invalidate_user_sessions(self, db: AsyncSession, user_id: UUID) -> None:
        from app.repository.models.auth_session import Session
        await db.execute(
            update(Session)
            .where(Session.user_id == user_id, Session.is_active.is_(True))
            .values(is_active=False)
        )

    # -----------------------------------------------------------------------
    # Password reset helpers
    # -----------------------------------------------------------------------

    async def save_reset_token(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        reset_token_hash: str,
        expires_at: datetime,
    ) -> None:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(reset_token_hash=reset_token_hash, reset_token_expires_at=expires_at)
        )

    async def get_user_by_reset_token(self, db: AsyncSession, reset_token_hash: str) -> Optional[User]:
        res = await db.execute(
            select(User).where(User.reset_token_hash == reset_token_hash)
        )
        return res.scalar_one_or_none()

    async def update_password(self, db: AsyncSession, user_id: UUID, password_hash: str) -> None:
        await db.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )

    async def clear_reset_token(self, db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(reset_token_hash=None, reset_token_expires_at=None)
        )
