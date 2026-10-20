"""Pod Inspector — detects unhealthy pods in the cluster.

Checks for problematic pod states such as CrashLoopBackOff,
ImagePullBackOff, Pending, Error, OOMKilled, and stuck
ContainerCreating.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import PodInspectionResult, ProblematicPod

# Pod phases / reasons we consider unhealthy
UNHEALTHY_STATES: set[str] = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "Pending",
    "Error",
    "OOMKilled",
    "ContainerCreating",
    "CreateContainerConfigError",
    "RunContainerError",
    "InvalidImageName",
    "ContainerStatusUnknown",
}


class PodInspector:
    """Inspect cluster pods and surface unhealthy ones."""

    def __init__(self, executor: KubectlExecutor | None = None) -> None:
        self._executor = executor or KubectlExecutor()

    async def inspect(self) -> PodInspectionResult:
        """Run ``kubectl get pods -A -o json`` and analyse the results."""
        logger.info("Inspecting pods across all namespaces")

        success, data, error = await self._executor.execute_json("get pods -A")

        if not success or data is None:
            logger.error(f"Pod inspection failed: {error}")
            return PodInspectionResult(healthy=False, error=error)

        items: list[dict] = data.get("items", [])
        problematic: list[ProblematicPod] = []

        for pod in items:
            metadata = pod.get("metadata", {})
            status_block = pod.get("status", {})
            pod_name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "default")
            phase = status_block.get("phase", "Unknown")

            # Check container statuses for specific failure reasons
            container_statuses = status_block.get("containerStatuses", [])
            init_container_statuses = status_block.get(
                "initContainerStatuses", []
            )

            pod_issue = self._check_containers(
                pod_name, namespace, container_statuses
            )
            if pod_issue:
                problematic.append(pod_issue)
                continue

            init_issue = self._check_containers(
                pod_name, namespace, init_container_statuses
            )
            if init_issue:
                problematic.append(init_issue)
                continue

            # Check if the pod phase itself is problematic
            if phase in ("Pending", "Failed", "Unknown"):
                reason = status_block.get("reason", phase)
                message = status_block.get("message", "")
                problematic.append(
                    ProblematicPod(
                        name=pod_name,
                        namespace=namespace,
                        status=phase,
                        reason=reason,
                        message=message,
                    )
                )

        healthy = len(problematic) == 0
        logger.info(
            f"Pod inspection complete — {len(items)} pods, "
            f"{len(problematic)} problematic"
        )

        return PodInspectionResult(
            healthy=healthy,
            total_pods=len(items),
            problematic_pods=problematic,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_containers(
        pod_name: str,
        namespace: str,
        container_statuses: list[dict],
    ) -> ProblematicPod | None:
        """Return a ProblematicPod if any container is in a bad state."""
        for cs in container_statuses:
            restart_count = cs.get("restartCount", 0)
            state = cs.get("state", {})

            # Waiting states (CrashLoopBackOff, ImagePullBackOff, etc.)
            waiting = state.get("waiting", {})
            if waiting:
                reason = waiting.get("reason", "")
                if reason in UNHEALTHY_STATES:
                    return ProblematicPod(
                        name=pod_name,
                        namespace=namespace,
                        status=reason,
                        reason=reason,
                        restart_count=restart_count,
                        message=waiting.get("message", ""),
                    )

            # Terminated with error
            terminated = state.get("terminated", {})
            if terminated:
                reason = terminated.get("reason", "")
                exit_code = terminated.get("exitCode", 0)
                if reason in UNHEALTHY_STATES or exit_code != 0:
                    return ProblematicPod(
                        name=pod_name,
                        namespace=namespace,
                        status=reason or f"ExitCode:{exit_code}",
                        reason=reason,
                        restart_count=restart_count,
                        message=terminated.get("message", ""),
                    )

        return None
