"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return the health status of the service."""
    return {
        "status": "healthy",
        "service": "ai-kubernetes-agent",
    }
