"""AI assistant API — three endpoints for the chat lifecycle.

POST /api/v1/ai/assistant/start   — open a session, pre-load context into Redis
POST /api/v1/ai/assistant/chat    — send a message, run the multi-agent pipeline
POST /api/v1/ai/assistant/stop    — close the session, clear Redis cache
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.core.auth_dependency import AuthContext, get_current_user
from app.common.responses import ok_response
from app.config.redis import get_redis
from app.repository.session import get_db
from app.schemas.assistant import ChatRequest, StopRequest
from app.services.ai.assistant_service import AssistantService

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /start
# ---------------------------------------------------------------------------

@router.post("/start")
async def assistant_start(
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Open a new AI chat session for the authenticated user.

    - Inserts a ``chat_sessions`` row (status=ACTIVE).
    - Fetches user profile + last 10 chat turns and caches them in Redis
      (key: ``ai_context:{chat_sess_id}``, TTL: 1 hour).

    Returns ``chat_sess_id`` — pass this in every subsequent /chat and /stop call.
    """
    service = AssistantService()
    data = await service.start_session(
        db, get_redis(), auth.user, auth.session_id
    )
    return ok_response(request, "Assistant session started.", data=data)


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

@router.post("/chat")
async def assistant_chat(
    request: Request,
    payload: ChatRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Process one user message through the three-layer AI pipeline.

    Pipeline layers:
      1. Router (assistant agent)  — splits message, assigns agents + context.
      2. Domain agents (parallel)  — bank_manager / loan_officer / accountant / support.
      3. Receptionist              — combines all responses into a single reply.

    Every LLM call is logged to ``llm_interactions``.
    The final exchange is saved to ``chat_responses``.
    Redis chat history is updated after each turn.

    Returns ``response`` (str) and ``actions`` (list of redirect objects).
    """
    service = AssistantService()
    data = await service.process_chat(
        db, get_redis(), auth.user, payload.chat_sess_id, payload.message
    )
    return ok_response(request, "Response generated.", data=data)


# ---------------------------------------------------------------------------
# POST /stop
# ---------------------------------------------------------------------------

@router.post("/stop")
async def assistant_stop(
    request: Request,
    payload: StopRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Close the AI chat session.

    - Sets ``chat_sessions.status`` to ``CLOSED``.
    - Deletes the Redis context cache for this session.
    """
    service = AssistantService()
    data = await service.stop_session(
        db, get_redis(), auth.user, payload.chat_sess_id
    )
    return ok_response(request, data["message"], data=None)
