"""Authentication dependency for FastAPI endpoints.

Validates bearer tokens against InsForge's session verification endpoint.
Ensures that all incoming requests are authentic and identifies the caller.
"""

from __future__ import annotations

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings

security = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """User profile verified from InsForge session."""

    id: str
    email: str
    role: str = "authenticated"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> AuthenticatedUser:
    """Validate InsForge Bearer token and extract user identity.

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Validate against InsForge sessions/current endpoint
    url = f"{settings.INSFORGE_BASE_URL.rstrip('/')}/api/auth/sessions/current"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            user_data = data.get("user")
            if user_data and "id" in user_data:
                return AuthenticatedUser(
                    id=str(user_data["id"]),
                    email=str(user_data.get("email", "")),
                    role=str(user_data.get("role", "authenticated")),
                )

        logger.warning(
            f"Token validation failed with status {response.status_code}: {response.text[:100]}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except httpx.RequestError as exc:
        logger.error(f"Error contacting InsForge auth service: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> AuthenticatedUser | None:
    """Extract user identity if token is present, else None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
