"""OpenRouter LLM Client using HTTPX.

Handles authentication, timeout management, exponential backoff retries,
and clean error logging without exposing secrets.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings


class LLMClientError(Exception):
    """Raised when communication with the LLM API fails."""


class LLMClient:
    """Async client for OpenRouter chat completions."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self._model = (
            model
            if model
            else (settings.OPENROUTER_MODEL or "minimax/minimax-m3.1-flash:free")
        )
        self._base_url = (
            base_url
            if base_url is not None
            else settings.OPENROUTER_BASE_URL.rstrip("/")
        )
        self._timeout = (
            timeout
            if timeout is not None
            else settings.OPENROUTER_TIMEOUT_SECONDS
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else settings.OPENROUTER_MAX_RETRIES
        )

    @property
    def is_configured(self) -> bool:
        """Check if an API key is provided."""
        return bool(self._api_key and self._api_key.strip())

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Send chat completion request to OpenRouter with retries and timeout.

        Args:
            system_prompt: Persona and guidelines.
            user_prompt: Investigation evidence and question.

        Returns:
            Parsed JSON dict from LLM response.

        Raises:
            LLMClientError: On missing key, network failure, or unparseable response.
        """
        if not self.is_configured:
            raise LLMClientError(
                "OPENROUTER_API_KEY is not configured. Please set OPENROUTER_API_KEY in the environment."
            )

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Kubernetes Agent",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,  # Low temperature for deterministic analysis
        }

        masked_key = (
            f"{self._api_key[:6]}...{self._api_key[-4:]}"
            if len(self._api_key) > 10
            else "***"
        )
        logger.info(
            f"Calling OpenRouter model='{self._model}' using key={masked_key}"
        )

        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await asyncio.wait_for(
                        client.post(
                            url,
                            headers=headers,
                            json=payload,
                        ),
                        timeout=self._timeout,
                    )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise LLMClientError(
                            "OpenRouter returned empty choices array"
                        )

                    message_content = (
                        choices[0].get("message", {}).get("content", "")
                    )
                    return self._extract_json(message_content)

                # Retry on 5xx or 429
                if response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"OpenRouter attempt {attempt + 1}/{self._max_retries + 1} "
                        f"returned status {response.status_code}: {response.text[:200]}"
                    )
                    last_exception = LLMClientError(
                        f"OpenRouter HTTP {response.status_code}: {response.text[:150]}"
                    )
                else:
                    # 4xx client errors (bad request, auth) should not be retried
                    raise LLMClientError(
                        f"OpenRouter request failed with status {response.status_code}: {response.text[:200]}"
                    )

            except httpx.TimeoutException as exc:
                logger.warning(
                    f"OpenRouter attempt {attempt + 1}/{self._max_retries + 1} timed out"
                )
                last_exception = LLMClientError(
                    f"OpenRouter request timed out after {self._timeout}s"
                )
            except httpx.RequestError as exc:
                logger.warning(
                    f"OpenRouter attempt {attempt + 1}/{self._max_retries + 1} network error: {exc}"
                )
                last_exception = LLMClientError(
                    f"Network error connecting to OpenRouter: {exc}"
                )

            if attempt < self._max_retries:
                backoff_time = (2 ** attempt) * 1.0
                logger.info(f"Retrying OpenRouter in {backoff_time}s...")
                await asyncio.sleep(backoff_time)

        if last_exception:
            raise last_exception
        raise LLMClientError("Failed to communicate with OpenRouter after retries")

    @staticmethod
    def _extract_json(raw_text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM text that might include markdown fences."""
        cleaned = raw_text.strip()

        # Handle ```json ... ``` code blocks
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

        # If enclosed in { }, isolate the outermost JSON object
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx : end_idx + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse LLM JSON: {exc} | Raw text: {raw_text[:300]}")
            raise LLMClientError(f"LLM did not return valid JSON: {exc}")
