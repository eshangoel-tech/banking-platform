"""Pydantic schemas for the AI assistant endpoints."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    chat_sess_id: UUID = Field(..., description="Active AI chat session ID from /assistant/start")
    message: str = Field(..., min_length=1, max_length=2000, description="User's message")


class StopRequest(BaseModel):
    chat_sess_id: UUID = Field(..., description="AI chat session ID to close")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RedirectAction(BaseModel):
    name: str = Field(..., description="Tool / action name (e.g. PAY_EMI)")
    label: str = Field(..., description="Human-readable button label")
    url: str = Field(..., description="Frontend route to navigate to")


class AssistantStartData(BaseModel):
    chat_sess_id: UUID


class ChatResponseData(BaseModel):
    response: str
    actions: list[RedirectAction] = Field(default_factory=list)
    chat_sess_id: UUID
