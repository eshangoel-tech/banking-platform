"""User model."""
import uuid

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.common.db.base import Base


class User(Base):
    """User model representing bank customers."""

    __tablename__ = "users"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    uuid = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )

    full_name = Column(
        String(150),
        nullable=False,
    )

    date_of_birth = Column(
        Date,
        nullable=False,
    )

    phone = Column(
        String(15),
        unique=True,
        nullable=False,
        index=True,
    )

    email = Column(
        String(150),
        unique=True,
        nullable=True,
        index=True,
    )

    address_line_1 = Column(
        String(255),
        nullable=True,
    )

    address_line_2 = Column(
        String(255),
        nullable=True,
    )

    city = Column(
        String(100),
        nullable=True,
    )

    state = Column(
        String(100),
        nullable=True,
    )

    pincode = Column(
        String(10),
        nullable=True,
    )

    user_settings = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

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
