"""MCP transport authentication, isolation and application wiring."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.mcp import build_http_mcp, mcp_asgi_app
from app.core.auth import create_access_token
from app.core.config import settings
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.services.mcp_tools import ToolIdentity
from tests.fakes import FakePoint, FakeQdrant

HEADERS = {"Accept": "application/json, text/event-stream"}
POINT_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
async def mcp_user(db: AsyncSession, tenant_a: Tenant) -> User:
    user = User(tenant_id=tenant_a.id, email="mcp@example.test", hashed_password="unused")
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def mcp_client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    def factory() -> nullcontext[AsyncSession]:
        return nullcontext(db)

    server = build_http_mcp(factory)
    transport = mcp_asgi_app(server, factory)
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def run_manager() -> None:
        async with server.session_manager.run():
            started.set()
            await stopped.wait()

    manager = asyncio.create_task(run_manager())
    try:
        await started.wait()
        async with AsyncClient(
            transport=ASGITransport(app=transport),
            base_url="http://localhost:8000",
            headers=HEADERS,
        ) as client:
            yield client
    finally:
        stopped.set()
        await manager


def _authenticate(client: AsyncClient, user: User) -> None:
    client.headers["Authorization"] = f"Bearer {create_access_token(user.id, user.tenant_id, 0)}"


async def _rpc(
    client: AsyncClient, method: str, params: dict[str, object] | None = None, path: str = "/"
) -> Response:
    return await client.post(
        path, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    )


async def _initialize(client: AsyncClient, path: str = "/") -> None:
    response = await _rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
        path,
    )
    assert response.status_code == 200
    assert "protocolVersion" in response.json()["result"]


async def test_mcp_without_token_is_401(mcp_client: AsyncClient) -> None:
    response = await _rpc(mcp_client, "tools/list")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_mcp_with_expired_token_is_401(
    mcp_client: AsyncClient,
    mcp_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PastDatetime:
        @staticmethod
        def now(tz: object) -> datetime:
            return datetime.now(UTC) - timedelta(days=365)

    monkeypatch.setattr("app.core.auth.datetime", PastDatetime)
    _authenticate(mcp_client, mcp_user)
    assert (await _rpc(mcp_client, "tools/list")).status_code == 401


async def test_mcp_with_revoked_token_is_401(
    mcp_client: AsyncClient,
    mcp_user: User,
    db: AsyncSession,
) -> None:
    _authenticate(mcp_client, mcp_user)
    mcp_user.token_version = 1
    await db.commit()
    assert (await _rpc(mcp_client, "tools/list")).status_code == 401


async def test_mcp_in_local_environment_still_requires_a_token(
    mcp_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "environment", "local")
    assert (await _rpc(mcp_client, "tools/list")).status_code == 401


async def test_mcp_lists_two_tools_with_a_valid_token(
    mcp_client: AsyncClient, mcp_user: User
) -> None:
    _authenticate(mcp_client, mcp_user)
    await _initialize(mcp_client)
    response = await _rpc(mcp_client, "tools/list")
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"search_documents", "read_passage"}
    assert len(tools) == 2
    assert all("tenant_id" not in tool["inputSchema"]["properties"] for tool in tools)


async def _seed_passage(db: AsyncSession, tenant: Tenant) -> tuple[Project, FakeQdrant]:
    project = Project(tenant_id=tenant.id, name="Projet")
    db.add(project)
    await db.commit()
    return project, FakeQdrant(
        [
            FakePoint(
                id=POINT_ID,
                payload={
                    "tenant_id": str(tenant.id),
                    "project_id": str(project.id),
                    "document_id": "11111111-1111-4111-8111-111111111111",
                    "filename": "cctp.pdf",
                    "text": "Béton C25/30.",
                    "page": 3,
                    "position": 2,
                    "type": "cctp",
                },
            )
        ]
    )


async def test_mcp_tenant_a_reads_its_own_passage_over_http(
    mcp_client: AsyncClient,
    mcp_user: User,
    db: AsyncSession,
    tenant_a: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, store = await _seed_passage(db, tenant_a)
    monkeypatch.setattr("app.services.search.qdrant_client", store)
    _authenticate(mcp_client, mcp_user)
    await _initialize(mcp_client)
    response = await _rpc(
        mcp_client,
        "tools/call",
        {
            "name": "read_passage",
            "arguments": {"project_id": str(project.id), "point_id": POINT_ID},
        },
    )
    result = response.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["passage"]["text"] == "Béton C25/30."
    assert result["structuredContent"]["passage"]["point_id"] == POINT_ID


async def test_mcp_tenant_a_cannot_read_tenant_b(
    mcp_client: AsyncClient,
    mcp_user: User,
    db: AsyncSession,
    tenant_a: Tenant,
    tenant_b: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    foreign, store = await _seed_passage(db, tenant_b)
    own = Project(tenant_id=tenant_a.id, name="Own")
    db.add(own)
    await db.commit()
    monkeypatch.setattr("app.services.search.qdrant_client", store)
    _authenticate(mcp_client, mcp_user)
    await _initialize(mcp_client)
    response = await _rpc(
        mcp_client,
        "tools/call",
        {
            "name": "read_passage",
            "arguments": {"project_id": str(own.id), "point_id": POINT_ID},
        },
    )
    assert response.json()["result"]["structuredContent"]["passage"] is None
    for name, arguments in (
        ("read_passage", {"project_id": str(foreign.id), "point_id": POINT_ID}),
        ("search_documents", {"project_id": str(foreign.id), "query": "béton"}),
    ):
        result = (
            await _rpc(mcp_client, "tools/call", {"name": name, "arguments": arguments})
        ).json()["result"]
        assert result["isError"] is True
        assert "Project not found" in result["content"][0]["text"]
        assert "Béton C25/30" not in str(result)


async def test_mcp_rejects_an_unlisted_host(mcp_client: AsyncClient, mcp_user: User) -> None:
    _authenticate(mcp_client, mcp_user)
    mcp_client.headers["Host"] = "untrusted.example"
    assert (await _rpc(mcp_client, "tools/list")).status_code in (421, 403)


async def test_mcp_rate_limit_returns_429_past_the_limit(
    db: AsyncSession,
    mcp_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mcp_rate_limit_per_minute", 1)

    def factory() -> nullcontext[AsyncSession]:
        return nullcontext(db)

    server = build_http_mcp(factory)
    transport = mcp_asgi_app(server, factory)
    async with (
        server.session_manager.run(),
        AsyncClient(
            transport=ASGITransport(app=transport),
            base_url="http://localhost:8000",
            headers=HEADERS,
        ) as client,
    ):
        _authenticate(client, mcp_user)
        await _initialize(client)
        response = await _rpc(client, "tools/list")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


async def test_main_app_serves_mcp_without_redirect() -> None:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        response = await _rpc(client, "tools/list", path="/mcp")
    assert response.status_code == 401


async def test_main_lifespan_enters_the_session_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    engine = AsyncMock()
    monkeypatch.setattr(main, "engine", engine)
    engine.connect = lambda: nullcontext(AsyncMock())
    monkeypatch.setattr(main, "_seed_dev_data", AsyncMock())
    monkeypatch.setattr("app.core.database.async_session", lambda: nullcontext(AsyncMock()))
    monkeypatch.setattr("app.services.auth.reconcile_admin_roles", AsyncMock())
    monkeypatch.setattr(
        "app.api.mcp.resolve_bearer_identity", AsyncMock(return_value=ToolIdentity(uuid.uuid4()))
    )
    async with (
        main.lifespan(main.app),
        AsyncClient(
            transport=ASGITransport(app=main.app),
            base_url="http://localhost:8000",
            headers={**HEADERS, "Authorization": "Bearer test"},
        ) as client,
    ):
        await _initialize(client, "/mcp")
        response = await _rpc(client, "tools/list", path="/mcp")
        assert response.status_code == 200
        assert {tool["name"] for tool in response.json()["result"]["tools"]} == {
            "search_documents",
            "read_passage",
        }


def test_importing_the_app_keeps_the_app_root_log_format() -> None:
    """Building a FastMCP server must not take over the root logger before main.py configures it.

    Run in a fresh interpreter: the test process has long imported the app and pytest owns
    the root handlers, so only a clean import shows what production gets.
    """
    import subprocess
    import sys
    from pathlib import Path

    probe = (
        "import logging, app.main\n"
        "root = logging.getLogger()\n"
        "print('|'.join(type(h).__name__ for h in root.handlers))\n"
        "print('|'.join(str(getattr(h.formatter, '_fmt', None)) for h in root.handlers))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    handlers, formats = result.stdout.strip().splitlines()[-2:]
    assert handlers == "StreamHandler"
    assert formats == "%(levelname)s:%(name)s:%(message)s"
