"""Shared LLM call utility for all AI agents.

Tries providers in priority order (AI_PROVIDER_PRIORITY env var).
Falls back to the next provider if one fails (quota, network, etc.).
All agent modules call ``call_llm()`` — never instantiate LLMs directly.

This function is **synchronous** — callers in async context must use
``asyncio.to_thread()``.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.ai_config import (
    AI_PROVIDER_PRIORITY,
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    """Metadata captured from a single LLM call — persisted to llm_interactions."""

    agent_name: str
    request_text: str       # full user-facing content sent to the model
    response_text: str      # raw model output
    status: str             # "SUCCESS" | "FAILED"
    provider_used: str = "" # which provider actually responded
    error_msg: str | None = None
    token_input: int = 0
    token_output: int = 0
    context_attached: str = ""  # comma-separated context key names
    latency_ms: int = 0


def _build_llm(provider: str, temperature: float) -> BaseChatModel:
    """Instantiate the LLM for the given provider."""
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=GROQ_MODEL,
            temperature=temperature,
            groq_api_key=GROQ_API_KEY,
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=temperature,
            openai_api_key=OPENAI_API_KEY,
        )
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=CLAUDE_MODEL,
            temperature=temperature,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )
    raise ValueError(f"Unknown AI provider: '{provider}'")


def call_llm(
    agent_name: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3,
    context_keys: list[str] | None = None,
) -> LLMCallResult:
    """
    Call the LLM with automatic provider fallback.

    Tries each provider in AI_PROVIDER_PRIORITY order.
    If a provider fails (quota, network, etc.) it logs a warning and
    moves to the next one.  Only marks FAILED if all providers fail.

    Parameters
    ----------
    agent_name:     Logical name of the calling agent (for DB logging).
    system_prompt:  System instruction passed to the model.
    user_content:   User-facing content (query + formatted context).
    temperature:    Sampling temperature.
    context_keys:   Context type names attached to this call (for logging).
    """
    context_str = ",".join(context_keys or [])
    result = LLMCallResult(
        agent_name=agent_name,
        request_text=user_content,
        response_text="",
        status="SUCCESS",
        context_attached=context_str,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    last_exc: Exception | None = None

    for provider in AI_PROVIDER_PRIORITY:
        try:
            llm = _build_llm(provider, temperature)
            start = time.time()
            response = llm.invoke(messages)
            result.latency_ms = int((time.time() - start) * 1000)

            result.response_text = response.content or ""
            result.provider_used = provider

            # LangChain normalises usage across providers via usage_metadata
            # Fallback to OpenAI-style response_metadata if missing
            usage_meta = getattr(response, "usage_metadata", None) or {}
            if usage_meta:
                result.token_input = usage_meta.get("input_tokens", 0)
                result.token_output = usage_meta.get("output_tokens", 0)
            else:
                usage = (response.response_metadata or {}).get("token_usage", {})
                result.token_input = usage.get("prompt_tokens", 0)
                result.token_output = usage.get("completion_tokens", 0)

            logger.info(
                "LLM call OK | agent=%s provider=%s tokens_in=%d tokens_out=%d latency=%dms",
                agent_name, provider,
                result.token_input, result.token_output, result.latency_ms,
            )
            return result

        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Provider '%s' failed for agent '%s': %s — trying next provider",
                provider, agent_name, type(exc).__name__,
            )
            continue

    # All providers failed
    result.status = "FAILED"
    result.error_msg = str(last_exc)
    logger.error(
        "All providers failed for agent '%s'. Priority: %s. Last error: %s",
        agent_name, AI_PROVIDER_PRIORITY, last_exc,
    )
    return result


def _strip_json_fences(raw: str) -> str:
    """
    Extract a JSON object from LLM output, handling:
    - Markdown code fences (```json ... ```)
    - Preamble text before the JSON (e.g. "Here is the response: {...}")
    - Trailing text after the JSON
    """
    import re

    raw = raw.strip()

    # 1. Strip markdown code fences
    if raw.startswith("```"):
        parts = raw.split("```")
        inner = parts[1] if len(parts) > 1 else raw
        if inner.startswith("json"):
            inner = inner[4:]
        raw = inner.strip()

    # 2. If it's already valid JSON, return as-is
    if raw.startswith("{"):
        return raw

    # 3. Extract the first {...} block from the text (handles preamble/suffix)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return match.group(0)

    return raw
