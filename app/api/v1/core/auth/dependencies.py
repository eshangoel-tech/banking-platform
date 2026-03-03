"""FastAPI dependencies for authenticated endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import token_expired, token_invalid
from app.common.utils.security import verify_token
from app.repository.models.auth_session import Session
from app.repository.models.user import User
from app.repository.session import get_db

_bearer = HTTPBearer()


@dataclass
class AuthContext:
    """Authenticated request context: resolved user + validated session_id."""

    user: User
    session_id: UUID


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """
    Validate Bearer JWT, verify the session, and return an AuthContext.

    Raises AppException (401) when:
    - Token is missing, malformed, or has an invalid signature
    - Token has expired
    - Session does not exist, is inactive, or has expired
    - User record no longer exists
    """
    token = credentials.credentials

    try:
        payload = verify_token(token)
    except jwt.ExpiredSignatureError:
        raise token_expired()
    except jwt.InvalidTokenError:
        raise token_invalid()

    user_id_str: Optional[str] = payload.get("user_id")
    session_id_str: Optional[str] = payload.get("session_id")

    if not user_id_str or not session_id_str:
        raise token_invalid()

    try:
        user_id = UUID(user_id_str)
        session_id = UUID(session_id_str)
    except (ValueError, AttributeError):
        raise token_invalid()

    now = datetime.utcnow()

    # Validate session: must exist, be active, and not expired
    session_res = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
        )
    )
    session = session_res.scalar_one_or_none()

    if session is None or not session.is_active or session.expires_at < now:
        raise token_invalid("Session is invalid or has expired")

    # Load the user record
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()

    if user is None:
        raise token_invalid()

    return AuthContext(user=user, session_id=session_id)
