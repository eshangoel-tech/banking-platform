"""AI / LLM configuration — loaded once at import time."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# OpenAI / LangChain settings
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Redis TTL for AI session context cache (seconds)
AI_SESSION_REDIS_TTL: int = 3600  # 1 hour

# Number of past chat turns injected into every LLM call
AI_CHAT_HISTORY_LIMIT: int = 10
