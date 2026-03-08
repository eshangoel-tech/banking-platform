"""LLM interaction model — low-level record of each agent/model call."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class LLMInteraction(Base):
    """
    Records every individual LLM call made to fulfil a chat response.

    One ChatResponse may trigger multiple LLM calls (e.g. planner + tool).
    """

    __tablename__ = "llm_interactions"
    __table_args__ = (
        Index("ix_llm_interactions_response_id", "response_id"),
        Index("ix_llm_interactions_agent_name", "agent_name"),
        Index("ix_llm_interactions_status", "status"),
        Index("ix_llm_interactions_created_at", "created_at"),
    )

    interaction_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    response_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_name = Column(String(128), nullable=False)

    # Raw prompt sent to the model
    request = Column(Text, nullable=True)

    # Raw model output
    response = Column(Text, nullable=True)

    # SUCCESS | FAILED | PARTIAL
    status = Column(String(20), nullable=False, default="SUCCESS", server_default="SUCCESS")

    error_msg = Column(Text, nullable=True)

    token_input = Column(Integer, nullable=True)
    token_output = Column(Integer, nullable=True)

    # Comma-separated or JSON list of context names attached (e.g. "user_context,account_context")
    context_attached = Column(Text, nullable=True)

    latency_ms = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
