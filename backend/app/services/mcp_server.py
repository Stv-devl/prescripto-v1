"""Registration of the two read tools on a FastMCP server.

Transport-agnostic on purpose: the HTTP instance mounted on /mcp (api/mcp.py) and the
shared in-process instance of the chat graph both go through `register_tools`.
Each caller passes the way tools get a DB session, so the graph reuses its request
session and the tests their SQLite one. Errors come back as MCP error results; only a
business exception's own message ever reaches the client.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.lowlevel import Server
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.schemas.search import ToolPassage
from app.services.mcp_tools import read_project_passage, search_project_passages

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

INTERNAL_ERROR = "Internal error"


def lowlevel_server(server: FastMCP) -> Server:
    """Keep the SDK's private low-level server access in one adapter."""
    return server._mcp_server


class SearchToolResult(BaseModel):
    passages: list[ToolPassage]


class ReadToolResult(BaseModel):
    passage: ToolPassage | None


def _tool_error(tool: str, exc: Exception) -> ToolError:
    if isinstance(exc, AppException):
        return ToolError(exc.message)
    logger.error("[MCP] Tool %s failed: %s", tool, type(exc).__name__)
    return ToolError(INTERNAL_ERROR)


def register_tools(server: FastMCP, session_factory: SessionFactory) -> None:
    """Register `search_documents` and `read_passage` on `server`."""

    @server.tool(
        name="search_documents",
        description=(
            "Search the CCTP passages of one project. Returns passages with their "
            "document, page and point id."
        ),
    )
    async def search_documents(
        project_id: Annotated[str, Field(description="Project UUID.")],
        query: Annotated[str, Field(description="What to look for, in French.")],
        lot: Annotated[str | None, Field(description="Optional lot filter.")] = None,
        doc_type: Annotated[str | None, Field(description="Optional document type.")] = None,
    ) -> SearchToolResult:
        try:
            async with session_factory() as db:
                passages = await search_project_passages(
                    db, project_id=project_id, query=query, lot=lot, doc_type=doc_type
                )
        except Exception as exc:
            raise _tool_error("search_documents", exc) from exc
        return SearchToolResult(passages=passages)

    @server.tool(
        name="read_passage",
        description="Read the full text of one passage of a project by its point id.",
    )
    async def read_passage(
        project_id: Annotated[str, Field(description="Project UUID.")],
        point_id: Annotated[str, Field(description="Point id returned by search_documents.")],
    ) -> ReadToolResult:
        try:
            async with session_factory() as db:
                passage = await read_project_passage(db, project_id=project_id, point_id=point_id)
        except Exception as exc:
            raise _tool_error("read_passage", exc) from exc
        return ReadToolResult(passage=passage)
