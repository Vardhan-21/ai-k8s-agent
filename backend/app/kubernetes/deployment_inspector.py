"""Deployment Inspector — checks deployment health across the cluster.

Detects unavailable replicas, rollout failures, and problematic
deployment conditions.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import DeploymentInspectionResult, DeploymentStatus


class DeploymentInspector:
    """Inspect deployments and surface unhealthy ones."""

    def __init__(self, executor: KubectlExecutor | None = None) -> None:
        self._executor = executor or KubectlExecutor()

    async def inspect(self) -> DeploymentInspectionResult:
        """Run ``kubectl get deployments -A -o json`` and analyse."""
        logger.info("Inspecting deployments across all namespaces")

        success, data, error = await self._executor.execute_json(
            "get deployments -A"
        )

        if not success or data is None:
            logger.error(f"Deployment inspection failed: {error}")
            return DeploymentInspectionResult(healthy=False, error=error)

        items: list[dict] = data.get("items", [])
        unhealthy: list[DeploymentStatus] = []

        for dep in items:
            metadata = dep.get("metadata", {})
            spec = dep.get("spec", {})
            status_block = dep.get("status", {})

            name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "default")

            desired = spec.get("replicas", 0)
            available = status_block.get("availableReplicas", 0) or 0
            unavailable = status_block.get("unavailableReplicas", 0) or 0

            # Collect condition messages
            conditions: list[str] = []
            for cond in status_block.get("conditions", []):
                cond_type = cond.get("type", "")
                cond_status = cond.get("status", "")
                cond_msg = cond.get("message", "")
                if cond_status != "True" or cond_type in (
                    "ReplicaFailure",
                    "Progressing",
                ):
                    conditions.append(
                        f"{cond_type}={cond_status}: {cond_msg}"
                    )

            is_ready = available >= desired and unavailable == 0

            if not is_ready:
                unhealthy.append(
                    DeploymentStatus(
                        name=name,
                        namespace=namespace,
                        desired_replicas=desired,
                        available_replicas=available,
                        unavailable_replicas=unavailable,
                        ready=False,
                        conditions=conditions,
                    )
                )

        healthy = len(unhealthy) == 0
        logger.info(
            f"Deployment inspection complete — {len(items)} deployments, "
            f"{len(unhealthy)} unhealthy"
        )

        return DeploymentInspectionResult(
            healthy=healthy,
            total_deployments=len(items),
            unhealthy_deployments=unhealthy,
        )
