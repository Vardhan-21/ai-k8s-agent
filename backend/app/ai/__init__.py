"""AI package for Kubernetes Troubleshooting.

Provides Senior Kubernetes SRE reasoning, prompt construction,
secret sanitization, OpenRouter LLM execution, and confidence calibration.
"""

from app.ai.confidence_engine import ConfidenceEngine
from app.ai.llm_client import LLMClient, LLMClientError
from app.ai.prompt_builder import SYSTEM_PROMPT, build_troubleshooting_prompt
from app.ai.reasoning import AIReasoningEngine
from app.ai.sanitizer import redact_text, sanitize_investigation_payload

__all__ = [
    "AIReasoningEngine",
    "LLMClient",
    "LLMClientError",
    "ConfidenceEngine",
    "build_troubleshooting_prompt",
    "SYSTEM_PROMPT",
    "redact_text",
    "sanitize_investigation_payload",
]
