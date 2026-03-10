"""AI assistant orchestration service.

Implements the three-layer multi-agent pipeline:

  Layer 1 — Router (assistant agent)
    Splits the user message into sub-queries, assigns each to a specialist
    agent, and specifies which context types are needed.

  Layer 2 — Domain agents (run concurrently via asyncio.gather)
    bank_manager, loan_officer, accountant, support_staff.
    Each receives its sub-query + pre-fetched context and returns a
    natural-language response plus optional redirect suggestions.

  Layer 3 — Receptionist
    Combines all domain-agent responses and direct receptionist tasks into
    a single, coherent final reply.  Also collects and deduplicates all
    redirect actions.

All LLM calls (layers 1–3) are logged to llm_interactions.
The final user↔assistant exchange is logged to chat_responses.
Session context (user_context + rolling chat history) is cached in Redis.
"""
from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.assistant.agent import RouterDecision, route_message
from app.ai_agents.bank_manager.agent import respond as bank_manager_respond
from app.ai_agents.loan_officer.agent import respond as loan_officer_respond
from app.ai_agents.accountant.agent import respond as accountant_respond
from app.ai_agents.support_staff.agent import respond as support_respond
from app.ai_agents.receptionist.agent import (
    AgentResponse,
    ReceptionistTask,
    combine_responses,
)
from app.common.utils.exceptions import chat_session_expired, chat_session_not_found
from app.config.ai_config import AI_CHAT_HISTORY_LIMIT, AI_SESSION_REDIS_TTL
from app.repository.core.chat_repository.repository import ChatRepository
from app.repository.models.user import User
from app.services.ai.context_fetch import (
    fetch_account_context,
    fetch_bank_policy_context,
    fetch_bank_policy_document,
    fetch_bank_rules_context,
    fetch_chat_history_context,
    fetch_loan_details,
    fetch_transaction_context,
    fetch_transactions_tool,
    fetch_user_context,
)
from app.services.ai.llm_utils import LLMCallResult

logger = logging.getLogger(__name__)

_REDIS_KEY = "ai_context:{chat_sess_id}"

# Maps router agent names → domain agent respond() functions
_DOMAIN_AGENTS = {
    "bank_manager": bank_manager_respond,
    "loan_officer": loan_officer_respond,
    "accountant": accountant_respond,
    "support": support_respond,
}


