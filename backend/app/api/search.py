"""Search API endpoints."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.search import SearchRequest, SearchResponse
from app.services import project as project_service
from app.services import search as search_service

router = APIRouter(prefix="/projects/{project_id}/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_documents(
    project_id: uuid.UUID,
    body: SearchRequest,
    db: DbSession,
    user: CurrentUser,
) -> SearchResponse:
    """Semantic search over indexed documents in a project."""
    await project_service.get_project(db, tenant_id=user["tenant_id"], project_id=project_id)

    results = await search_service.search_documents(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        query=body.query,
        filters=body.filters,
        limit=body.limit,
    )

    return SearchResponse(results=results, total=len(results))
