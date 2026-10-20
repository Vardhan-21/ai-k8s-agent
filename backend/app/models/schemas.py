"""Pydantic schemas for request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    service: str


# ---------------------------------------------------------------------------
# Pod inspection
# ---------------------------------------------------------------------------

class ProblematicPod(BaseModel):
    """A single pod that is in an unhealthy state."""

    name: str
    namespace: str
    status: str
    reason: str = ""
    restart_count: int = 0
    message: str = ""


class PodInspectionResult(BaseModel):
    """Result of inspecting all pods in the cluster."""

    healthy: bool = True
    total_pods: int = 0
    problematic_pods: list[ProblematicPod] = Field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Logs collection
# ---------------------------------------------------------------------------

class PodLog(BaseModel):
    """Log snippet for a single pod."""

    pod_name: str
    namespace: str
    container: str = ""
    logs: str = ""
    error: str = ""


class LogsCollectionResult(BaseModel):
    """Result of collecting logs for failing pods."""

    collected: bool = True
    pod_logs: list[PodLog] = Field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Events analysis
# ---------------------------------------------------------------------------

class ClusterEvent(BaseModel):
    """A single noteworthy Kubernetes event."""

    type: str = ""
    reason: str = ""
    message: str = ""
    namespace: str = ""
    involved_object: str = ""
    count: int = 1
    last_seen: str = ""


class EventsAnalysisResult(BaseModel):
    """Result of analyzing cluster events."""

    healthy: bool = True
    warning_events: list[ClusterEvent] = Field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Deployment inspection
# ---------------------------------------------------------------------------

class DeploymentStatus(BaseModel):
    """Status of a single deployment."""

    name: str
    namespace: str
    desired_replicas: int = 0
    available_replicas: int = 0
    unavailable_replicas: int = 0
    ready: bool = True
    conditions: list[str] = Field(default_factory=list)


class DeploymentInspectionResult(BaseModel):
    """Result of inspecting deployments."""

    healthy: bool = True
    total_deployments: int = 0
    unhealthy_deployments: list[DeploymentStatus] = Field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Network inspection
# ---------------------------------------------------------------------------

class ServiceStatus(BaseModel):
    """Status of a single Kubernetes service."""

    name: str
    namespace: str
    type: str = ""
    cluster_ip: str = ""
    has_endpoints: bool = True
    selector_mismatch: bool = False
    issues: list[str] = Field(default_factory=list)


class NetworkInspectionResult(BaseModel):
    """Result of inspecting cluster networking."""

    healthy: bool = True
    services: list[ServiceStatus] = Field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Full investigation
# ---------------------------------------------------------------------------

class InvestigationPayload(BaseModel):
    """Complete investigation evidence gathered from the cluster."""

    pods: PodInspectionResult = Field(default_factory=PodInspectionResult)
    logs: LogsCollectionResult = Field(default_factory=LogsCollectionResult)
    events: EventsAnalysisResult = Field(default_factory=EventsAnalysisResult)
    deployments: DeploymentInspectionResult = Field(
        default_factory=DeploymentInspectionResult
    )
    network: NetworkInspectionResult = Field(
        default_factory=NetworkInspectionResult
    )


# ---------------------------------------------------------------------------
# AI Diagnosis
# ---------------------------------------------------------------------------

class DiagnosisResult(BaseModel):
    """Structured AI diagnosis produced by the Senior SRE reasoning engine."""

    root_cause: str
    explanation: str
    fix: str
    kubectl_command: str
    prevention_recommendation: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    confidence_reasoning: str = ""


class InvestigationResponse(BaseModel):
    """Top-level response for POST /investigate."""

    status: str = "success"
    context: str | None = None
    investigation: InvestigationPayload = Field(
        default_factory=InvestigationPayload
    )
    diagnosis: DiagnosisResult | None = None


# ---------------------------------------------------------------------------
# Cluster Contexts
# ---------------------------------------------------------------------------

class ClusterContextInfo(BaseModel):
    """Safe metadata for a Kubernetes context from kubeconfig."""

    name: str
    cluster: str
    user: str = ""
    is_current: bool = False
    server: str = ""
    status: str = "unknown"  # "reachable", "unreachable", "unknown"
    error: str | None = None


class ContextsListResponse(BaseModel):
    """Response schema for listing available Kubernetes contexts."""

    contexts: list[ClusterContextInfo] = Field(default_factory=list)
    current_context: str | None = None
    total: int = 0


class InvestigateRequest(BaseModel):
    """Request payload for triggering an investigation."""

    context: str | None = None
