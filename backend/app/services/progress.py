"""Investigation Progress Tracker.

Manages stage transitions during an active investigation.
Publishes progress updates when each stage begins or completes,
and provides live progress state to clients.
"""

from __future__ import annotations

import asyncio
from typing import Any
from loguru import logger
from pydantic import BaseModel

PROGRESS_STAGES = [
    {"id": "checking_pods", "label": "Checking Pods"},
    {"id": "reading_logs", "label": "Reading Logs"},
    {"id": "analyzing_events", "label": "Analyzing Events"},
    {"id": "inspecting_deployments", "label": "Inspecting Deployments"},
    {"id": "checking_networking", "label": "Checking Networking"},
    {"id": "ai_reasoning", "label": "AI Reasoning"},
    {"id": "completed", "label": "Root Cause Found"},
]


class ProgressUpdate(BaseModel):
    """Payload for a progress event."""

    investigation_id: str
    stage: str
    label: str
    completed: bool = False
    timestamp: float | None = None


class ProgressTracker:
    """In-memory progress registry allowing SSE or live polling for active investigations."""

    _active_investigations: dict[str, list[str]] = {}
    _subscribers: dict[str, list[asyncio.Queue]] = {}

    @classmethod
    def start_investigation(cls, investigation_id: str) -> None:
        """Initialize tracking for a new investigation."""
        cls._active_investigations[investigation_id] = []
        if investigation_id not in cls._subscribers:
            cls._subscribers[investigation_id] = []

    @classmethod
    async def update_stage(cls, investigation_id: str, stage: str) -> None:
        """Mark a stage as reached and notify all subscribers."""
        if investigation_id not in cls._active_investigations:
            cls._active_investigations[investigation_id] = []

        if stage not in cls._active_investigations[investigation_id]:
            cls._active_investigations[investigation_id].append(stage)

        stage_label = next(
            (s["label"] for s in PROGRESS_STAGES if s["id"] == stage), stage
        )
        logger.info(f"[{investigation_id}] Progress stage: {stage} ({stage_label})")

        # Notify any waiting queues (e.g., SSE or WebSocket connections)
        update = {
            "investigation_id": investigation_id,
            "stage": stage,
            "label": stage_label,
            "completed_stages": list(cls._active_investigations[investigation_id]),
        }

        queues = cls._subscribers.get(investigation_id, [])
        for q in list(queues):
            try:
                q.put_nowait(update)
            except Exception:
                pass

    @classmethod
    def get_completed_stages(cls, investigation_id: str) -> list[str]:
        """Return the list of completed stages for this investigation."""
        return cls._active_investigations.get(investigation_id, [])

    @classmethod
    def subscribe(cls, investigation_id: str) -> asyncio.Queue:
        """Subscribe to live progress updates for an investigation."""
        if investigation_id not in cls._subscribers:
            cls._subscribers[investigation_id] = []
        q: asyncio.Queue = asyncio.Queue()
        cls._subscribers[investigation_id].append(q)
        return q

    @classmethod
    def unsubscribe(cls, investigation_id: str, q: asyncio.Queue) -> None:
        """Unsubscribe from progress updates."""
        if investigation_id in cls._subscribers:
            try:
                cls._subscribers[investigation_id].remove(q)
            except ValueError:
                pass
