"""Events Analyzer — reads Kubernetes events and surfaces warnings.

Filters for noteworthy event reasons such as FailedScheduling,
BackOff, FailedMount, FailedPull, ErrImagePull, and Unhealthy.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import ClusterEvent, EventsAnalysisResult

# Event reasons we consider warning-worthy
WARNING_REASONS: set[str] = {
    "FailedScheduling",
    "BackOff",
    "FailedMount",
    "FailedAttachVolume",
    "FailedPull",
    "ErrImagePull",
    "Unhealthy",
    "FailedCreate",
    "FailedKillPod",
    "NodeNotReady",
    "Evicted",
    "OOMKilling",
    "NetworkNotReady",
    "InsufficientMemory",
    "InsufficientCPU",
}


class EventsAnalyzer:
    """Analyze cluster events for warning signs."""

    def __init__(self, executor: KubectlExecutor | None = None) -> None:
        self._executor = executor or KubectlExecutor()

    async def analyze(self) -> EventsAnalysisResult:
        """Fetch and filter cluster events for warnings."""
        logger.info("Analyzing cluster events")

        success, data, error = await self._executor.execute_json(
            "get events -A"
        )

        if not success or data is None:
            logger.error(f"Events analysis failed: {error}")
            return EventsAnalysisResult(healthy=False, error=error)

        items: list[dict] = data.get("items", [])
        warning_events: list[ClusterEvent] = []

        for event in items:
            event_type = event.get("type", "Normal")
            reason = event.get("reason", "")

            # Keep Warning-type events and any event whose reason we track
            if event_type != "Warning" and reason not in WARNING_REASONS:
                continue

            involved = event.get("involvedObject", {})
            involved_desc = (
                f"{involved.get('kind', '')}/"
                f"{involved.get('name', '')}"
            )

            warning_events.append(
                ClusterEvent(
                    type=event_type,
                    reason=reason,
                    message=event.get("message", ""),
                    namespace=event.get("metadata", {}).get(
                        "namespace", ""
                    ),
                    involved_object=involved_desc,
                    count=event.get("count", 1),
                    last_seen=event.get("lastTimestamp", ""),
                )
            )

        healthy = len(warning_events) == 0
        logger.info(
            f"Events analysis complete — {len(items)} events, "
            f"{len(warning_events)} warnings"
        )

        return EventsAnalysisResult(
            healthy=healthy,
            warning_events=warning_events,
        )
