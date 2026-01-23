"""Payment model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class Payment(Base):
    """Payment model representing external payment requests."""

    __tablename__ = "payments"

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

    amount = Column(
        Numeric(14, 2),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=True,
    )

    request = Column(
        JSONB,
        nullable=False,
    )

    response = Column(
        JSONB,
        nullable=True,
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
    user = relationship("User", backref="payments")
