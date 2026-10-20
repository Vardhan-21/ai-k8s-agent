"""Secret sanitizer for Kubernetes evidence.

Treats logs, events, and pod manifests as untrusted input.
Redacts API keys, credentials, tokens, passwords, and private keys
before sending evidence to the LLM reasoning engine.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.schemas import (
    ClusterEvent,
    DeploymentInspectionResult,
    EventsAnalysisResult,
    InvestigationPayload,
    LogsCollectionResult,
    NetworkInspectionResult,
    PodInspectionResult,
    PodLog,
    ProblematicPod,
    ServiceStatus,
)

# Common secret patterns
_PATTERNS = [
    # Connection strings with credentials (postgres, mysql, mongodb, redis, etc.)
    (
        re.compile(r"(?i)([a-z0-9+.-]+://[^:\s]+):([^@\s/]+)(@[^\s/]+)"),
        r"\1:[REDACTED_PASSWORD]\3",
    ),
    # Bearer / JWT tokens
    (
        re.compile(r"(?i)\b(bearer\s+)(ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]*)"),
        r"\1[REDACTED_TOKEN]",
    ),
    # Standalone JWTs
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]+\b"),
        "[REDACTED_JWT]",
    ),
    # PEM Private keys
    (
        re.compile(
            r"-----BEGIN [A-Z\s]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z\s]+ PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # AWS Access Key IDs
    (
        re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    # OpenRouter / OpenAI-style keys (sk-..., ik_...)
    (
        re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,}|ik_[a-zA-Z0-9]{20,})\b"),
        "[REDACTED_API_KEY]",
    ),
    # Common secret/token/password assignments in env strings or logs (e.g. DB_PASSWORD=..., SECRET_KEY: ...)
    (
        re.compile(
            r"(?i)\b([a-z0-9_-]*(?:password|passwd|secret|api_key|apikey|auth_token|access_token|private_key|client_secret)[a-z0-9_-]*)\s*[:=]\s*(?!\[REDACTED)([\"']?[^\"'\s,;]{4,}[\"']?)"
        ),
        r"\1=[REDACTED_SECRET]",
    ),
]


def redact_text(text: str) -> str:
    """Redact sensitive patterns from a given text string."""
    if not text:
        return text

    sanitized = text
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def sanitize_investigation_payload(payload: InvestigationPayload) -> dict[str, Any]:
    """Sanitize the entire investigation payload into a clean, safe dict for LLM consumption.

    Redacts all logs, events, error messages, and pod annotations/messages.
    """
    # 1. Sanitize Pods
    sanitized_problematic_pods = [
        {
            "name": pod.name,
            "namespace": pod.namespace,
            "status": pod.status,
            "reason": pod.reason,
            "restart_count": pod.restart_count,
            "message": redact_text(pod.message),
        }
        for pod in payload.pods.problematic_pods
    ]

    # 2. Sanitize Logs
    sanitized_pod_logs = [
        {
            "pod_name": log.pod_name,
            "namespace": log.namespace,
            "container": log.container,
            "logs": redact_text(log.logs),
            "error": redact_text(log.error),
        }
        for log in payload.logs.pod_logs
    ]

    # 3. Sanitize Events
    sanitized_events = [
        {
            "type": ev.type,
            "reason": ev.reason,
            "message": redact_text(ev.message),
            "namespace": ev.namespace,
            "involved_object": ev.involved_object,
            "count": ev.count,
            "last_seen": ev.last_seen,
        }
        for ev in payload.events.warning_events
    ]

    # 4. Sanitize Deployments
    sanitized_deployments = [
        {
            "name": dep.name,
            "namespace": dep.namespace,
            "desired_replicas": dep.desired_replicas,
            "available_replicas": dep.available_replicas,
            "unavailable_replicas": dep.unavailable_replicas,
            "ready": dep.ready,
            "conditions": [redact_text(c) for c in dep.conditions],
        }
        for dep in payload.deployments.unhealthy_deployments
    ]

    # 5. Sanitize Network
    sanitized_services = [
        {
            "name": svc.name,
            "namespace": svc.namespace,
            "type": svc.type,
            "cluster_ip": svc.cluster_ip,
            "has_endpoints": svc.has_endpoints,
            "selector_mismatch": svc.selector_mismatch,
            "issues": [redact_text(iss) for iss in svc.issues],
        }
        for svc in payload.network.services
    ]

    return {
        "pods": {
            "healthy": payload.pods.healthy,
            "total_pods": payload.pods.total_pods,
            "problematic_pods": sanitized_problematic_pods,
            "error": redact_text(payload.pods.error),
        },
        "logs": {
            "collected": payload.logs.collected,
            "pod_logs": sanitized_pod_logs,
            "error": redact_text(payload.logs.error),
        },
        "events": {
            "healthy": payload.events.healthy,
            "warning_events": sanitized_events,
            "error": redact_text(payload.events.error),
        },
        "deployments": {
            "healthy": payload.deployments.healthy,
            "total_deployments": payload.deployments.total_deployments,
            "unhealthy_deployments": sanitized_deployments,
            "error": redact_text(payload.deployments.error),
        },
        "network": {
            "healthy": payload.network.healthy,
            "services": sanitized_services,
            "error": redact_text(payload.network.error),
        },
    }
