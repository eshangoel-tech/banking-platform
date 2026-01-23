"""AI request model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class AIRequest(Base):
    """AI request model representing external AI calls."""

    __tablename__ = "ai_requests"

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

    # Relationship
    user = relationship("User", backref="ai_requests")
