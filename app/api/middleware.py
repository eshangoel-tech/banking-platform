"""HTTP middleware for structured request/response logging."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.common.sanitization import sanitize_payload, truncate_payload
from app.repository.session import SessionLocal
from app.repository.models.request_log import RequestLog

logger = logging.getLogger("http")


async def _persist_request_log_async(data: dict) -> None:
    """Persist a RequestLog row in a background thread."""

    def _sync_persist() -> None:
        db = SessionLocal()
        try:
            log_row = RequestLog(**data)
            db.add(log_row)
            db.commit()
        except Exception:
            logger.exception("Failed to persist request log")
        finally:
            db.close()

    await asyncio.to_thread(_sync_persist)


class HttpLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Generates a request_id
    - Measures latency
    - Extracts session_id and user_id (best-effort)
    - Sanitizes and truncates request/response bodies
    - Logs to stdout and request_logs table asynchronously
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        request_id = uuid.uuid4()
        start_time = time.perf_counter()

        # Extract session/user from headers (can be refined later from auth)
        raw_session_id = request.headers.get("X-Session-Id")
        raw_user_id = request.headers.get("X-User-Id")

        session_id: Optional[uuid.UUID]
        user_id: Optional[uuid.UUID]
        try:
            session_id = uuid.UUID(raw_session_id) if raw_session_id else None
        except Exception:
            session_id = None

        try:
            user_id = uuid.UUID(raw_user_id) if raw_user_id else None
        except Exception:
            user_id = None

        # Expose on request.state for later use (e.g. exception handler)
        request.state.request_id = request_id
        request.state.session_id = session_id
        request.state.user_id = user_id

        # Safely read body and rebuild request stream so downstream can read it
        body_bytes = await request.body()
        try:
            request_json = json.loads(body_bytes.decode() or "{}")
        except json.JSONDecodeError:
            request_json = None

        async def body_gen() -> Any:
            yield body_bytes

        request = Request(request.scope, receive=body_gen)

        # Call downstream application
        try:
            response = await call_next(request)
        except Exception:
            # Let the global exception handler deal with DB logging;
            # we still add context to the logger here.
            logger.exception(
                "Unhandled exception in request",
                extra={
                    "request_id": str(request_id),
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            raise

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Try to capture JSON response body if available and small
        response_json: Optional[Any] = None
        try:
            if hasattr(response, "body") and response.body is not None:
                response_json = json.loads(response.body.decode() or "{}")
        except Exception:
            response_json = None

        # Sanitize and truncate payloads
        safe_request_body = None
        if isinstance(request_json, (dict, list)):
            safe_request_body = truncate_payload(sanitize_payload(request_json))

        safe_response_body = None
        if isinstance(response_json, (dict, list)):
            safe_response_body = truncate_payload(sanitize_payload(response_json))

        log_data = {
            "id": uuid.uuid4(),
            "request_id": request_id,
            "session_id": session_id,
            "user_id": user_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_body": safe_request_body,
            "response_body": safe_response_body,
            "error_message": None,
        }

        # Fire-and-forget DB persistence
        asyncio.create_task(_persist_request_log_async(log_data))

        # Emit structured log to stdout
        logger.info(
            "HTTP request",
            extra={
                "request_id": str(request_id),
                "session_id": str(session_id) if session_id else None,
                "user_id": str(user_id) if user_id else None,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response

