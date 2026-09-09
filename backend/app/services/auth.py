"""Auth service — signup, login, refresh, user retrieval, password reset/change."""

import asyncio
import logging
import uuid
from typing import NamedTuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import effective_admin_emails, settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.models.tenant import Tenant
from app.models.user import ADMIN_ROLE, DEFAULT_ROLE, User
from app.services.email import send_reset_email

logger = logging.getLogger(__name__)

_DUMMY_PASSWORD_HASH = "$2b$12$aCHY1v/dVqTqq46cSprb0e7N5.GefsDAKsifTtwPu3U4sFDB/.CMm"


async def signup(db: AsyncSession, email: str, password: str, name: str) -> tuple[User, str, str]:
    """Register a new user with a new tenant. Returns (user, access_token, refresh_token)."""
    result = await db.execute(select(User).where(User.email == email))
    taken = result.scalar_one_or_none() is not None
    if taken or email in effective_admin_emails(settings):
        raise ConflictError("email already registered")

    tenant = Tenant(name=name, plan="free")
    db.add(tenant)
    await db.flush()

    hashed = await asyncio.to_thread(hash_password, password)

    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hashed,
        role=DEFAULT_ROLE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, tenant.id, user.token_version)
    refresh_token = create_refresh_token(user.id, tenant.id, user.token_version)
    return user, access_token, refresh_token


async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    """Authenticate a user by email/password. Returns (user, access_token, refresh_token)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        await asyncio.to_thread(verify_password, password, _DUMMY_PASSWORD_HASH)
        raise UnauthorizedError("invalid login credentials")

    if not await asyncio.to_thread(verify_password, password, user.hashed_password):
        raise UnauthorizedError("invalid login credentials")

    access_token = create_access_token(user.id, user.tenant_id, user.token_version)
    refresh_token = create_refresh_token(user.id, user.tenant_id, user.token_version)
    return user, access_token, refresh_token


async def refresh(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """Validate a refresh token and issue a new token pair."""
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type")

    user_id = uuid.UUID(payload["user_id"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("User no longer exists")

    if payload.get("token_version") != user.token_version:
        raise UnauthorizedError("refresh token revoked")

    new_access = create_access_token(user.id, user.tenant_id, user.token_version)
    new_refresh = create_refresh_token(user.id, user.tenant_id, user.token_version)
    return new_access, new_refresh


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Get the current user by ID, eagerly loading the tenant."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.tenant))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    return user


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, first_name: str | None, last_name: str | None
) -> User:
    """Update profile fields (first_name, last_name) for the current user."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.tenant))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name

    await db.commit()
    await db.refresh(user)
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.tenant))
    )
    return result.scalar_one()


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Generate a reset token and send email. Always succeeds (no email leak)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is not None:
        token = create_reset_token(user.id)
        reset_url = f"{settings.app_url}/reset-password?token={token}"
        await send_reset_email(email, reset_url)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """Validate a reset token and update the user's password."""
    user_id = decode_reset_token(token)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("invalid reset token")

    user.hashed_password = await asyncio.to_thread(hash_password, new_password)
    user.token_version += 1
    await db.commit()


async def change_password(
    db: AsyncSession, user_id: uuid.UUID, current_password: str, new_password: str
) -> None:
    """Change password for an authenticated user after verifying the current one."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User not found")

    if not await asyncio.to_thread(verify_password, current_password, user.hashed_password):
        raise UnauthorizedError("invalid current password")

    user.hashed_password = await asyncio.to_thread(hash_password, new_password)
    user.token_version += 1
    await db.commit()


class AdminReconciliation(NamedTuple):
    """What one reconciliation changed. Addresses as stored, except `unknown`."""

    promoted: tuple[str, ...]
    demoted: tuple[str, ...]
    unknown: tuple[str, ...]


async def verify_admin_role(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Verify that the given user has admin role. Raises ForbiddenError if not."""
    result = await db.execute(
        select(User.role).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    role = result.scalar_one_or_none()
    if role != ADMIN_ROLE:
        raise ForbiddenError("Admin access required")


async def reconcile_admin_roles(db: AsyncSession) -> AdminReconciliation:
    """Align users.role on ADMIN_EMAILS: promote the listed, demote the rest.

    Args:
        db: Active async session.

    Returns:
        AdminReconciliation: promoted, demoted and unmatched addresses.
    """
    listed = effective_admin_emails(settings)
    rows = await db.execute(
        select(User).where(or_(User.email.in_(listed), User.role == ADMIN_ROLE))
    )

    promoted: list[str] = []
    demoted: list[str] = []
    matched: set[str] = set()

    for user in rows.scalars():
        if user.email in listed:
            matched.add(user.email)
            if user.role != ADMIN_ROLE:
                user.role = ADMIN_ROLE
                promoted.append(user.email)
        elif user.role == ADMIN_ROLE:
            user.role = DEFAULT_ROLE
            demoted.append(user.email)

    await db.commit()

    unknown = tuple(sorted(listed - matched))
    if unknown:
        logger.error(
            "ADMIN_EMAILS names no account: %s. Signup refuses a listed address, "
            "so remove it, register the account, then list it again.",
            ", ".join(unknown),
        )
    logger.info(
        "Admin roles reconciled: %d promoted, %d demoted, %d unmatched",
        len(promoted),
        len(demoted),
        len(unknown),
    )
    return AdminReconciliation(tuple(promoted), tuple(demoted), unknown)


async def verify_access_token_version(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    token_version: int | None,
) -> None:
    """Refuse an access token whose version no longer matches the user's.

    A missing claim needs no branch of its own: User.token_version is a
    non-nullable int, so None never equals it and an unversioned token is
    refused by the same comparison.

    A vanished user and a token claiming the wrong tenant are deliberately
    indistinguishable here — both make the lookup return nothing, and the caller
    must learn neither.
    """
    result = await db.execute(
        select(User.token_version).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    current_version = result.scalar_one_or_none()

    if current_version is None:
        raise UnauthorizedError("Invalid token")

    if token_version != current_version:
        raise UnauthorizedError("access token revoked")
