"""JWT token utilities and password hashing."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, token_version: int) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
        "token_version": token_version,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, tenant_id: uuid.UUID, token_version: int) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "refresh",
        "token_version": token_version,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class ResetClaims(NamedTuple):
    """What a password-reset token vouches for."""

    user_id: uuid.UUID
    token_version: int


def create_reset_token(user_id: uuid.UUID, token_version: int) -> str:
    """Create a short-lived JWT token for password reset (30 min)."""
    expire = datetime.now(UTC) + timedelta(minutes=30)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "reset",
        "token_version": token_version,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_reset_token(token: str) -> ResetClaims:
    """Decode a password-reset JWT. Raises UnauthorizedError on failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("invalid reset token") from exc

    if payload.get("type") != "reset":
        raise UnauthorizedError("invalid reset token")

    sub = payload.get("sub")
    if sub is None:
        raise UnauthorizedError("invalid reset token")

    token_version = payload.get("token_version")
    if not isinstance(token_version, int) or isinstance(token_version, bool):
        raise UnauthorizedError("invalid reset token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise UnauthorizedError("invalid reset token") from exc

    return ResetClaims(user_id, token_version)


def decode_token(token: str) -> dict[str, str | int | None]:
    """Decode and validate a JWT token. Raises UnauthorizedError on failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    sub = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if sub is None or tenant_id is None:
        raise UnauthorizedError("Invalid token payload")

    return {
        "user_id": sub,
        "tenant_id": tenant_id,
        "type": payload.get("type", ""),
        "token_version": payload.get("token_version"),
    }
