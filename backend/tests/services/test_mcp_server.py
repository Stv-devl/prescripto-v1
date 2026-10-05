"""The MCP server surface: two read tools, identity from context, errors as results.

The server is a real FastMCP instance reached through an in-memory client session,
so the cases assert what a model would actually receive: the tool list, the
structured result, and the error text (which must never leak internals).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from unittest.mock import AsyncMock, patch

from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.tenant import Tenant
from app.services.mcp_server import register_tools
from app.services.mcp_tools import ToolIdentity, identity_scope
from tests.fakes import FakePoint, FakeQdrant

HEALTHY_TEXT = "Le béton des fondations est de classe C25/30."
FOREIGN_TEXT = "Secret du voisin : dalle en béton précontraint."


def _point_id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


async def _project(db: AsyncSession, tenant: Tenant, name: str = "Projet") -> Project:
    project = Project(tenant_id=tenant.id, name=name)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


def _chunk(n: int, *, tenant: Tenant, project: Project, text: str = HEALTHY_TEXT) -> FakePoint:
    return FakePoint(
        id=_point_id(n),
        payload={
            "tenant_id": str(tenant.id),
            "project_id": str(project.id),
            "document_id": "11111111-1111-4111-8111-111111111111",
            "filename": "cctp.pdf",
            "text": text,
            "page": 3,
            "position": 2,
            "lot": "03 - Maçonnerie",
            "phase": "PRO",
            "type": "cctp",
        },
    )


@asynccontextmanager
async def _client(db: AsyncSession, identity: ToolIdentity | None) -> AsyncIterator[ClientSession]:
    server = FastMCP("test")
    register_tools(server, lambda: nullcontext(db))
    if identity is None:
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            yield session
        return
    with identity_scope(identity):
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            yield session


class TestServerCoreBehaviour:
    async def test_lists_exactly_the_two_read_tools(self, db: AsyncSession) -> None:
        async with _client(db, None) as session:
            listed = await session.list_tools()

        assert {tool.name for tool in listed.tools} == {"search_documents", "read_passage"}

    async def test_no_tool_schema_exposes_tenant_id(self, db: AsyncSession) -> None:
        async with _client(db, None) as session:
            listed = await session.list_tools()

        assert len(listed.tools) == 2
        for tool in listed.tools:
            assert "tenant_id" not in tool.inputSchema.get("properties", {})

    async def test_search_tool_returns_structured_passages_for_the_identity(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project_a = await _project(db, tenant_a)
        project_b = await _project(db, tenant_b)
        store = FakeQdrant(
            [
                _chunk(1, tenant=tenant_a, project=project_a),
                _chunk(2, tenant=tenant_b, project=project_b, text=FOREIGN_TEXT),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            async with _client(db, ToolIdentity(tenant_id=tenant_a.id)) as session:
                result = await session.call_tool(
                    "search_documents", {"project_id": str(project_a.id), "query": "béton"}
                )

        assert result.isError is False
        passages = result.structuredContent["passages"]
        assert len(passages) == 1
        assert passages[0]["point_id"] == _point_id(1)
        assert passages[0]["text"] == HEALTHY_TEXT
        assert passages[0]["page"] == 3
        assert passages[0]["lot"] == "03 - Maçonnerie"


class TestServerBusinessRules:
    async def test_call_without_identity_returns_an_error_result(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project_a = await _project(db, tenant_a)
        store = FakeQdrant([_chunk(1, tenant=tenant_a, project=project_a)])
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            async with _client(db, None) as session:
                result = await session.call_tool(
                    "search_documents", {"project_id": str(project_a.id), "query": "béton"}
                )

        assert result.isError is True
        assert "Not authenticated" in result.content[0].text
        assert HEALTHY_TEXT not in result.content[0].text

    async def test_cross_tenant_search_returns_an_error_result_without_passages(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project_b = await _project(db, tenant_b)
        store = FakeQdrant([_chunk(1, tenant=tenant_b, project=project_b, text=FOREIGN_TEXT)])
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            async with _client(db, ToolIdentity(tenant_id=tenant_a.id)) as session:
                result = await session.call_tool(
                    "search_documents", {"project_id": str(project_b.id), "query": "béton"}
                )

        assert result.isError is True
        assert "Project not found" in result.content[0].text
        assert FOREIGN_TEXT not in result.content[0].text

    async def test_cross_tenant_read_passage_returns_no_passage(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project_a = await _project(db, tenant_a)
        project_b = await _project(db, tenant_b)
        store = FakeQdrant([_chunk(2, tenant=tenant_b, project=project_b, text=FOREIGN_TEXT)])

        with patch("app.services.search.qdrant_client", store):
            async with _client(db, ToolIdentity(tenant_id=tenant_a.id)) as session:
                result = await session.call_tool(
                    "read_passage", {"project_id": str(project_a.id), "point_id": _point_id(2)}
                )

        assert result.isError is False
        assert result.structuredContent == {"passage": None}

    async def test_unexpected_failure_returns_a_generic_error(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project_a = await _project(db, tenant_a)
        store = FakeQdrant([_chunk(1, tenant=tenant_a, project=project_a)])
        embed = AsyncMock(side_effect=RuntimeError("qdrant host x"))

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            async with _client(db, ToolIdentity(tenant_id=tenant_a.id)) as session:
                result = await session.call_tool(
                    "search_documents", {"project_id": str(project_a.id), "query": "béton"}
                )

        assert result.isError is True
        assert "Internal error" in result.content[0].text
        assert "qdrant host x" not in result.content[0].text
        assert "Traceback" not in result.content[0].text


class TestServerEdgeCases:
    async def test_extra_tenant_id_argument_never_reaches_another_tenant(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project_a = await _project(db, tenant_a)
        project_b = await _project(db, tenant_b)
        store = FakeQdrant(
            [
                _chunk(1, tenant=tenant_a, project=project_a),
                _chunk(2, tenant=tenant_b, project=project_b, text=FOREIGN_TEXT),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            async with _client(db, ToolIdentity(tenant_id=tenant_a.id)) as session:
                result = await session.call_tool(
                    "search_documents",
                    {
                        "project_id": str(project_a.id),
                        "query": "béton",
                        "tenant_id": str(tenant_b.id),
                    },
                )

        rendered = repr(result.structuredContent) + "".join(
            getattr(block, "text", "") for block in result.content
        )
        assert FOREIGN_TEXT not in rendered
        assert _point_id(2) not in rendered
