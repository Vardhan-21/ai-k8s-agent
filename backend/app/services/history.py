"""Investigation History service.

Persists investigation records to InsForge's PostgreSQL database
and queries recent user history with user-level authorization.
Treats all content as untrusted and redacts secrets before persistence.
"""

from __future__ import annotations

import httpx
from loguru import logger
from pydantic import BaseModel

from app.ai.sanitizer import redact_text
from app.core.config import settings
from app.models.schemas import DiagnosisResult


class InvestigationRecord(BaseModel):
    """Investigation record stored in InsForge database."""

    id: str | None = None
    user_id: str
    created_at: str | None = None
    cluster_context: str | None = None
    root_cause: str
    explanation: str = ""
    fix: str = ""
    kubectl_command: str = ""
    namespace: str = "all"
    confidence: int
    status: str = "completed"


class HistoryService:
    """Handles investigation persistence and retrieval via InsForge PostgREST API."""

    def __init__(self) -> None:
        self._base_url = settings.INSFORGE_BASE_URL.rstrip("/")
        self._api_key = settings.INSFORGE_API_KEY

    async def save_investigation(
        self,
        user_id: str,
        diagnosis: DiagnosisResult,
        namespace: str = "all",
        status: str = "completed",
        cluster_context: str | None = None,
    ) -> bool:
        """Save an investigation record to InsForge database.

        Failures are caught and logged so live diagnosis is never broken.
        """
        record = {
            "user_id": user_id,
            "cluster_context": cluster_context,
            "root_cause": redact_text(diagnosis.root_cause),
            "explanation": redact_text(diagnosis.explanation),
            "fix": redact_text(diagnosis.fix),
            "kubectl_command": redact_text(diagnosis.kubectl_command),
            "namespace": namespace,
            "confidence": diagnosis.confidence,
            "status": status,
        }

        url = f"{self._base_url}/api/database/records/investigations"
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=[record])

            if response.status_code in (200, 201):
                logger.info(f"Successfully persisted investigation for user={user_id}")
                return True

            logger.warning(
                f"Failed to persist investigation: HTTP {response.status_code} - {response.text[:200]}"
            )
            return False
        except Exception as exc:
            logger.error(f"Error persisting investigation to InsForge: {exc}")
            return False

    async def get_user_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Fetch past investigations for the specified authenticated user."""
        url = (
            f"{self._base_url}/api/database/records/investigations"
            f"?user_id=eq.{user_id}&order=created_at.desc&limit={limit}"
        )
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()

            logger.warning(
                f"Failed to fetch user history: HTTP {response.status_code} - {response.text[:200]}"
            )
            return []
        except Exception as exc:
            logger.error(f"Error fetching history from InsForge: {exc}")
            return []
