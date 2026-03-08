"""Auth service: registration, email verification, login, and password management."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    invalid_credentials,
    invalid_otp,
    max_otp_attempts,
    otp_expired,
    token_expired,
    token_invalid,
    user_already_exists,
    user_blocked,
    user_not_found,
)
from app.common.utils.otp import (
    generate_otp,
    hash_otp,
    send_otp_email,
    send_reset_password_email,
    verify_otp_hash,
)
from app.common.utils.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repository.core.auth_repository.repository import AuthRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, repo: AuthRepository | None = None) -> None:
        self.repo = repo or AuthRepository()

    # -----------------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------------

    async def register_user(
        self,
        db: AsyncSession,
        *,
        full_name: str,
        email: str,
        phone: str,
        password: str,
        salary=None,
    ) -> str:
        if await self.repo.get_user_by_email(db, email):
            raise user_already_exists("Email already registered")
        if await self.repo.get_user_by_phone(db, phone):
            raise user_already_exists("Phone already registered")

        password_hash = hash_password(password)
        customer_id = await self.repo.generate_unique_customer_id(db)

        user = await self.repo.create_user(
            db,
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            customer_id=customer_id,
            salary=salary,
        )

        otp = generate_otp()
        otp_hash = hash_otp(otp)
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        await self.repo.create_otp(
            db,
            user_id=user.id,
            otp_hash=otp_hash,
            otp_type="EMAIL_VERIFY",
            expires_at=expires_at,
            max_attempts=3,
        )
        await db.commit()

        # best-effort — SMTP failure does not roll back registration
        try:
            await send_otp_email(email, otp, otp_type="EMAIL_VERIFY")
        except Exception:
            logger.exception(
                "Failed to send registration OTP",
                extra={"user_id": str(user.id)},
            )

        return str(user.id)

    async def verify_email(
        self,
        db: AsyncSession,
        *,
        email: str,
        otp: str,
    ) -> dict:
        user = await self.repo.get_user_by_email(db, email)
        if not user:
            raise user_not_found()

        now = datetime.utcnow()
        otp_row = await self.repo.get_valid_otp(
            db, user_id=user.id, otp_type="EMAIL_VERIFY", now=now
        )
        if not otp_row:
            raise otp_expired()

        if otp_row.attempts is not None and otp_row.attempts >= otp_row.max_attempts:
            raise max_otp_attempts()

        if not verify_otp_hash(otp, otp_row.otp_hash):
            otp_row = await self.repo.increment_otp_attempts(db, otp_row)
            await db.commit()
            if otp_row.attempts >= otp_row.max_attempts:
                raise max_otp_attempts()
            raise invalid_otp()

        await self.repo.mark_otp_verified(db, otp_row.id)
        await self.repo.activate_user(db, user.id)
        account_number = await self.repo.generate_unique_account_number(db)
        account = await self.repo.create_account(
            db,
            user_id=user.id,
            account_number=account_number,
        )
        await db.commit()

        # Fire-and-forget: joining bonus + scheduled salary credit (via Celery)
        try:
            from app.tasks.account_tasks import on_email_verified_task
            on_email_verified_task.delay(str(user.id), str(account.id))
        except Exception:
            logger.exception(
                "Failed to dispatch on_email_verified_task",
                extra={"user_id": str(user.id)},
            )

        return {
            "user_id": str(user.id),
            "status": "ACTIVE",
            "account_id": str(account.id),
            "account_number": account.account_number,
        }

    # -----------------------------------------------------------------------
    # Login
    # -----------------------------------------------------------------------

    async def login_user(
        self,
        db: AsyncSession,
        *,
        identifier: str,
        password: str,
    ) -> None:
        """Step 1: verify password and send a LOGIN OTP to the user's email."""
        user = await self.repo.get_user_by_identifier(db, identifier)
        if not user:
            raise user_not_found()

        now = datetime.utcnow()
        if user.blocked_until and user.blocked_until > now:
            raise user_blocked(
                f"Account is blocked until {user.blocked_until.strftime('%Y-%m-%d %H:%M')} UTC."
            )

        if not verify_password(password, user.password_hash):
            new_attempts = (user.failed_login_attempts or 0) + 1
            await self.repo.increment_failed_attempts(db, user.id)
            if new_attempts > 3:
                await self.repo.block_user(db, user.id, now + timedelta(hours=1))
            await db.commit()
            raise invalid_credentials()

        # Correct password — reset counter and issue OTP
        otp = generate_otp()
        otp_hash = hash_otp(otp)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        await self.repo.reset_failed_attempts(db, user.id)
        await self.repo.create_otp(
            db,
            user_id=user.id,
            otp_hash=otp_hash,
            otp_type="LOGIN",
            expires_at=expires_at,
            max_attempts=3,
        )
        await db.commit()

        try:
            await send_otp_email(user.email, otp, otp_type="LOGIN")
        except Exception:
            logger.exception(
                "Failed to send login OTP",
                extra={"user_id": str(user.id)},
            )

    async def verify_login_otp(
        self,
        db: AsyncSession,
        *,
        identifier: str,
        otp: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Step 2: verify LOGIN OTP, create session, and return JWT."""
        user = await self.repo.get_user_by_identifier(db, identifier)
        if not user:
            raise user_not_found()

        now = datetime.utcnow()
        otp_row = await self.repo.get_valid_otp(
            db, user_id=user.id, otp_type="LOGIN", now=now
        )
        if not otp_row:
            raise otp_expired()

        if otp_row.attempts is not None and otp_row.attempts >= otp_row.max_attempts:
            raise max_otp_attempts()

        if not verify_otp_hash(otp, otp_row.otp_hash):
            otp_row = await self.repo.increment_otp_attempts(db, otp_row)
            await db.commit()
            if otp_row.attempts >= otp_row.max_attempts:
                raise max_otp_attempts()
            raise invalid_otp()

        await self.repo.mark_otp_verified(db, otp_row.id)
        session = await self.repo.create_session(
            db,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            session_meta={"full_name": user.full_name, "email": user.email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.repo.update_last_login(db, user.id)
        await db.commit()

        access_token = create_access_token(
            data={"user_id": str(user.id), "session_id": str(session.id)},
            expires_delta=timedelta(minutes=30),
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "session_id": str(session.id),
        }

    # -----------------------------------------------------------------------
    # Password management
    # -----------------------------------------------------------------------

    async def forgot_password(self, db: AsyncSession, *, email: str) -> None:
        """Generate a reset token and send the email (always returns silently even if not found)."""
        user = await self.repo.get_user_by_email(db, email)
        if not user:
            return  # never reveal whether the email is registered

        raw_token = generate_reset_token()
        token_hash = hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        await self.repo.save_reset_token(
            db,
            user_id=user.id,
            reset_token_hash=token_hash,
            expires_at=expires_at,
        )
        await db.commit()

        try:
            await send_reset_password_email(email, raw_token)
        except Exception:
            logger.exception(
                "Failed to send reset password email",
                extra={"user_id": str(user.id)},
            )

    async def reset_password(
        self,
        db: AsyncSession,
        *,
        token: str,
        new_password: str,
    ) -> None:
        """Validate the reset token, update the password, and invalidate all active sessions."""
        token_hash = hash_token(token)
        user = await self.repo.get_user_by_reset_token(db, token_hash)
        if not user:
            raise token_invalid()

        now = datetime.utcnow()
        if not user.reset_token_expires_at or user.reset_token_expires_at < now:
            raise token_expired()

        new_hash = hash_password(new_password)

        await self.repo.update_password(db, user.id, new_hash)
        await self.repo.clear_reset_token(db, user.id)
        await self.repo.invalidate_user_sessions(db, user.id)
        await db.commit()
