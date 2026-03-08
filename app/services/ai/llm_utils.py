"""Shared LLM call utility for all AI agents.

Wraps LangChain + OpenAI with automatic timing, token counting, and structured
error handling.  All agent modules call ``call_llm()`` rather than instantiating
``ChatOpenAI`` directly.

This function is **synchronous** — callers running inside an async context must
wrap it with ``asyncio.to_thread()``.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config.ai_config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    """Metadata captured from a single LLM call — persisted to llm_interactions."""

    agent_name: str
    request_text: str       # full user-facing content sent to the model
    response_text: str      # raw model output
    status: str             # "SUCCESS" | "FAILED"
    error_msg: str | None = None
    token_input: int = 0
    token_output: int = 0
    context_attached: str = ""  # comma-separated context key names
    latency_ms: int = 0


def call_llm(
    agent_name: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3,
    context_keys: list[str] | None = None,
) -> LLMCallResult:
    """
    Call the configured OpenAI model with a system + user message pair.

    Always returns an ``LLMCallResult``; on exception ``status`` is ``"FAILED"``
    and ``error_msg`` contains the exception message.

    Parameters
    ----------
    agent_name:
        Logical name of the calling agent (stored in llm_interactions.agent_name).
    system_prompt:
        The system instruction passed to the model.
    user_content:
        The user-facing content (query + formatted context).
    temperature:
        Model sampling temperature (0.1 for deterministic routing, 0.7 for prose).
    context_keys:
        List of context type names attached to this call (for DB logging only).
    """
    context_str = ",".join(context_keys or [])
    result = LLMCallResult(
        agent_name=agent_name,
        request_text=user_content,
        response_text="",
        status="SUCCESS",
        context_attached=context_str,
    )

    try:
        llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=temperature,
            openai_api_key=OPENAI_API_KEY,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        start = time.time()
        response = llm.invoke(messages)
        result.latency_ms = int((time.time() - start) * 1000)

        result.response_text = response.content or ""
        usage = (response.response_metadata or {}).get("token_usage", {})
        result.token_input = usage.get("prompt_tokens", 0)
        result.token_output = usage.get("completion_tokens", 0)

    except Exception as exc:
        result.status = "FAILED"
        result.error_msg = str(exc)
        logger.exception("LLM call failed for agent '%s'", agent_name)

    return result


def _strip_json_fences(raw: str) -> str:
    """Remove markdown code fences that some models wrap around JSON output."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        # parts[1] is the content; first token may be language tag (e.g. "json")
        inner = parts[1] if len(parts) > 1 else raw
        if inner.startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return raw
