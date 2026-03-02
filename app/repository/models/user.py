"""User model."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class User(Base):
    """
    Bank customer.

    Uses UUID primary key and stores basic profile and security-related fields.
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # External/customer-facing identifier
    customer_id = Column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name = Column(String(150), nullable=False)

    email = Column(
        String(150),
        unique=True,
        index=True,
        nullable=False,
    )

    phone = Column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash = Column(String(255), nullable=False)

    # Flexible structured address container
    address = Column(JSONB, nullable=True)

    salary = Column(Numeric(14, 2), nullable=True)

    kyc_status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )

    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    blocked_until = Column(DateTime(timezone=False), nullable=True)

    last_login_at = Column(DateTime(timezone=False), nullable=True)

    # Password reset fields
    reset_token_hash = Column(String(64), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships (lazy, for navigation only)
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user")

