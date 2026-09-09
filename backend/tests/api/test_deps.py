"""Unit tests for the `get_current_user` FastAPI dependency."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user
from app.core.exceptions import RateLimitError, UnauthorizedError


def _exploding_db() -> AsyncMock:
    """A session that fails the test if anything queries it.

    Several cases below assert that a token is refused *before* the database is
    read. A plain AsyncMock cannot tell the two orders apart — both raise the
    same error — so the double has to be the thing that discriminates.
    """
    db = AsyncMock()
    refuse = AssertionError("the database must not be read on this path")
    # Every read entry point, not just the one the service happens to use today:
    # armed on `execute` alone this double would answer `scalar`/`get` cheerfully
    # and the cases below would prove nothing.
    for method in ("execute", "scalar", "scalars", "get", "stream", "stream_scalars"):
        getattr(db, method).side_effect = refuse
    return db


def _credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake.jwt.token")


class TestGetCurrentUserTokenType:
    async def test_get_current_user_rejects_non_access_token(self) -> None:
        with (
            patch(
                "app.api.deps.decode_token",
                return_value={
                    "user_id": str(uuid.uuid4()),
                    "tenant_id": str(uuid.uuid4()),
                    "type": "refresh",
                    "token_version": 0,
                },
            ),
            pytest.raises(UnauthorizedError),
        ):
            await get_current_user(_credentials(), _exploding_db())

    async def test_get_current_user_accepts_access_token(self) -> None:
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        with (
            patch(
                "app.api.deps.decode_token",
                return_value={
                    "user_id": str(user_id),
                    "tenant_id": str(tenant_id),
                    "type": "access",
                    "token_version": 0,
                },
            ),
            patch("app.services.auth.verify_access_token_version", new_callable=AsyncMock),
        ):
            result = await get_current_user(_credentials(), AsyncMock())

        assert result == {"user_id": user_id, "tenant_id": tenant_id}

    async def test_get_current_user_rejects_token_missing_type(self) -> None:
        with (
            patch(
                "app.api.deps.decode_token",
                return_value={
                    "user_id": str(uuid.uuid4()),
                    "tenant_id": str(uuid.uuid4()),
                },
            ),
            pytest.raises(UnauthorizedError),
        ):
            await get_current_user(_credentials(), _exploding_db())


class TestGetCurrentUserTokenVersion:
    """The window this dependency exists to close.

    No patch of decode_token here: a real user, a real token, a real session.
    A version check that lives in the service but is never reached from deps —
    dead branch, missing await — passes every mocked case and fails these.
    """

    async def test_token_stops_being_accepted_after_change_password(
        self, db: object, tenant_a: object
    ) -> None:
        from app.core.auth import create_access_token
        from app.models.user import User
        from app.services.auth import change_password

        user = User(
            tenant_id=tenant_a.id,
            email="eco@cabinet.fr",
            hashed_password="not-a-real-hash",
            token_version=0,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(user.id, tenant_a.id, user.token_version)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        served = await get_current_user(credentials, db)
        assert served == {"user_id": user.id, "tenant_id": tenant_a.id}

        with (
            patch("app.services.auth.verify_password", return_value=True),
            patch("app.services.auth.hash_password", return_value="new_hashed_password"),
        ):
            await change_password(db, user.id, "old_password123", "new_password456")

        with pytest.raises(UnauthorizedError, match="revoked"):
            await get_current_user(credentials, db)

    async def test_current_token_is_served(self, db: object, tenant_a: object) -> None:
        from app.core.auth import create_access_token
        from app.models.user import User

        user = User(
            tenant_id=tenant_a.id,
            email="eco@cabinet.fr",
            hashed_password="not-a-real-hash",
            token_version=4,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(user.id, tenant_a.id, 4)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        assert await get_current_user(credentials, db) == {
            "user_id": user.id,
            "tenant_id": tenant_a.id,
        }


class TestDevBypass:
    async def test_dev_bypass_serves_the_seeded_user_without_reading_the_database(self) -> None:
        dev_user_id = uuid.uuid4()
        dev_tenant_id = uuid.uuid4()

        with (
            patch("app.api.deps._dev_user_id", dev_user_id),
            patch("app.api.deps._dev_tenant_id", dev_tenant_id),
        ):
            result = await get_current_user(None, _exploding_db())

        assert result == {"user_id": dev_user_id, "tenant_id": dev_tenant_id}


async def _seated_user(db: object, tenant: object, role: str) -> object:
    """A persisted User row carrying the given role."""
    from app.models.user import User

    user = User(
        tenant_id=tenant.id,
        email=f"{role}@cabinet.fr",
        hashed_password="not-a-real-hash",
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestGetAdminUser:
    async def test_an_authenticated_owner_is_refused(
        self, db: object, tenant_a: object
    ) -> None:
        from app.api.deps import get_admin_user
        from app.core.exceptions import ForbiddenError

        user = await _seated_user(db, tenant_a, "owner")

        with pytest.raises(ForbiddenError):
            await get_admin_user({"user_id": user.id, "tenant_id": tenant_a.id}, db)

    async def test_an_admin_of_the_authenticated_tenant_is_served_unchanged(
        self, db: object, tenant_a: object
    ) -> None:
        from app.api.deps import get_admin_user

        user = await _seated_user(db, tenant_a, "admin")
        identity = {"user_id": user.id, "tenant_id": tenant_a.id}

        assert await get_admin_user(identity, db) == identity

    async def test_the_tenant_the_caller_is_authenticated_as_is_the_one_checked(
        self, db: object, tenant_a: object, tenant_b: object
    ) -> None:
        """What stops the guard being handed the right user_id and any tenant.

        The row exists and is admin, so a dependency passing only the user_id
        would let this through — the identity says tenant_b, and this admin
        belongs to tenant_a.
        """
        from app.api.deps import get_admin_user
        from app.core.exceptions import ForbiddenError

        user = await _seated_user(db, tenant_a, "admin")

        with pytest.raises(ForbiddenError):
            await get_admin_user({"user_id": user.id, "tenant_id": tenant_b.id}, db)


def _request(client_host: str, forwarded: str | None = None) -> object:
    """A bare ASGI request carrying a socket address and, optionally, a header."""
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (client_host, 0), "headers": headers})


class TestTheRateLimitKey:
    def test_the_key_is_the_socket_address(self) -> None:
        from app.api.deps import rate_limited

        meter = rate_limited("probe-socket", limit=1, window_seconds=60)

        meter(_request("10.0.0.1"))

        with pytest.raises(RateLimitError):
            meter(_request("10.0.0.1"))

    def test_another_socket_has_its_own_count(self) -> None:
        from app.api.deps import rate_limited

        meter = rate_limited("probe-other", limit=1, window_seconds=60)
        meter(_request("10.0.0.1"))

        assert meter(_request("10.0.0.2")) is None

    def test_a_forged_forwarded_header_does_not_change_the_key(self) -> None:
        """The case that stops a later "fix" from opening the hole in silence.

        Reading X-Forwarded-For here would let anyone skip the limit by sending
        a fresh value per request. Resolving the real client is uvicorn's job,
        through FORWARDED_ALLOW_IPS, and Settings refuses to start deployed
        until that is configured.
        """
        from app.api.deps import rate_limited

        meter = rate_limited("probe-forged", limit=1, window_seconds=60)
        meter(_request("10.0.0.1", forwarded="203.0.113.7"))

        with pytest.raises(RateLimitError):
            meter(_request("10.0.0.1", forwarded="203.0.113.8"))
