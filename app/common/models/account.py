"""Account model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class Account(Base):
    """Account model representing bank accounts."""

    __tablename__ = "accounts"

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

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_number = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    ifsc_code = Column(
        String(15),
        nullable=False,
    )

    account_type = Column(
        String(30),
        nullable=False,
    )

    balance = Column(
        Numeric(14, 2),
        nullable=False,
        default=0.00,
        server_default="0.00",
    )

    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
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

    # Relationship
    user = relationship("User", backref="accounts")
