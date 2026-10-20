"""AI Reasoning Engine for Kubernetes Troubleshooting.

Orchestrates prompt building, LLM client execution, root cause analysis,
fix recommendations, confidence evaluation, and heuristic fallbacks.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.ai.confidence_engine import ConfidenceEngine
from app.ai.llm_client import LLMClient, LLMClientError
from app.ai.prompt_builder import SYSTEM_PROMPT, build_troubleshooting_prompt
from app.ai.sanitizer import sanitize_investigation_payload
from app.models.schemas import DiagnosisResult, InvestigationPayload


class AIReasoningEngine:
    """Senior Kubernetes SRE reasoning engine for incident diagnosis."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()
        self._confidence_engine = ConfidenceEngine()

    async def diagnose(self, payload: InvestigationPayload) -> DiagnosisResult:
        """Analyze Kubernetes investigation evidence and produce a structured diagnosis.

        Args:
            payload: Evidence gathered by the investigation layer.

        Returns:
            DiagnosisResult with root cause, explanation, fix, kubectl command, and confidence.
        """
        # 1. Check if cluster connection/kubectl failed entirely
        if self._is_cluster_unreachable(payload):
            return self._build_cluster_unreachable_diagnosis(payload)

        # 2. Check if cluster is completely healthy
        if self._is_cluster_healthy(payload):
            return self._build_healthy_diagnosis()

        # 3. Sanitize evidence before sending to LLM (Safeguard: Redact secrets)
        sanitized_evidence = sanitize_investigation_payload(payload)

        # 4. Attempt LLM reasoning if client is configured
        if self._llm_client.is_configured:
            try:
                user_prompt = build_troubleshooting_prompt(sanitized_evidence)
                logger.info("Executing LLM reasoning via OpenRouter...")
                raw_response = await self._llm_client.generate_completion(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )

                # Calibrate confidence using explicit evidence-based criteria
                raw_confidence = int(raw_response.get("confidence", 70))
                llm_reasoning = raw_response.get("confidence_reasoning", "")
                calibrated_confidence, confidence_reasoning = (
                    self._confidence_engine.evaluate(
                        sanitized_evidence, raw_confidence, llm_reasoning
                    )
                )

                return DiagnosisResult(
                    root_cause=raw_response.get(
                        "root_cause", "Unspecified Kubernetes issue detected."
                    ),
                    explanation=raw_response.get(
                        "explanation",
                        "Failure detected during cluster inspection.",
                    ),
                    fix=raw_response.get(
                        "fix",
                        "Review pod logs and deployment configuration.",
                    ),
                    kubectl_command=raw_response.get(
                        "kubectl_command", "kubectl get pods,events -A"
                    ),
                    prevention_recommendation=raw_response.get(
                        "prevention_recommendation",
                        "Implement health checks and resource limits.",
                    ),
                    confidence=calibrated_confidence,
                    confidence_reasoning=confidence_reasoning,
                )
            except LLMClientError as exc:
                logger.warning(
                    f"LLM reasoning failed, falling back to heuristic engine: {exc}"
                )
            except Exception as exc:
                logger.error(
                    f"Unexpected error in LLM reasoning: {exc}", exc_info=True
                )

        # 5. Fallback: Rule-based SRE heuristic engine
        logger.info("Using rule-based SRE heuristic engine for diagnosis")
        return self._heuristic_diagnosis(sanitized_evidence)

    # ----------------------------------------------------------------------
    # Health and Connectivity Checks
    # ----------------------------------------------------------------------

    @staticmethod
    def _is_cluster_healthy(payload: InvestigationPayload) -> bool:
        """Return True if all components reported clean health without errors."""
        has_no_pod_issues = (
            payload.pods.healthy and len(payload.pods.problematic_pods) == 0
        )
        has_no_events = (
            payload.events.healthy and len(payload.events.warning_events) == 0
        )
        has_no_dep_issues = (
            payload.deployments.healthy
            and len(payload.deployments.unhealthy_deployments) == 0
        )
        has_no_network_issues = (
            payload.network.healthy and len(payload.network.services) == 0
        )
        has_no_errors = not (
            payload.pods.error
            or payload.events.error
            or payload.deployments.error
            or payload.network.error
        )

        return (
            has_no_pod_issues
            and has_no_events
            and has_no_dep_issues
            and has_no_network_issues
            and has_no_errors
        )

    @staticmethod
    def _is_cluster_unreachable(payload: InvestigationPayload) -> bool:
        """Check if kubectl failed to reach the cluster API server."""
        errors = [
            payload.pods.error,
            payload.events.error,
            payload.deployments.error,
            payload.network.error,
        ]
        connectivity_keywords = [
            "connection refused",
            "kubectl: not found",
            "couldn't get current server API group list",
            "Unable to connect to the server",
            "no configuration has been provided",
            "Unauthorized",
        ]
        return any(
            any(kw.lower() in err.lower() for kw in connectivity_keywords)
            for err in errors
            if err
        )

    @staticmethod
    def _build_cluster_unreachable_diagnosis(
        payload: InvestigationPayload,
    ) -> DiagnosisResult:
        """Construct diagnosis when cluster is unreachable."""
        error_msg = (
            payload.pods.error
            or payload.events.error
            or "Connection to Kubernetes API server failed"
        )
        return DiagnosisResult(
            root_cause="Kubernetes API server unreachable",
            explanation=(
                f"The investigation engine was unable to communicate with the cluster. "
                f"Error detail: {error_msg.splitlines()[-1] if error_msg else 'Unknown'}"
            ),
            fix=(
                "Verify that your kubeconfig is properly configured and the cluster is online. "
                "Set KUBECONFIG_PATH in backend/.env to a valid kubeconfig file."
            ),
            kubectl_command="kubectl cluster-info",
            prevention_recommendation=(
                "Ensure network routes to the control plane are open and credentials have not expired."
            ),
            confidence=95,
            confidence_reasoning="High confidence: kubectl command execution returned connection refused or cluster unreachable.",
        )

    @staticmethod
    def _build_healthy_diagnosis() -> DiagnosisResult:
        """Construct diagnosis for a completely healthy cluster."""
        return DiagnosisResult(
            root_cause="No incident detected",
            explanation="All inspected pods, deployments, warning events, and network services are in a healthy state.",
            fix="No remediation required. The cluster workloads are operating normally.",
            kubectl_command="kubectl get nodes,pods,svc -A",
            prevention_recommendation="Maintain automated monitoring, alerts, and resource quotas to prevent future incidents.",
            confidence=98,
            confidence_reasoning="High confidence: All Kubernetes health checks passed without warnings or errors.",
        )

    # ----------------------------------------------------------------------
    # Heuristic SRE Fallback Engine
    # ----------------------------------------------------------------------

    def _heuristic_diagnosis(
        self, evidence: dict[str, Any]
    ) -> DiagnosisResult:
        """Deterministic SRE heuristic diagnosis based on gathered evidence."""
        problematic_pods = evidence.get("pods", {}).get(
            "problematic_pods", []
        )
        pod_logs = evidence.get("logs", {}).get("pod_logs", [])
        warning_events = evidence.get("events", {}).get("warning_events", [])
        unhealthy_deps = evidence.get("deployments", {}).get(
            "unhealthy_deployments", []
        )
        network_services = evidence.get("network", {}).get("services", [])

        # Priority 1: Pod failures with logs
        if problematic_pods:
            top_pod = problematic_pods[0]
            pod_name = top_pod.get("name", "unknown")
            ns = top_pod.get("namespace", "default")
            status = top_pod.get("status", "Unknown")

            # Check logs for this pod
            matching_log = next(
                (l for l in pod_logs if l.get("pod_name") == pod_name), {}
            )
            log_text = matching_log.get("logs", "")

            # Missing environment variable
            if (
                "not set" in log_text.lower()
                or "missing" in log_text.lower()
                or "required" in log_text.lower()
            ):
                import re

                env_match = re.search(
                    r"([A-Z0-9_]{3,})\s+(?:is\s+)?(?:not set|missing|required)",
                    log_text,
                    re.IGNORECASE,
                )
                var_name = (
                    env_match.group(1)
                    if env_match
                    else "required environment variable"
                )
                return DiagnosisResult(
                    root_cause=f"Application failed to start due to missing environment variable ({var_name})",
                    explanation=f"Pod {pod_name} in namespace {ns} is in {status}. Logs show failure: {log_text.splitlines()[-1] if log_text else 'Startup failure'}",
                    fix=f"Configure the missing environment variable {var_name} in the deployment or secret.",
                    kubectl_command=f"kubectl set env deployment/{pod_name.split('-')[0]} {var_name}=<VALUE> -n {ns}",
                    prevention_recommendation="Use ConfigMaps and Secrets with schema validation in your deployment manifests.",
                    confidence=92,
                    confidence_reasoning="High confidence: Pod state is CrashLoopBackOff and container logs explicitly cite missing environment variable.",
                )

            # Image pull failure
            if status in ("ImagePullBackOff", "ErrImagePull"):
                return DiagnosisResult(
                    root_cause=f"Container image pull failure on pod {pod_name}",
                    explanation=f"Pod {pod_name} cannot pull its container image. The image may not exist or credentials may be missing.",
                    fix="Verify image name, tag, and imagePullSecrets in the pod specification.",
                    kubectl_command=f"kubectl describe pod {pod_name} -n {ns}",
                    prevention_recommendation="Validate image tags in CI/CD pipeline before triggering Kubernetes deployments.",
                    confidence=90,
                    confidence_reasoning="High confidence: Pod state is ImagePullBackOff / ErrImagePull.",
                )

            # OOMKilled
            if "OOMKilled" in status or "137" in str(top_pod.get("message", "")):
                return DiagnosisResult(
                    root_cause=f"Container OOMKilled (Out of Memory) on pod {pod_name}",
                    explanation=f"Pod {pod_name} exceeded its configured container memory limits and was terminated by the Linux kernel OOM killer.",
                    fix="Increase the memory limit in the deployment resource specifications.",
                    kubectl_command=f"kubectl edit deployment/{pod_name.split('-')[0]} -n {ns}",
                    prevention_recommendation="Profile application memory consumption and set appropriate resource requests and limits.",
                    confidence=94,
                    confidence_reasoning="High confidence: Pod termination status is OOMKilled with exit code 137.",
                )

            # Generic CrashLoopBackOff
            if status == "CrashLoopBackOff":
                return DiagnosisResult(
                    root_cause=f"Application crash on startup in pod {pod_name}",
                    explanation=f"Pod {pod_name} repeatedly exits immediately after launching. Message: {top_pod.get('message', 'Process terminated')}",
                    fix="Inspect application logs and entrypoint configuration to address startup crash.",
                    kubectl_command=f"kubectl logs {pod_name} -n {ns} --previous",
                    prevention_recommendation="Add startup probes and verify application startup dependencies before deployment.",
                    confidence=85,
                    confidence_reasoning="Strong confidence: CrashLoopBackOff state detected; container logs inspection recommended.",
                )

        # Priority 2: Unhealthy deployments
        if unhealthy_deps:
            dep = unhealthy_deps[0]
            dep_name = dep.get("name", "unknown")
            ns = dep.get("namespace", "default")
            return DiagnosisResult(
                root_cause=f"Deployment rollout stalled for {dep_name}",
                explanation=f"Deployment {dep_name} in namespace {ns} has {dep.get('unavailable_replicas', 0)} unavailable replica(s). Conditions: {'; '.join(dep.get('conditions', []))}",
                fix="Inspect deployment rollout status and describe replica set for failure events.",
                kubectl_command=f"kubectl rollout status deployment/{dep_name} -n {ns}",
                prevention_recommendation="Configure rolling update parameters with maxSurge and maxUnavailable to prevent complete outages.",
                confidence=85,
                confidence_reasoning="Deployment replica count and condition metrics show stalled rollout.",
            )

        # Priority 3: Network issues
        if network_services:
            svc = network_services[0]
            svc_name = svc.get("name", "unknown")
            ns = svc.get("namespace", "default")
            return DiagnosisResult(
                root_cause=f"Service {svc_name} has no available endpoints",
                explanation=f"Service {svc_name} in namespace {ns} cannot route traffic because it has no ready pod endpoints. Selector mismatch or pod crashes likely.",
                fix="Check service selector labels against pod labels to ensure they match.",
                kubectl_command=f"kubectl describe svc {svc_name} -n {ns}",
                prevention_recommendation="Use automated linting for Kubernetes labels and selectors.",
                confidence=82,
                confidence_reasoning="Service endpoints check confirmed 0 ready addresses for the target service.",
            )

        # Generic fallback
        return DiagnosisResult(
            root_cause="Kubernetes cluster anomalies detected",
            explanation="Unhealthy cluster resources or warning events were identified during the investigation.",
            fix="Inspect active warning events and pod statuses across all namespaces.",
            kubectl_command="kubectl get events --sort-by='.lastTimestamp' -A",
            prevention_recommendation="Implement Prometheus/Grafana alerting on warning events and restart counts.",
            confidence=60,
            confidence_reasoning="Moderate confidence: Symptoms detected across cluster events and resources.",
        )
