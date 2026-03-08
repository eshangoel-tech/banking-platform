"""Celery application configuration."""
from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "banking",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.loan_tasks", "app.tasks.account_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Acknowledge tasks only after execution to prevent loss on worker crash
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
