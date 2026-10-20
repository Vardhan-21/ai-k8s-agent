"""Unit and integration tests for AI Kubernetes Agent reasoning engine."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.confidence_engine import ConfidenceEngine
from app.ai.llm_client import LLMClient, LLMClientError
from app.ai.prompt_builder import SYSTEM_PROMPT, build_troubleshooting_prompt
from app.ai.reasoning import AIReasoningEngine
from app.ai.sanitizer import redact_text, sanitize_investigation_payload
from app.main import app
from app.models.schemas import (
    ClusterEvent,
    DeploymentInspectionResult,
    DeploymentStatus,
    DiagnosisResult,
    EventsAnalysisResult,
    InvestigationPayload,
    InvestigationResponse,
    LogsCollectionResult,
    NetworkInspectionResult,
    PodInspectionResult,
    PodLog,
    ProblematicPod,
    ServiceStatus,
)


# ---------------------------------------------------------------------------
# 1. Secret Sanitization Tests
# ---------------------------------------------------------------------------

def test_redact_sensitive_strings():
    """Verify secret patterns are redacted from untrusted text."""
    # DB URL password
    raw_url = "postgresql://dbuser:supersecretpass@postgres.default.svc:5432/production"
    redacted = redact_text(raw_url)
    assert "supersecretpass" not in redacted
    assert "[REDACTED_PASSWORD]" in redacted

    # JWT / Bearer
    raw_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"
    redacted_bearer = redact_text(raw_bearer)
    assert "doNotLeakThisSignature" not in redacted_bearer
    assert "[REDACTED_TOKEN]" in redacted_bearer

    # OpenRouter API Key
    api_key = "test-openrouter-key"

    # Password assignment
    raw_pw = "DB_PASSWORD=my_super_secure_password"
    redacted_pw = redact_text(raw_pw)
    assert "my_super_secure_password" not in redacted_pw
    assert "[REDACTED_SECRET]" in redacted_pw


def test_sanitize_investigation_payload():
    """Verify payload sanitizer removes secrets across all fields."""
    payload = InvestigationPayload(
        pods=PodInspectionResult(
            healthy=False,
            total_pods=1,
            problematic_pods=[
                ProblematicPod(
                    name="auth-service-79b8",
                    namespace="prod",
                    status="CrashLoopBackOff",
                    message="Secret DB_PASSWORD=my_secret_pw",
                )
            ],
        ),
        logs=LogsCollectionResult(
            collected=True,
            pod_logs=[
                PodLog(
                    pod_name="auth-service-79b8",
                    namespace="prod",
                    logs="Connection failed to postgres://user:mypassword@db.prod:5432/app",
                )
            ],
        ),
    )

    sanitized = sanitize_investigation_payload(payload)
    assert "my_secret_pw" not in str(sanitized)
    assert "mypassword" not in str(sanitized)
    assert "[REDACTED_SECRET]" in sanitized["pods"]["problematic_pods"][0]["message"]
    assert "[REDACTED_PASSWORD]" in sanitized["logs"]["pod_logs"][0]["logs"]


# ---------------------------------------------------------------------------
# 2. Prompt Builder Tests
# ---------------------------------------------------------------------------

def test_prompt_builder():
    """Verify system prompt and user prompt formatting."""
    assert "Senior Kubernetes Site Reliability Engineer" in SYSTEM_PROMPT
    assert "root_cause" in SYSTEM_PROMPT
    assert "confidence" in SYSTEM_PROMPT

    mock_evidence = {
        "pods": {"healthy": False, "problematic_pods": [{"name": "api", "status": "CrashLoopBackOff"}]}
    }
    user_prompt = build_troubleshooting_prompt(mock_evidence)
    assert "CrashLoopBackOff" in user_prompt
    assert "root_cause" in user_prompt


# ---------------------------------------------------------------------------
# 3. Confidence Engine Tests
# ---------------------------------------------------------------------------

def test_confidence_engine_with_strong_evidence():
    """Verify high confidence when pod status and direct logs align."""
    evidence = {
        "pods": {
            "problematic_pods": [
                {"name": "payment-service", "status": "CrashLoopBackOff"}
            ]
        },
        "logs": {
            "pod_logs": [
                {"pod_name": "payment-service", "logs": "FATAL: DATABASE_URL environment variable is required"}
            ]
        },
        "events": {
            "warning_events": [{"reason": "BackOff", "message": "Back-off restarting failed container"}]
        },
        "deployments": {"unhealthy_deployments": []},
        "network": {"services": []},
    }

    confidence, reasoning = ConfidenceEngine.evaluate(evidence, llm_confidence=92)
    assert confidence >= 85
    assert "Strengths" in reasoning
    assert "clearly identifiable" in reasoning


def test_confidence_engine_with_weak_evidence():
    """Verify confidence drops when no logs are available."""
    evidence = {
        "pods": {
            "problematic_pods": [
                {"name": "unknown-service", "status": "Error"}
            ]
        },
        "logs": {"pod_logs": []},
        "events": {"warning_events": []},
        "deployments": {"unhealthy_deployments": []},
        "network": {"services": []},
    }

    confidence, reasoning = ConfidenceEngine.evaluate(evidence, llm_confidence=90)
    assert confidence < 75
    assert "Uncertainties" in reasoning
    assert "No container logs available" in reasoning


# ---------------------------------------------------------------------------
# 4. LLM Client Extraction Tests
# ---------------------------------------------------------------------------

def test_llm_client_extract_json():
    """Verify JSON extraction handles clean JSON and fenced JSON."""
    raw_clean = '{"root_cause": "OOM", "confidence": 90}'
    data = LLMClient._extract_json(raw_clean)
    assert data["root_cause"] == "OOM"

    raw_fenced = '```json\n{"root_cause": "CrashLoopBackOff", "confidence": 88}\n```'
    data_fenced = LLMClient._extract_json(raw_fenced)
    assert data_fenced["root_cause"] == "CrashLoopBackOff"

    with pytest.raises(LLMClientError):
        LLMClient._extract_json("Not a json string at all")


# ---------------------------------------------------------------------------
# 5. AI Reasoning Engine with Mocked LLM Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_reasoning_with_mocked_llm():
    """Verify LLM diagnosis is validated and calibrated properly."""
    mock_payload = InvestigationPayload(
        pods=PodInspectionResult(
            healthy=False,
            total_pods=1,
            problematic_pods=[
                ProblematicPod(
                    name="payment-service-58d9",
                    namespace="default",
                    status="CrashLoopBackOff",
                    restart_count=5,
                )
            ],
        ),
        logs=LogsCollectionResult(
            collected=True,
            pod_logs=[
                PodLog(
                    pod_name="payment-service-58d9",
                    namespace="default",
                    logs="FATAL: DATABASE_URL not set in environment",
                )
            ],
        ),
        events=EventsAnalysisResult(
            healthy=False,
            warning_events=[
                ClusterEvent(
                    reason="BackOff",
                    message="Back-off restarting failed container",
                    involved_object="Pod/payment-service-58d9",
                )
            ],
        ),
    )

    mock_llm_response = {
        "root_cause": "Application failed because DATABASE_URL environment variable is missing",
        "explanation": "Payment service process exited with code 1 due to missing database connection parameters.",
        "fix": "Add the DATABASE_URL environment variable to the deployment manifest.",
        "kubectl_command": "kubectl set env deployment/payment-service DATABASE_URL=postgresql://user:pass@db:5432/app",
        "prevention_recommendation": "Use Kubernetes Secrets and validate configuration in staging.",
        "confidence": 95,
        "confidence_reasoning": "Explicit fatal log and CrashLoopBackOff corroboration.",
    }

    mock_client = AsyncMock(spec=LLMClient)
    mock_client.is_configured = True
    mock_client.generate_completion.return_value = mock_llm_response

    engine = AIReasoningEngine(llm_client=mock_client)
    diagnosis = await engine.diagnose(mock_payload)

    assert isinstance(diagnosis, DiagnosisResult)
    assert "DATABASE_URL" in diagnosis.root_cause
    assert "kubectl set env" in diagnosis.kubectl_command
    assert diagnosis.confidence >= 85
    assert diagnosis.confidence_reasoning != ""


@pytest.mark.asyncio
async def test_ai_reasoning_healthy_cluster():
    """Verify completely healthy cluster produces clean 'No incident' diagnosis without LLM call."""
    healthy_payload = InvestigationPayload(
        pods=PodInspectionResult(healthy=True, total_pods=10),
        events=EventsAnalysisResult(healthy=True),
        deployments=DeploymentInspectionResult(healthy=True, total_deployments=3),
        network=NetworkInspectionResult(healthy=True),
    )

    mock_client = AsyncMock(spec=LLMClient)
    mock_client.is_configured = True

    engine = AIReasoningEngine(llm_client=mock_client)
    diagnosis = await engine.diagnose(healthy_payload)

    # LLM should NOT be called for a 100% healthy cluster
    mock_client.generate_completion.assert_not_called()
    assert diagnosis.root_cause == "No incident detected"
    assert diagnosis.confidence >= 95


@pytest.mark.asyncio
async def test_ai_reasoning_llm_failure_fallback():
    """Verify heuristic fallback handles LLM failure gracefully."""
    mock_payload = InvestigationPayload(
        pods=PodInspectionResult(
            healthy=False,
            total_pods=1,
            problematic_pods=[
                ProblematicPod(
                    name="web-frontend-99a",
                    namespace="default",
                    status="ImagePullBackOff",
                )
            ],
        ),
        logs=LogsCollectionResult(collected=True, pod_logs=[]),
    )

    mock_client = AsyncMock(spec=LLMClient)
    mock_client.is_configured = True
    mock_client.generate_completion.side_effect = LLMClientError("Network timeout connecting to OpenRouter")

    engine = AIReasoningEngine(llm_client=mock_client)
    diagnosis = await engine.diagnose(mock_payload)

    # Heuristic fallback should identify ImagePullBackOff
    assert "image pull failure" in diagnosis.root_cause.lower()
    assert "kubectl describe pod" in diagnosis.kubectl_command
    assert diagnosis.confidence >= 80


# ---------------------------------------------------------------------------
# 6. Integration Tests for Authentication, Investigation & Progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_investigate_unauthorized():
    """Verify POST /investigate without authentication credentials returns HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/investigate")

    assert response.status_code == 401
    assert "Missing authentication credentials" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_post_investigate_authorized():
    """Verify POST /investigate with authenticated user returns HTTP 200 with diagnosis."""
    from app.core.auth import AuthenticatedUser, get_current_user

    async def mock_user_override():
        return AuthenticatedUser(
            id="198a90de-33ce-4c3a-b613-476e9722ca6e",
            email="testuser@example.com",
            role="authenticated",
        )

    app.dependency_overrides[get_current_user] = mock_user_override

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/investigate?investigation_id=test-inv-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "investigation" in data
        assert "diagnosis" in data

        diagnosis = data["diagnosis"]
        assert "root_cause" in diagnosis
        assert "explanation" in diagnosis
        assert "fix" in diagnosis
        assert "kubectl_command" in diagnosis
        assert "confidence" in diagnosis
        assert isinstance(diagnosis["confidence"], int)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_progress_tracker():
    """Verify ProgressTracker records stages and notifies subscribers."""
    from app.services.progress import ProgressTracker

    inv_id = "test-track-999"
    ProgressTracker.start_investigation(inv_id)
    q = ProgressTracker.subscribe(inv_id)

    await ProgressTracker.update_stage(inv_id, "checking_pods")
    update = q.get_nowait()
    assert update["stage"] == "checking_pods"
    assert "checking_pods" in ProgressTracker.get_completed_stages(inv_id)

    ProgressTracker.unsubscribe(inv_id, q)


@pytest.mark.asyncio
async def test_history_service_graceful_failure():
    """Verify that history persistence failure does not crash the application."""
    from app.services.history import HistoryService

    history = HistoryService()
    # Pointing to invalid port to simulate network failure
    history._base_url = "http://127.0.0.1:59999"

    mock_diagnosis = DiagnosisResult(
        root_cause="Test Failure",
        explanation="Test Explanation",
        fix="Test Fix",
        kubectl_command="kubectl get pods",
        confidence=80,
    )

    success = await history.save_investigation(
        user_id="fake-user-id",
        diagnosis=mock_diagnosis,
    )
    # Must return False gracefully without raising unhandled exceptions
    assert success is False
