"""Shared API response helpers — single source of truth for response structure.

Every successful response has the shape:
    {
        "success": true,
        "message": "<human-readable string>",
        "data": <payload | null>,
        "request_id": "<uuid string>"
    }
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request


def _get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return str(rid) if rid else ""


def ok_response(
    request: Request,
    message: str,
    data: Any = None,
) -> dict:
    """Return a standardised success response dict."""
    return {
        "success": True,
        "message": message,
        "data": data,
        "request_id": _get_request_id(request),
    }
