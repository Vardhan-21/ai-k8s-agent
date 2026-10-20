"""Confidence Engine — evaluates evidence certainty and calibrates diagnosis confidence.

Calculates confidence using explicit evidence-based criteria and explains uncertainty
rather than accepting unverified LLM confidence scores.
"""

from __future__ import annotations

from typing import Any


class ConfidenceEngine:
    """Calculates evidence-based confidence scores and rationale for diagnoses."""

    @staticmethod
    def evaluate(
        sanitized_evidence: dict[str, Any],
        llm_confidence: int,
        llm_reasoning: str = "",
    ) -> tuple[int, str]:
        """Evaluate evidence quality, compute objective confidence score, and explain certainty.

        Args:
            sanitized_evidence: Sanitized investigation dictionary.
            llm_confidence: Proposed confidence from LLM (0-100).
            llm_reasoning: Rationale provided by the LLM.

        Returns:
            Tuple of (calibrated_confidence: int, confidence_reasoning: str).
        """
        pods = sanitized_evidence.get("pods", {})
        logs = sanitized_evidence.get("logs", {})
        events = sanitized_evidence.get("events", {})
        deployments = sanitized_evidence.get("deployments", {})
        network = sanitized_evidence.get("network", {})

        problematic_pods = pods.get("problematic_pods", [])
        pod_logs = logs.get("pod_logs", [])
        warning_events = events.get("warning_events", [])
        unhealthy_deployments = deployments.get("unhealthy_deployments", [])
        network_issues = [s for s in network.get("services", []) if s.get("issues")]

        # If everything is healthy, confidence in cluster health is high
        if (
            not problematic_pods
            and not warning_events
            and not unhealthy_deployments
            and not network_issues
        ):
            return 95, "Cluster is fully healthy across pods, events, deployments, and services."

        evidence_score = 40  # Baseline
        supporting_factors: list[str] = []
        uncertainty_factors: list[str] = []

        # 1. Pod failure specificity
        specific_reasons = {
            "CrashLoopBackOff",
            "ImagePullBackOff",
            "ErrImagePull",
            "OOMKilled",
            "CreateContainerConfigError",
        }
        has_specific_pod_state = any(
            p.get("status") in specific_reasons for p in problematic_pods
        )
        if has_specific_pod_state:
            evidence_score += 20
            supporting_factors.append("Pod failure state is clearly identifiable")
        elif problematic_pods:
            evidence_score += 10
            uncertainty_factors.append("Pod state is generic (e.g. Pending/Error)")

        # 2. Corroborating logs
        logs_with_content = [
            l for l in pod_logs if l.get("logs") and len(l.get("logs").strip()) > 10
        ]
        if logs_with_content:
            evidence_score += 25
            supporting_factors.append("Direct container error logs captured")
        elif problematic_pods:
            evidence_score -= 15
            uncertainty_factors.append("No container logs available for failing pods")

        # 3. Corroborating events
        if warning_events:
            evidence_score += 15
            supporting_factors.append(
                f"{len(warning_events)} relevant Kubernetes warning events found"
            )

        # 4. Deployment or Network correlation
        if unhealthy_deployments:
            evidence_score += 10
            supporting_factors.append("Deployment replica conditions confirm outage")

        if network_issues:
            evidence_score += 10
            supporting_factors.append("Service/endpoint routing issues detected")

        # Bound score between 10 and 98
        computed_score = max(10, min(98, evidence_score))

        # Harmonize with LLM score: take weighted average (60% evidence, 40% LLM)
        if 0 <= llm_confidence <= 100:
            final_score = int((computed_score * 0.6) + (llm_confidence * 0.4))
        else:
            final_score = computed_score

        # Build clear reasoning explanation
        reasons_parts: list[str] = []
        if supporting_factors:
            reasons_parts.append(f"Strengths: {'; '.join(supporting_factors)}.")
        if uncertainty_factors:
            reasons_parts.append(f"Uncertainties: {'; '.join(uncertainty_factors)}.")
        if llm_reasoning:
            reasons_parts.append(f"LLM assessment: {llm_reasoning}")

        final_reasoning = " ".join(reasons_parts).strip() or "Evaluated based on gathered cluster evidence."

        return final_score, final_reasoning
