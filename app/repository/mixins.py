"""SQLAlchemy mixins for common model fields."""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class IDMixin:
    """Mixin providing UUID primary key."""

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )


class TimestampMixin:
    """Mixin providing created_at and updated_at UTC timestamps."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

