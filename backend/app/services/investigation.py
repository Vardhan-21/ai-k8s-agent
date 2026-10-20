"""Investigation Service — orchestrates the full evidence-gathering pipeline.

Runs each inspector in order and assembles a single structured payload
that a downstream AI reasoning layer can consume.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.kubernetes.pod_inspector import PodInspector
from app.kubernetes.logs_collector import LogsCollector
from app.kubernetes.events_analyzer import EventsAnalyzer
from app.kubernetes.deployment_inspector import DeploymentInspector
from app.kubernetes.network_inspector import NetworkInspector
from app.models.schemas import InvestigationPayload
from app.services.progress import ProgressTracker


class InvestigationService:
    """Orchestrate a full cluster investigation.

    Flow:
        1. Check Pods
        2. Collect Logs (for any problematic pods found)
        3. Analyze Events
        4. Inspect Deployments
        5. Check Networking
    """

    def __init__(self, context: str | None = None) -> None:
        self._context = context
        self._executor = KubectlExecutor(context=context)
        self._pod_inspector = PodInspector(self._executor)
        self._logs_collector = LogsCollector(self._executor)
        self._events_analyzer = EventsAnalyzer(self._executor)
        self._deployment_inspector = DeploymentInspector(self._executor)
        self._network_inspector = NetworkInspector(self._executor)

    async def run(self, investigation_id: str | None = None) -> InvestigationPayload:
        """Execute the full investigation pipeline and return evidence."""
        logger.info(f"=== Starting cluster investigation (context: {self._context or 'default'}) ===")

        # Step 1 — Pods
        logger.info("Step 1/5: Inspecting pods")
        if investigation_id:
            await ProgressTracker.update_stage(investigation_id, "checking_pods")
        pods_result = await self._pod_inspector.inspect()

        # Step 2 — Logs (only for problematic pods)
        logger.info("Step 2/5: Collecting logs")
        if investigation_id:
            await ProgressTracker.update_stage(investigation_id, "reading_logs")
        logs_result = await self._logs_collector.collect(
            pods_result.problematic_pods
        )

        # Step 3 — Events
        logger.info("Step 3/5: Analyzing events")
        if investigation_id:
            await ProgressTracker.update_stage(investigation_id, "analyzing_events")
        events_result = await self._events_analyzer.analyze()

        # Step 4 — Deployments
        logger.info("Step 4/5: Inspecting deployments")
        if investigation_id:
            await ProgressTracker.update_stage(investigation_id, "inspecting_deployments")
        deployments_result = await self._deployment_inspector.inspect()

        # Step 5 — Networking
        logger.info("Step 5/5: Inspecting network")
        if investigation_id:
            await ProgressTracker.update_stage(investigation_id, "checking_networking")
        network_result = await self._network_inspector.inspect()

        logger.info("=== Cluster investigation complete ===")

        return InvestigationPayload(
            pods=pods_result,
            logs=logs_result,
            events=events_result,
            deployments=deployments_result,
            network=network_result,
        )
