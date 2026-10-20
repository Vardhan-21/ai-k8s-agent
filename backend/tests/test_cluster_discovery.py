"""Unit tests for Kubernetes Cluster Discovery, Context Management, and Isolation."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.kubernetes.cluster_service import ClusterService, LoopbackProxyManager
from app.kubernetes.kubectl import KubectlExecutor
from app.models.schemas import ClusterContextInfo


@pytest.fixture
def sample_kubeconfig():
    return {
        "apiVersion": "v1",
        "current-context": "kind-kubernetes-troubleshooting",
        "contexts": [
            {
                "name": "kind-kubernetes-troubleshooting",
                "context": {
                    "cluster": "kind-cluster",
                    "user": "kind-user",
                },
            },
            {
                "name": "remote-prod-cluster",
                "context": {
                    "cluster": "prod-cluster",
                    "user": "arn:aws:iam::123456:role/Admin",
                },
            },
        ],
        "clusters": [
            {
                "name": "kind-cluster",
                "cluster": {
                    "server": "https://127.0.0.1:2886",
                    "certificate-authority-data": "SECRET_CA_DATA",
                },
            },
            {
                "name": "prod-cluster",
                "cluster": {
                    "server": "https://prod.k8s.example.com",
                    "certificate-authority-data": "SECRET_PROD_CA",
                },
            },
        ],
        "users": [
            {
                "name": "kind-user",
                "user": {
                    "client-certificate-data": "SECRET_CERT",
                    "client-key-data": "SECRET_KEY",
                },
            },
            {
                "name": "arn:aws:iam::123456:role/Admin",
                "user": {
                    "token": "SECRET_TOKEN_DO_NOT_EXPOSE",
                },
            },
        ],
    }


def test_kubectl_executor_context_building():
    """Verify KubectlExecutor properly quotes and sets context isolation flag."""
    executor = KubectlExecutor(context="kind-kubernetes-troubleshooting")
    cmd = executor._build_command("get pods -A")
    assert "--context kind-kubernetes-troubleshooting" in cmd
    assert "get pods -A" in cmd


def test_kubectl_executor_default_context():
    """Verify KubectlExecutor without context does not append --context."""
    executor = KubectlExecutor(context=None)
    cmd = executor._build_command("get pods -A")
    assert "--context" not in cmd
    assert "get pods -A" in cmd


@pytest.mark.asyncio
async def test_cluster_discovery_sanitization(sample_kubeconfig):
    """Verify cluster context discovery strips all secret credentials."""
    service = ClusterService()

    with patch.object(service, "_load_kubeconfig", return_value=sample_kubeconfig), \
         patch.object(service, "check_reachability", new_callable=AsyncMock) as mock_reach:
        mock_reach.return_value = (True, None)

        response = await service.list_contexts(check_reachability=True)

        assert response.total == 2
        assert response.current_context == "kind-kubernetes-troubleshooting"

        # Check that no secrets are returned
        dumped = response.model_dump_json()
        assert "SECRET_CERT" not in dumped
        assert "SECRET_KEY" not in dumped
        assert "SECRET_TOKEN_DO_NOT_EXPOSE" not in dumped
        assert "SECRET_CA_DATA" not in dumped
        assert "SECRET_PROD_CA" not in dumped

        # Verify safe metadata
        ctx1 = next(c for c in response.contexts if c.name == "kind-kubernetes-troubleshooting")
        assert ctx1.is_current is True
        assert ctx1.status == "reachable"
        assert ctx1.server == "https://127.0.0.1:2886"

        ctx2 = next(c for c in response.contexts if c.name == "remote-prod-cluster")
        assert ctx2.is_current is False
        assert ctx2.user == "Admin"  # Sanitized from ARN


@pytest.mark.asyncio
async def test_validate_context_success(sample_kubeconfig):
    """Validation succeeds when context is present and reachable."""
    service = ClusterService()
    with patch.object(service, "_load_kubeconfig", return_value=sample_kubeconfig), \
         patch.object(service, "check_reachability", new_callable=AsyncMock) as mock_reach:
        mock_reach.return_value = (True, None)

        info = await service.validate_context("kind-kubernetes-troubleshooting")
        assert info.name == "kind-kubernetes-troubleshooting"
        assert info.status == "reachable"


@pytest.mark.asyncio
async def test_validate_context_not_found(sample_kubeconfig):
    """Validation raises HTTP 400 when context is missing."""
    service = ClusterService()
    with patch.object(service, "_load_kubeconfig", return_value=sample_kubeconfig), \
         patch.object(service, "check_reachability", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await service.validate_context("non-existent-cluster")
        assert exc_info.value.status_code == 400
        assert "was not found in kubeconfig" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_context_unreachable(sample_kubeconfig):
    """Validation raises HTTP 400 when cluster is offline or unreachable."""
    service = ClusterService()
    with patch.object(service, "_load_kubeconfig", return_value=sample_kubeconfig), \
         patch.object(service, "check_reachability", new_callable=AsyncMock) as mock_reach:
        mock_reach.return_value = (False, "Connection timed out")

        with pytest.raises(HTTPException) as exc_info:
            await service.validate_context("remote-prod-cluster")
        assert exc_info.value.status_code == 400
        assert "Unable to connect to Kubernetes cluster 'remote-prod-cluster'" in exc_info.value.detail
