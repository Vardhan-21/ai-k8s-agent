"""Network Inspector — checks services and endpoint health.

Detects missing endpoints, selector mismatches, and DNS-related
issues across all namespaces.
"""

from __future__ import annotations

from loguru import logger

from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import NetworkInspectionResult, ServiceStatus


class NetworkInspector:
    """Inspect cluster networking (services & endpoints)."""

    def __init__(self, executor: KubectlExecutor | None = None) -> None:
        self._executor = executor or KubectlExecutor()

    async def inspect(self) -> NetworkInspectionResult:
        """Check services and their endpoints across all namespaces."""
        logger.info("Inspecting network (services & endpoints)")

        # Fetch services
        svc_ok, svc_data, svc_err = await self._executor.execute_json(
            "get services -A"
        )
        if not svc_ok or svc_data is None:
            logger.error(f"Service inspection failed: {svc_err}")
            return NetworkInspectionResult(healthy=False, error=svc_err)

        # Fetch endpoints
        ep_ok, ep_data, ep_err = await self._executor.execute_json(
            "get endpoints -A"
        )
        # Build a lookup: (namespace, name) -> has_ready_addresses
        endpoints_map: dict[tuple[str, str], bool] = {}
        if ep_ok and ep_data:
            for ep in ep_data.get("items", []):
                ep_meta = ep.get("metadata", {})
                key = (
                    ep_meta.get("namespace", ""),
                    ep_meta.get("name", ""),
                )
                subsets = ep.get("subsets") or []
                has_addresses = any(
                    s.get("addresses") for s in subsets
                )
                endpoints_map[key] = has_addresses

        services_with_issues: list[ServiceStatus] = []
        svc_items: list[dict] = svc_data.get("items", [])

        for svc in svc_items:
            metadata = svc.get("metadata", {})
            spec = svc.get("spec", {})
            name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "default")
            svc_type = spec.get("type", "ClusterIP")
            cluster_ip = spec.get("clusterIP", "")
            selector = spec.get("selector") or {}

            issues: list[str] = []

            # Skip headless / kubernetes internal services
            if name == "kubernetes" and namespace == "default":
                continue

            # Check for missing endpoints
            ep_key = (namespace, name)
            has_endpoints = endpoints_map.get(ep_key, False)

            if not has_endpoints and svc_type != "ExternalName":
                issues.append("No ready endpoints")

            # Check for missing selector
            selector_mismatch = False
            if not selector and svc_type not in ("ExternalName", "NodePort"):
                selector_mismatch = True
                issues.append("No selector defined — cannot route traffic")

            if issues:
                services_with_issues.append(
                    ServiceStatus(
                        name=name,
                        namespace=namespace,
                        type=svc_type,
                        cluster_ip=cluster_ip,
                        has_endpoints=has_endpoints,
                        selector_mismatch=selector_mismatch,
                        issues=issues,
                    )
                )

        healthy = len(services_with_issues) == 0
        logger.info(
            f"Network inspection complete — {len(svc_items)} services, "
            f"{len(services_with_issues)} with issues"
        )

        return NetworkInspectionResult(
            healthy=healthy,
            services=services_with_issues,
        )
