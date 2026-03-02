"""Audit logging service."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.repository.models.audit_log import AuditLog


class AuditService:
    """High-level API for writing audit events."""

    @staticmethod
    def log_event(
        db: Session,
        *,
        user_id: Optional[str],
        session_id: Optional[str],
        event_type: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Insert a new audit log row.

        This is a thin wrapper around the AuditLog model so business code
        does not depend on model details.
        """
        event = AuditLog(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_metadata=metadata or {},
        )
        db.add(event)
        db.commit()

