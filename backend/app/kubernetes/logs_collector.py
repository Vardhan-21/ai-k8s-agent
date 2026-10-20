"""Logs Collector — fetches recent logs for failing pods.

Focuses on capturing relevant failure evidence such as exceptions,
connection failures, missing env vars, image failures, and startup
errors.  Keeps output concise by limiting the number of tail lines.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import LogsCollectionResult, PodLog, ProblematicPod

# Maximum number of log lines to retrieve per container
_MAX_TAIL_LINES = 50


class LogsCollector:
    """Collect recent logs for problematic pods."""

    def __init__(self, executor: KubectlExecutor | None = None) -> None:
        self._executor = executor or KubectlExecutor()

    async def collect(
        self, problematic_pods: list[ProblematicPod]
    ) -> LogsCollectionResult:
        """Fetch logs for each problematic pod.

        Args:
            problematic_pods: List of pods identified as unhealthy.

        Returns:
            LogsCollectionResult containing log snippets for each pod.
        """
        if not problematic_pods:
            logger.info("No problematic pods — skipping log collection")
            return LogsCollectionResult(collected=True, pod_logs=[])

        logger.info(
            f"Collecting logs for {len(problematic_pods)} problematic pod(s)"
        )

        pod_logs: list[PodLog] = []

        for pod in problematic_pods:
            log_entry = await self._fetch_pod_logs(pod.name, pod.namespace)
            pod_logs.append(log_entry)

            # Also try to grab previous container logs (useful for
            # CrashLoopBackOff where the current container may have no logs)
            if pod.status in ("CrashLoopBackOff", "Error", "OOMKilled"):
                prev_log = await self._fetch_pod_logs(
                    pod.name, pod.namespace, previous=True
                )
                if prev_log.logs:
                    prev_log.container = f"{prev_log.container} (previous)"
                    pod_logs.append(prev_log)

        logger.info(f"Log collection complete — {len(pod_logs)} entries")
        return LogsCollectionResult(collected=True, pod_logs=pod_logs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _fetch_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        previous: bool = False,
    ) -> PodLog:
        """Fetch logs for a single pod."""
        cmd = (
            f"logs {pod_name} -n {namespace} "
            f"--tail={_MAX_TAIL_LINES} --timestamps"
        )
        if previous:
            cmd += " --previous"

        result = await self._executor.execute(cmd)

        if not result.success:
            return PodLog(
                pod_name=pod_name,
                namespace=namespace,
                logs="",
                error=result.error,
            )

        return PodLog(
            pod_name=pod_name,
            namespace=namespace,
            logs=result.output,
        )
