"""Rule evaluation model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.common.db.base import Base


class RuleEvaluation(Base):
    """Rule evaluation model representing decision explainability."""

    __tablename__ = "rule_evaluations"

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

    rule_name = Column(
        String(100),
        nullable=False,
        index=True,
    )

    subject_type = Column(
        String(30),
        nullable=True,
    )

    subject_id = Column(
        BigInteger,
        nullable=True,
    )

    decision = Column(
        String(20),
        nullable=True,
    )

    reasoning = Column(
        JSONB,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
