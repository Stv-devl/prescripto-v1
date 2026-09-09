"""HTTP-level tests for the admin role barrier.

Sixteen routes sit behind `AdminUser`, and until this file nothing exercised
that dependency: replacing the body of `verify_admin_role` with `return None`
left the whole suite green.

`httpx.AsyncClient` over `ASGITransport` rather than `TestClient`: the latter
drives the app from another thread with its own event loop, while the `db`
fixture's SQLite connection belongs to this one. It also means the lifespan is
never run, which is what we want — it would reach for a real Postgres.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.user import User
from app.schemas.admin import ChunkStatsResponse, QualityAlerts

_STATS_ROUTE = f"/api/admin/projects/{uuid.uuid4()}/chunks/stats"


async def _seated_user(db: object, tenant: object, role: str) -> User:
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


@pytest_asyncio.fixture
async def client(db: object) -> AsyncIterator[AsyncClient]:
    """An HTTP client whose requests read the test session.

    The teardown clears every override: `app` is a module-level object, so one
    left behind would leak into every test that runs after this file.
    """
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _empty_stats() -> ChunkStatsResponse:
    """A valid, empty payload. The route's own shape, so the case fails on the
    barrier rather than on response serialisation."""
    return ChunkStatsResponse(
        total_chunks=0,
        total_documents=0,
        by_document=[],
        by_content_type={},
        by_lot={},
        by_type={},
        size_distribution={},
        quality_alerts=QualityAlerts(
            chunks_without_keywords=0,
            chunks_heading_only=0,
            chunks_very_short=0,
            chunks_oversized=0,
            documents_with_errors=0,
        ),
    )


def _authenticated_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user.id,
        "tenant_id": user.tenant_id,
    }


class TestTheAdminBarrier:
    async def test_an_authenticated_non_admin_is_refused_with_403(
        self, client: AsyncClient, db: object, tenant_a: object
    ) -> None:
        _authenticated_as(await _seated_user(db, tenant_a, "owner"))

        response = await client.get(_STATS_ROUTE)

        assert response.status_code == 403

    async def test_an_admin_passes_the_barrier(
        self, client: AsyncClient, db: object, tenant_a: object
    ) -> None:
        _authenticated_as(await _seated_user(db, tenant_a, "admin"))

        with patch(
            "app.api.admin.admin_service.get_chunk_stats",
            new_callable=AsyncMock,
            return_value=_empty_stats(),
        ):
            response = await client.get(_STATS_ROUTE)

        assert response.status_code == 200

    async def test_an_unauthenticated_call_answers_401_and_not_403(
        self, client: AsyncClient
    ) -> None:
        """A 403 here would say the route exists and the account is known.

        No override of get_current_user: the request carries no credentials, so
        the identity dependency refuses before the role is ever looked at.
        """
        response = await client.get(_STATS_ROUTE)

        assert response.status_code == 401


@pytest.fixture(autouse=True)
def _no_dev_bypass() -> Iterator[None]:
    """conftest pins ENVIRONMENT=local, which serves a seeded user with no token.

    The seeded ids are None in the suite, so the bypass already falls through to
    the 401 — this guard makes the case independent of that, instead of resting
    on a global that another file could set.
    """
    with (
        patch("app.api.deps._dev_user_id", None),
        patch("app.api.deps._dev_tenant_id", None),
    ):
        yield
