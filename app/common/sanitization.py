"""Utilities for sanitizing and truncating payloads before logging."""
from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping, Sequence

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "otp",
    "one_time_password",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "auth_header",
    "card_number",
    "card_no",
    "pan",
    "cvv",
    "cvc",
    "pin",
    "security_code",
}


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        sanitized: MutableMapping[str, Any] = {}
        for key, value in obj.items():
            key_str = str(key)
            if key_str.lower() in SENSITIVE_KEYS:
                sanitized[key_str] = "***redacted***"
            else:
                sanitized[key_str] = _sanitize(value)
        return sanitized
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return [_sanitize(item) for item in obj]
    return obj


def sanitize_payload(payload: Any) -> Any:
    """
    Recursively remove sensitive fields from a payload.

    Works with nested dicts/lists. Non-collection values are returned as-is.
    """
    return _sanitize(payload)


def truncate_payload(payload: Any, max_bytes: int = 10 * 1024) -> Any:
    """
    Truncate payload if its JSON representation exceeds max_bytes.

    Returns a small marker object instead of the full payload when truncated.
    """
    try:
        serialized = json.dumps(payload, default=str)
    except Exception:
        # If we cannot serialize, just mark as non-serializable
        return {"_non_serializable": True}

    if len(serialized.encode("utf-8")) <= max_bytes:
        return payload

    return {
        "_truncated": True,
        "_approx_size_bytes": len(serialized.encode("utf-8")),
    }

