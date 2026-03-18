"""AI / LLM configuration — loaded once at import time."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Provider priority — comma-separated, left = highest priority
# Available values: groq, openai, claude
# Example: AI_PROVIDER_PRIORITY=groq,openai,claude
# ---------------------------------------------------------------------------
AI_PROVIDER_PRIORITY: list[str] = [
    p.strip()
    for p in os.getenv("AI_PROVIDER_PRIORITY", "groq,openai,claude").split(",")
    if p.strip()
]

# ---------------------------------------------------------------------------
# Groq — FREE tier (https://console.groq.com)
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ---------------------------------------------------------------------------
# OpenAI / ChatGPT — paid (https://platform.openai.com)
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Anthropic / Claude — paid, has free tier (https://console.anthropic.com)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# ---------------------------------------------------------------------------
# Redis TTL for AI session context cache (seconds)
# ---------------------------------------------------------------------------
AI_SESSION_REDIS_TTL: int = 3600  # 1 hour

# Number of past chat turns injected into every LLM call
AI_CHAT_HISTORY_LIMIT: int = 10
