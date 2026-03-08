"""Chat repository — data access for the AI assistant tables.

Covers:
  - chat_sessions  : lifecycle of one AI conversation.
  - chat_responses : individual user/assistant turns.
  - llm_interactions : low-level record of every LLM call.
"""
from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils.exceptions import (
    chat_session_closed,
    chat_session_not_found,
)
from app.repository.models.chat_response import ChatResponse
from app.repository.models.chat_session import ChatSession
from app.repository.models.llm_interaction import LLMInteraction


class ChatRepository:

    # ------------------------------------------------------------------
    # ChatSession
    # ------------------------------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        customer_id: str,
        session_id: UUID | None,
    ) -> ChatSession:
        """Create a new ACTIVE chat session."""
        session = ChatSession(
            customer_id=customer_id,
            session_id=session_id,
            status="ACTIVE",
        )
        db.add(session)
        await db.flush()
        return session

    async def get_session(
        self,
        db: AsyncSession,
        chat_sess_id: UUID,
    ) -> ChatSession | None:
        """Return a chat session by primary key or None."""
        result = await db.execute(
            select(ChatSession).where(ChatSession.chat_sess_id == chat_sess_id)
        )
        return result.scalar_one_or_none()

    async def close_session(
        self,
        db: AsyncSession,
        chat_sess_id: UUID,
    ) -> ChatSession:
        """Mark the session as CLOSED. Raises if not found or already closed."""
        session = await self.get_session(db, chat_sess_id)
        if session is None:
            raise chat_session_not_found()
        if session.status == "CLOSED":
            raise chat_session_closed()
        session.status = "CLOSED"
        await db.flush()
        return session

    # ------------------------------------------------------------------
    # ChatResponse
    # ------------------------------------------------------------------

    async def create_response(
        self,
        db: AsyncSession,
        chat_sess_id: UUID,
        user_message: str,
        assistant_response: str,
    ) -> ChatResponse:
        """Persist one conversational turn."""
        row = ChatResponse(
            chat_sess_id=chat_sess_id,
            user_message=user_message,
            assistant_response=assistant_response,
        )
        db.add(row)
        await db.flush()
        return row

    # ------------------------------------------------------------------
    # LLMInteraction
    # ------------------------------------------------------------------

    async def create_llm_interaction(
        self,
        db: AsyncSession,
        response_id: UUID,
        agent_name: str,
        request: str | None,
        response: str | None,
        status: str,
        error_msg: str | None,
        token_input: int | None,
        token_output: int | None,
        context_attached: str | None,
        latency_ms: int | None,
    ) -> LLMInteraction:
        """Persist one LLM call record linked to a ChatResponse."""
        row = LLMInteraction(
            response_id=response_id,
            agent_name=agent_name,
            request=request,
            response=response,
            status=status,
            error_msg=error_msg,
            token_input=token_input,
            token_output=token_output,
            context_attached=context_attached,
            latency_ms=latency_ms,
        )
        db.add(row)
        await db.flush()
        return row
