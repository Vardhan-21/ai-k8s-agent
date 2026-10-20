"""Kubernetes cluster discovery and context management service.

Discovers local and remote Kubernetes contexts from kubeconfig, verifies
reachability safely, and bridges host loopback networking when running inside Docker.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import re
import shlex
import socket
import threading
from urllib.parse import urlparse

from fastapi import HTTPException
from loguru import logger
import yaml

from app.core.config import settings
from app.models.schemas import ClusterContextInfo, ContextsListResponse


class LoopbackProxyManager:
    """Manages transparent TCP forwards from container 127.0.0.1 to host.docker.internal.

    This ensures that when kubeconfig points to 127.0.0.1:<port> (common in Kind, Minikube,
    and Docker Desktop on Windows/macOS), kubectl running inside the Linux container can
    reach the host-bound port while fully preserving TLS certificate verification.
    """

    _instance: LoopbackProxyManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._active_ports: set[int] = set()

    @classmethod
    def get_instance(cls) -> LoopbackProxyManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def ensure_forwarder(self, port: int, target_host: str = "host.docker.internal") -> bool:
        """Ensure a transparent TCP proxy is listening on 127.0.0.1:port."""
        with self._lock:
            if port in self._active_ports:
                return True

            # Test if something is already listening on this loopback port
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                test_sock.bind(("127.0.0.1", port))
                test_sock.close()
            except OSError:
                # Already bound by something (possibly an earlier thread)
                self._active_ports.add(port)
                return True

            # Start transparent forwarding thread
            thread = threading.Thread(
                target=self._run_forwarder,
                args=(port, target_host),
                daemon=True,
                name=f"k8s-loopback-proxy-{port}",
            )
            thread.start()
            self._active_ports.add(port)
            logger.info(f"Started loopback bridge: 127.0.0.1:{port} -> {target_host}:{port}")
            return True

    def _run_forwarder(self, port: int, target_host: str) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", port))
            server.listen(32)
        except Exception as exc:
            logger.warning(f"Could not bind loopback forwarder on port {port}: {exc}")
            return

        while True:
            try:
                client_sock, _ = server.accept()
                dest_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    dest_sock.connect((target_host, port))
                except Exception as connect_exc:
                    logger.debug(f"Loopback proxy connect failed to {target_host}:{port} - {connect_exc}")
                    client_sock.close()
                    continue

                def pipe(s_in: socket.socket, s_out: socket.socket) -> None:
                    try:
                        while True:
                            data = s_in.recv(16384)
                            if not data:
                                break
                            s_out.sendall(data)
                    except Exception:
                        pass
                    finally:
                        try:
                            s_in.close()
                        except Exception:
                            pass
                        try:
                            s_out.close()
                        except Exception:
                            pass

                threading.Thread(target=pipe, args=(client_sock, dest_sock), daemon=True).start()
                threading.Thread(target=pipe, args=(dest_sock, client_sock), daemon=True).start()
            except Exception as loop_exc:
                logger.debug(f"Loopback proxy accept loop error: {loop_exc}")
                break


class ClusterService:
    """Service to discover, list, and validate Kubernetes clusters and contexts."""

    def __init__(self) -> None:
        self._proxy_mgr = LoopbackProxyManager.get_instance()

    def get_kubeconfig_path(self) -> Path | None:
        """Resolve the active kubeconfig path, checking configured and fallback locations."""
        candidates = []
        if settings.KUBECONFIG_PATH:
            candidates.append(Path(settings.KUBECONFIG_PATH))
        # Standard container and home paths
        candidates.append(Path("/root/.kube/config"))
        candidates.append(Path.home() / ".kube" / "config")

        for p in candidates:
            try:
                if p.is_file():
                    return p
            except OSError:
                continue
        return None

    def _load_kubeconfig(self) -> dict | None:
        """Read and parse the kubeconfig YAML safely."""
        path = self.get_kubeconfig_path()
        if not path:
            logger.warning("No kubeconfig file found at configured or fallback paths.")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error(f"Failed to read kubeconfig at {path}: {exc}")
            return None

    def _ensure_network_bridges(self, clusters: list[dict]) -> None:
        """Inspect cluster endpoints and ensure loopback forwarders are up if needed."""
        for c in clusters:
            server_url = c.get("cluster", {}).get("server", "")
            if not server_url:
                continue
            try:
                parsed = urlparse(server_url)
                if parsed.hostname in ("127.0.0.1", "localhost") and parsed.port:
                    self._proxy_mgr.ensure_forwarder(parsed.port)
            except Exception as exc:
                logger.debug(f"Could not parse cluster server URL {server_url}: {exc}")

    async def check_reachability(self, context_name: str, timeout: int = 3) -> tuple[bool, str | None]:
        """Probe reachability of a context without modifying global context or state."""
        kpath = self.get_kubeconfig_path()
        cmd_parts = ["kubectl"]
        if kpath:
            cmd_parts.extend(["--kubeconfig", shlex.quote(str(kpath))])
        cmd_parts.extend([
            "--context", shlex.quote(context_name),
            "cluster-info",
            f"--request-timeout={timeout}s",
        ])
        cmd_str = " ".join(cmd_parts)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout + 2)
            if proc.returncode == 0:
                return True, None

            err_text = (stderr.decode() or stdout.decode()).strip()
            # Clean up error text to be concise and user-friendly
            clean_err = "Cluster unreachable"
            if "no such host" in err_text or "lookup" in err_text:
                clean_err = "DNS lookup failed (host not found)"
            elif "refused" in err_text.lower():
                clean_err = "Connection refused by host"
            elif "deadline exceeded" in err_text or "timed out" in err_text.lower():
                clean_err = "Connection timed out"
            elif "unauthorized" in err_text.lower():
                clean_err = "Authentication / credentials invalid"
            elif err_text:
                first_line = err_text.splitlines()[-1]
                clean_err = first_line[:120]

            return False, clean_err
        except asyncio.TimeoutError:
            return False, "Connection probe timed out"
        except Exception as exc:
            return False, f"Probe error: {str(exc)[:100]}"

    async def list_contexts(self, check_reachability: bool = True) -> ContextsListResponse:
        """List all discovered contexts with reachability and safe metadata (no secrets)."""
        data = self._load_kubeconfig()
        if not data:
            return ContextsListResponse(contexts=[], current_context=None, total=0)

        current_context = data.get("current-context")
        raw_contexts = data.get("contexts", [])
        raw_clusters = data.get("clusters", [])
        raw_users = data.get("users", [])

        # Build cluster server lookup map
        cluster_servers: dict[str, str] = {}
        for c in raw_clusters:
            c_name = c.get("name", "")
            c_server = c.get("cluster", {}).get("server", "")
            if c_name:
                cluster_servers[c_name] = c_server

        # Start bridges for local cluster endpoints
        self._ensure_network_bridges(raw_clusters)

        # Build safe context items
        contexts_to_probe: list[tuple[str, ClusterContextInfo]] = []
        for ctx_entry in raw_contexts:
            ctx_name = ctx_entry.get("name", "")
            if not ctx_name:
                continue

            ctx_body = ctx_entry.get("context", {})
            cluster_name = ctx_body.get("cluster", "")
            user_ref = ctx_body.get("user", "")
            server_endpoint = cluster_servers.get(cluster_name, "")

            # Sanitize user ref: only pass name/identifier, NEVER secrets
            safe_user = user_ref.split("/")[-1] if "/" in user_ref else user_ref

            info = ClusterContextInfo(
                name=ctx_name,
                cluster=cluster_name,
                user=safe_user,
                is_current=(ctx_name == current_context),
                server=server_endpoint,
                status="unknown",
            )
            contexts_to_probe.append((ctx_name, info))

        if check_reachability and contexts_to_probe:
            tasks = [self.check_reachability(name) for name, _ in contexts_to_probe]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (name, info), res in zip(contexts_to_probe, results):
                if isinstance(res, tuple):
                    reachable, err = res
                    info.status = "reachable" if reachable else "unreachable"
                    info.error = err
                else:
                    info.status = "unreachable"
                    info.error = str(res)

        final_contexts = [info for _, info in contexts_to_probe]
        return ContextsListResponse(
            contexts=final_contexts,
            current_context=current_context,
            total=len(final_contexts),
        )

    async def validate_context(self, context_name: str) -> ClusterContextInfo:
        """Validate that a requested context exists and is reachable.

        Raises HTTPException(400) with clear guidance if invalid or unreachable.
        """
        response = await self.list_contexts(check_reachability=True)
        matched = next((c for c in response.contexts if c.name == context_name), None)

        if not matched:
            valid_names = ", ".join(f"'{c.name}'" for c in response.contexts) or "none"
            raise HTTPException(
                status_code=400,
                detail=f"Kubernetes context '{context_name}' was not found in kubeconfig. Available contexts: {valid_names}.",
            )

        if matched.status == "unreachable":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unable to connect to Kubernetes cluster '{matched.name}'. "
                    f"Reason: {matched.error or 'Cluster is offline or unreachable'}. "
                    "Please verify cluster status, networking, and kubectl permissions."
                ),
            )

        return matched
