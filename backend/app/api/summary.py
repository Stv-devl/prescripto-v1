"""Summary API endpoints — project summary generation and retrieval."""

import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.schemas.summary import SummaryRead, SummaryStatusRead
from app.services import summary as summary_service

router = APIRouter(tags=["summary"])


@router.get(
    "/projects/{project_id}/summary/status",
    response_model=SummaryStatusRead,
)
async def get_summary_status(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SummaryStatusRead:
    """Check whether the project has documents and/or a cached summary."""
    return await summary_service.get_summary_status(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )


@router.get(
    "/projects/{project_id}/summary",
    response_model=SummaryRead,
)
async def get_summary(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SummaryRead:
    """Retrieve the cached project summary."""
    summary = await summary_service.get_summary(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary found for this project")

    data = None
    if summary.data_json:
        data = json.loads(summary.data_json)

    return SummaryRead(
        id=summary.id,
        project_id=summary.project_id,
        status=summary.status,
        data=data,
        error_message=summary.error_message,
        generated_at=summary.generated_at,
    )


@router.post("/projects/{project_id}/summary/generate")
async def generate_summary(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> StreamingResponse:
    """Generate a project summary via multi-pass RAG (SSE stream)."""
    stream = summary_service.generate_summary_stream(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