class AssistantService:
    """Orchestrates the three-layer AI assistant pipeline."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_session(
        self,
        db: AsyncSession,
        redis: Redis,
        user: User,
        auth_session_id: UUID,
    ) -> dict:
        """
        Create a new AI chat session and pre-load context into Redis.

        Steps
        -----
        1. Insert a ChatSession row (status=ACTIVE).
        2. Fetch user_context + last 10 chat turns from DB.
        3. Serialise to JSON and store in Redis with 1-hour TTL.
        4. Return {chat_sess_id}.
        """
        repo = ChatRepository()

        async with db.begin():
            chat_session = await repo.create_session(
                db,
                customer_id=user.customer_id,
                session_id=auth_session_id,
            )

        # Fetch context outside the transaction (read-only)
        user_ctx = await fetch_user_context(db, user.id)
        chat_history = await fetch_chat_history_context(
            db, user.customer_id, limit=AI_CHAT_HISTORY_LIMIT
        )

        redis_key = _REDIS_KEY.format(chat_sess_id=str(chat_session.chat_sess_id))
        redis.setex(
            redis_key,
            AI_SESSION_REDIS_TTL,
            json.dumps({"user_context": user_ctx, "chat_history": chat_history}),
        )

        logger.info(
            "AI session started: chat_sess_id=%s customer_id=%s",
            chat_session.chat_sess_id,
            user.customer_id,
        )
        return {"chat_sess_id": str(chat_session.chat_sess_id)}

    async def process_chat(
        self,
        db: AsyncSession,
        redis: Redis,
        user: User,
        chat_sess_id: UUID,
        message: str,
    ) -> dict:
        """
        Run the full three-layer pipeline for one user message.

        Returns
        -------
        {response: str, actions: list[dict], chat_sess_id: str}
        """
        # 1. Load cached context from Redis ----------------------------------
        redis_key = _REDIS_KEY.format(chat_sess_id=str(chat_sess_id))
        raw = redis.get(redis_key)
        if raw is None:
            raise chat_session_expired()
        redis_context: dict = json.loads(raw)

        all_llm_results: list[LLMCallResult] = []

        # 2. Layer 1 — Router ------------------------------------------------
        decisions, router_llm = await asyncio.to_thread(
            route_message,
            message,
            redis_context.get("chat_history", []),
        )
        all_llm_results.append(router_llm)

        # 3. Separate domain vs. receptionist tasks ---------------------------
        domain_decisions = [d for d in decisions if d.agent in _DOMAIN_AGENTS]
        receptionist_decisions = [d for d in decisions if d.agent == "receptionist"]

        # 4. Layer 2 — Domain agents (concurrent) ----------------------------
        agent_responses: list[AgentResponse] = []

        if domain_decisions:
            async def _run_domain(decision: RouterDecision) -> tuple[AgentResponse, LLMCallResult]:
                context_data = await self._fetch_context(db, user, decision, redis_context)
                agent_fn = _DOMAIN_AGENTS[decision.agent]
                resp_text, suggest_actions, llm_result = await asyncio.to_thread(
                    agent_fn, decision.text, context_data
                )
                return (
                    AgentResponse(
                        agent=decision.agent,
                        query=decision.text,
                        response=resp_text,
                        suggest_actions=suggest_actions,
                    ),
                    llm_result,
                )

            domain_results = await asyncio.gather(
                *[_run_domain(d) for d in domain_decisions]
            )
            for ar, llm_r in domain_results:
                agent_responses.append(ar)
                all_llm_results.append(llm_r)

        # 5. Layer 3 — Receptionist ------------------------------------------
        receptionist_tasks = [
            ReceptionistTask(text=d.text, action=d.action)
            for d in receptionist_decisions
        ]
        final_response, redirect_actions, receptionist_llm = await asyncio.to_thread(
            combine_responses,
            message,
            agent_responses,
            receptionist_tasks,
        )
        all_llm_results.append(receptionist_llm)

        # 6. Persist to DB ---------------------------------------------------
        async with db.begin():
            repo = ChatRepository()
            chat_resp = await repo.create_response(
                db,
                chat_sess_id=chat_sess_id,
                user_message=message,
                assistant_response=final_response,
            )
            for llm_r in all_llm_results:
                await repo.create_llm_interaction(
                    db,
                    response_id=chat_resp.response_id,
                    agent_name=llm_r.agent_name,
                    request=llm_r.request_text,
                    response=llm_r.response_text,
                    status=llm_r.status,
                    error_msg=llm_r.error_msg,
                    token_input=llm_r.token_input,
                    token_output=llm_r.token_output,
                    context_attached=llm_r.context_attached,
                    latency_ms=llm_r.latency_ms,
                )

        # 7. Update Redis chat history ----------------------------------------
        chat_history: list[dict] = redis_context.get("chat_history", [])
        chat_history.append({"user_message": message, "assistant_response": final_response})
        chat_history = chat_history[-AI_CHAT_HISTORY_LIMIT:]
        redis_context["chat_history"] = chat_history
        redis.setex(redis_key, AI_SESSION_REDIS_TTL, json.dumps(redis_context))

        return {
            "response": final_response,
            "actions": redirect_actions,
            "chat_sess_id": str(chat_sess_id),
        }

    async def stop_session(
        self,
        db: AsyncSession,
        redis: Redis,
        user: User,
        chat_sess_id: UUID,
    ) -> dict:
        """
        Mark the session as CLOSED and evict the Redis context cache.
        """
        repo = ChatRepository()

        async with db.begin():
            await repo.close_session(db, chat_sess_id)

        redis_key = _REDIS_KEY.format(chat_sess_id=str(chat_sess_id))
        redis.delete(redis_key)

        logger.info("AI session closed: chat_sess_id=%s", chat_sess_id)
        return {"message": "Session ended successfully."}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_context(
        self,
        db: AsyncSession,
        user: User,
        decision: RouterDecision,
        redis_context: dict,
    ) -> dict:
        """
        Resolve the context type names in ``decision.context`` into actual data.

        user_context and chat_history come from the Redis cache (no extra DB hit).
        All others are fetched from the DB or RAG on-demand.
        """
        context: dict = {}
        for ctx_type in decision.context:
            if ctx_type == "user_context":
                context["user_context"] = redis_context.get("user_context", {})
            elif ctx_type == "chat_history":
                context["chat_history"] = redis_context.get("chat_history", [])
            elif ctx_type == "account_context":
                context["account_context"] = await fetch_account_context(db, user.id)
            elif ctx_type == "transaction_context":
                context["transaction_context"] = await fetch_transaction_context(db, user.id, limit=10)
            elif ctx_type == "loan_context":
                context["loan_context"] = await fetch_loan_details(db, user.id)
            elif ctx_type == "bank_policy":
                # RAG — blocking; run in thread pool
                context["bank_policy"] = await asyncio.to_thread(
                    fetch_bank_policy_context, decision.text
                )
            elif ctx_type == "bank_rules":
                context["bank_rules"] = await asyncio.to_thread(
                    fetch_bank_rules_context, decision.text
                )
            # ── New tool-based context types ──────────────────────────────
            elif ctx_type == "transaction_analysis":
                # Full history + spending summary — used for deep financial analysis
                context["transaction_analysis"] = await fetch_transactions_tool(db, user.id)
            elif ctx_type == "bank_policy_document":
                # Deep RAG (top_k=6) — used for detailed, multi-section policy questions
                context["bank_policy_document"] = await asyncio.to_thread(
                    fetch_bank_policy_document, decision.text
                )
            else:
                logger.debug("Unknown context type requested by router: %s", ctx_type)
        return context
