"""Business logic of the two read tools exposed over MCP: search and read a passage.

The caller is a model, so nothing it sends is trusted for isolation: the tenant comes
from the identity set by whoever opened the MCP session (the /mcp auth middleware, or
the chat graph around its in-process session), never from a tool argument. Every
ownership refusal looks the same from outside — unknown, foreign and out-of-scope
projects all raise one message — so a probe learns nothing about what exists.
"""

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.schemas.search import SearchFilters, ToolPassage
from app.services import project as project_service
from app.services import search as search_service
from app.services.injection_guard import INJECTION_FLAG, looks_like_injection

logger = logging.getLogger(__name__)

QUERY_MAX_CHARS = 500
FILTER_MAX_CHARS = 100
SEARCH_TOOL_LIMIT = 8
READ_PASSAGE_SCORE = 0.5
PROJECT_NOT_FOUND = "Project not found"


@dataclass(frozen=True)
class ToolIdentity:
    """Who the tools act for. `allowed_project_id` narrows them to one project."""

    tenant_id: uuid.UUID
    allowed_project_id: uuid.UUID | None = None


_identity: ContextVar[ToolIdentity | None] = ContextVar("mcp_tool_identity", default=None)


@contextmanager
def identity_scope(identity: ToolIdentity) -> Iterator[None]:
    """Make `identity` the caller of every tool run inside the block (and tasks it spawns)."""
    token = _identity.set(identity)
    try:
        yield
    finally:
        _identity.reset(token)


def current_identity() -> ToolIdentity:
    """The identity set by the session opener; refuses when there is none."""
    identity = _identity.get()
    if identity is None:
        raise UnauthorizedError("Not authenticated")
    return identity


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(f"Invalid {field}") from exc


def _check_filter(value: str | None, field: str) -> None:
    if value is not None and len(value) > FILTER_MAX_CHARS:
        raise ValidationError(f"{field} longer than {FILTER_MAX_CHARS} characters")


async def _owned_project(
    db: AsyncSession, identity: ToolIdentity, raw_project_id: str
) -> uuid.UUID:
    project_id = _parse_uuid(raw_project_id, "project_id")
    if identity.allowed_project_id is not None and project_id != identity.allowed_project_id:
        logger.warning(
            "[MCP] Project %s refused for tenant %s: outside the session's project",
            project_id,
            identity.tenant_id,
        )
        raise NotFoundError(PROJECT_NOT_FOUND)
    try:
        await project_service.get_project(db, identity.tenant_id, project_id)
    except (NotFoundError, ForbiddenError) as exc:
        logger.warning(
            "[MCP] Project %s refused for tenant %s: unknown or foreign",
            project_id,
            identity.tenant_id,
        )
        raise NotFoundError(PROJECT_NOT_FOUND) from exc
    return project_id


async def search_project_passages(
    db: AsyncSession,
    *,
    project_id: str,
    query: str,
    lot: str | None = None,
    doc_type: str | None = None,
) -> list[ToolPassage]:
    """Search the passages of one project of the caller's tenant."""
    identity = current_identity()
    stripped = query.strip()
    if not stripped:
        raise ValidationError("Empty query")
    if len(query) > QUERY_MAX_CHARS:
        raise ValidationError(f"Query longer than {QUERY_MAX_CHARS} characters")
    _check_filter(lot, "lot")
    _check_filter(doc_type, "doc_type")
    owned = await _owned_project(db, identity, project_id)

    results = await search_service.search_merged(
        tenant_id=identity.tenant_id,
        project_id=owned,
        queries=[stripped],
        filters=SearchFilters(lot=lot, type=doc_type),
        limit=SEARCH_TOOL_LIMIT,
    )
    return [
        ToolPassage(
            **result.model_dump(exclude={"point_id"}),
            point_id=result.point_id,
            suspect=looks_like_injection(result.text),
        )
        for result in results[:SEARCH_TOOL_LIMIT]
        if result.point_id is not None
    ]


def _passage_from_payload(point_id: str, payload: dict[str, object]) -> ToolPassage:
    text = str(payload.get("text", ""))
    return ToolPassage(
        point_id=point_id,
        text=text,
        page=payload.get("page", 0),
        position=payload.get("position", 0),
        filename=payload.get("filename", ""),
        document_id=payload["document_id"],
        project_id=payload["project_id"],
        score=READ_PASSAGE_SCORE,
        lot=payload.get("lot", ""),
        phase=payload.get("phase", ""),
        type=payload.get("type", ""),
        heading_prefix=payload.get("heading_prefix"),
        section_title=payload.get("section_title"),
        parent_sections=payload.get("parent_sections", []),
        content_type=payload.get("content_type"),
        keywords=payload.get("keywords", []),
        localisation=payload.get("localisation", []),
        char_count=payload.get("char_count", len(text)),
        suspect=payload.get(INJECTION_FLAG) is True or looks_like_injection(text),
    )


async def read_project_passage(
    db: AsyncSession, *, project_id: str, point_id: str
) -> ToolPassage | None:
    """Read one passage by its point id; None unless it belongs to that project of the tenant."""
    identity = current_identity()
    point_uuid = _parse_uuid(point_id, "point_id")
    owned = await _owned_project(db, identity, project_id)

    payload = await search_service.retrieve_point_payload(str(point_uuid), identity.tenant_id)
    if payload is None:
        return None
    if payload.get("project_id") != str(owned):
        logger.warning(
            "[MCP] Point %s refused for tenant %s: not in project %s",
            point_uuid,
            identity.tenant_id,
            owned,
        )
        return None
    return _passage_from_payload(str(point_uuid), payload)
