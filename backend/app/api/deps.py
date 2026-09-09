"""FastAPI dependencies: DB session, current user, current tenant.

The bearer scheme accepts a missing token only when ENVIRONMENT=local
(dev_mode); get_current_user then falls back to the seeded dev user.
Everywhere else, HTTPBearer itself rejects a missing token before
get_current_user runs.
"""

import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.auth import decode_token
from app.core.config import settings
from app.core.database import async_session
from app.core.exceptions import RateLimitError, UnauthorizedError

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=not settings.dev_mode)

if settings.dev_mode:
    logger.warning(
        "AUTH BYPASS ENABLED: ENVIRONMENT=local, requests without a token are served "
        "as the seeded dev user. Never run this configuration outside a local machine."
    )

_dev_user_id: uuid.UUID | None = None
_dev_tenant_id: uuid.UUID | None = None


def set_dev_ids(user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Set the dev-only user/tenant IDs used by the ENVIRONMENT=local bypass.

    Called at startup by _seed_dev_data() in main.py.
    """
    global _dev_user_id, _dev_tenant_id  # noqa: PLW0603
    _dev_user_id = user_id
    _dev_tenant_id = tenant_id


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Yield an async DB session."""
    async with async_session() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, uuid.UUID]:
    """Decode JWT, check the token is still current, and return user_id + tenant_id.

    Falls back to the seeded dev user ONLY when ENVIRONMENT=local (see config.py).

    The version check costs one SELECT per authenticated request. Without it a
    stolen access token outlives a password change by up to
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES, which is the half of the revocation that
    /auth/refresh already covers.
    """
    if credentials is None and settings.dev_mode and _dev_user_id and _dev_tenant_id:
        return {"user_id": _dev_user_id, "tenant_id": _dev_tenant_id}
    if credentials is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")

    from app.services.auth import verify_access_token_version

    user_id = uuid.UUID(payload["user_id"])
    tenant_id = uuid.UUID(payload["tenant_id"])
    await verify_access_token_version(db, user_id, tenant_id, payload.get("token_version"))
    return {"user_id": user_id, "tenant_id": tenant_id}


async def get_current_tenant(
    current_user: Annotated[dict[str, uuid.UUID], Depends(get_current_user)],
) -> uuid.UUID:
    """Extract tenant_id from the current user."""
    return current_user["tenant_id"]


async def get_admin_user(
    current_user: Annotated[dict[str, uuid.UUID], Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, uuid.UUID]:
    """Verify the current user has admin role. Returns the same user dict."""
    from app.services.auth import verify_admin_role

    await verify_admin_role(db, current_user["user_id"], current_user["tenant_id"])
    return current_user


def rate_limited(bucket: str, limit: int, window_seconds: float) -> Callable[[Request], None]:
    """Build the dependency that meters one route by client socket address.

    Args:
        bucket: Counter bucket name; each bucket is limited independently.
        limit: Maximum hits allowed within the window.
        window_seconds: Length of the rate-limit window in seconds.

    Returns:
        A FastAPI dependency that raises RateLimitError past the limit.
    """

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        verdict = ratelimit.counter_for(bucket, limit, window_seconds).hit(client)
        if not verdict.allowed:
            logger.warning("Rate limit hit on %s by %s", bucket, client)
            raise RateLimitError(verdict.retry_after_seconds)

    return dependency


def auth_rate_limit(bucket: str) -> Callable[[Request], None]:
    """Per-minute metering, for the two routes that pay a bcrypt hash."""
    return rate_limited(bucket, settings.rate_limit_auth_per_minute, 60)


def reset_rate_limit(bucket: str) -> Callable[[Request], None]:
    """Metering for the two routes that send or consume a reset link."""
    return rate_limited(
        bucket,
        settings.rate_limit_reset_per_window,
        settings.rate_limit_reset_window_seconds,
    )


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[dict[str, uuid.UUID], Depends(get_current_user)]
CurrentTenant = Annotated[uuid.UUID, Depends(get_current_tenant)]
AdminUser = Annotated[dict[str, uuid.UUID], Depends(get_admin_user)]
