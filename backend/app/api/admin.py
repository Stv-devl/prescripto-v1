"""Admin endpoints — chunk inspection, statistics, and sync checking."""

import uuid

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DbSession
from app.schemas.admin import (
    BatchEnrichResponse,
    ChunkDetail,
    ChunkListItem,
    ChunkMergeRequest,
    ChunkMutationResponse,
    ChunkSplitRequest,
    ChunkStatsResponse,
    ChunkUpdateRequest,
    DuplicateResponse,
    PaginatedChunks,
    PlaygroundSearchRequest,
    PlaygroundSearchResponse,
    RechunkResponse,
    RepairPayloadsResponse,
    SectionNode,
    SemanticSearchRequest,
    SimilarChunkResult,
    SyncCheckResponse,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/projects/{project_id}/chunks", response_model=PaginatedChunks)
async def list_chunks(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    document_id: uuid.UUID | None = None,
    lot: str | None = None,
    type: str | None = None,
    content_type: str | None = None,
    min_chars: int | None = Query(default=None, ge=0),
    max_chars: int | None = Query(default=None, ge=0),
    has_keywords: bool | None = None,
    search: str | None = None,
    orphan: bool | None = None,
    parent_section: str | None = None,
    sort_by: str = Query(default="position", pattern="^(position|page|char_count|created_at)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> PaginatedChunks:
    return await admin_service.list_chunks(
        db,
        user["tenant_id"],
        project_id,
        page=page,
        per_page=per_page,
        document_id=document_id,
        lot=lot,
        doc_type=type,
        content_type=content_type,
        min_chars=min_chars,
        max_chars=max_chars,
        has_keywords=has_keywords,
        search=search,
        orphan=orphan,
        parent_section=parent_section,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/projects/{project_id}/chunks/stats", response_model=ChunkStatsResponse)
async def get_chunk_stats(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> ChunkStatsResponse:
    return await admin_service.get_chunk_stats(db, user["tenant_id"], project_id)


@router.post(
    "/projects/{project_id}/chunks/semantic-search",
    response_model=PaginatedChunks,
)
async def semantic_search_chunks(
    project_id: uuid.UUID,
    body: SemanticSearchRequest,
    db: DbSession,
    user: AdminUser,
) -> PaginatedChunks:
    return await admin_service.semantic_search_chunks(
        db,
        user["tenant_id"],
        project_id,
        query=body.query,
        lot=body.lot,
        limit=body.limit,
    )


@router.get(
    "/projects/{project_id}/chunks/section-tree",
    response_model=list[SectionNode],
)
async def get_section_tree(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> list[SectionNode]:
    return await admin_service.get_section_tree(db, user["tenant_id"], project_id)


@router.post(
    "/projects/{project_id}/chunks/batch-enrich-keywords",
    response_model=BatchEnrichResponse,
)
async def batch_enrich_keywords(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> BatchEnrichResponse:
    return await admin_service.batch_enrich_keywords(db, user["tenant_id"], project_id)


@router.post(
    "/projects/{project_id}/chunks/repair-legacy-payloads",
    response_model=RepairPayloadsResponse,
)
async def repair_legacy_payloads(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> RepairPayloadsResponse:
    return await admin_service.repair_legacy_payloads(db, user["tenant_id"], project_id)


@router.get(
    "/projects/{project_id}/chunks/{chunk_id}/similar",
    response_model=list[SimilarChunkResult],
)
async def find_similar_chunks(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(10, ge=1, le=50),
) -> list[SimilarChunkResult]:
    return await admin_service.find_similar_chunks(
        db, user["tenant_id"], project_id, chunk_id, limit=limit
    )


@router.get("/projects/{project_id}/chunks/{chunk_id}", response_model=ChunkDetail)
async def get_chunk_detail(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> ChunkDetail:
    return await admin_service.get_chunk_detail(db, user["tenant_id"], project_id, chunk_id)


@router.get(
    "/projects/{project_id}/documents/{document_id}/chunks",
    response_model=list[ChunkListItem],
)
async def list_document_chunks(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> list[ChunkListItem]:
    return await admin_service.list_document_chunks(db, user["tenant_id"], project_id, document_id)


@router.get(
    "/projects/{project_id}/documents/{document_id}/duplicates",
    response_model=DuplicateResponse,
)
async def detect_duplicates(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
    threshold: float = Query(default=0.92, ge=0.5, le=1.0),
) -> DuplicateResponse:
    return await admin_service.detect_duplicates(
        db,
        user["tenant_id"],
        project_id,
        document_id,
        threshold=threshold,
    )


@router.post(
    "/projects/{project_id}/playground/search",
    response_model=PlaygroundSearchResponse,
)
async def playground_search(
    project_id: uuid.UUID,
    body: PlaygroundSearchRequest,
    db: DbSession,
    user: AdminUser,
) -> PlaygroundSearchResponse:
    return await admin_service.playground_search(
        db,
        user["tenant_id"],
        project_id,
        query=body.query,
        lot=body.lot,
        content_type=body.content_type,
        limit=body.limit,
    )


@router.put(
    "/projects/{project_id}/chunks/{chunk_id}",
    response_model=ChunkMutationResponse,
)
async def update_chunk(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    body: ChunkUpdateRequest,
    db: DbSession,
    user: AdminUser,
) -> ChunkMutationResponse:
    return await admin_service.update_chunk(db, user["tenant_id"], project_id, chunk_id, body.text)


@router.post(
    "/projects/{project_id}/chunks/{chunk_id}/split",
    response_model=ChunkMutationResponse,
)
async def split_chunk(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    body: ChunkSplitRequest,
    db: DbSession,
    user: AdminUser,
) -> ChunkMutationResponse:
    return await admin_service.split_chunk(
        db, user["tenant_id"], project_id, chunk_id, body.split_position
    )


@router.post(
    "/projects/{project_id}/chunks/{chunk_id}/merge",
    response_model=ChunkMutationResponse,
)
async def merge_chunks(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    body: ChunkMergeRequest,
    db: DbSession,
    user: AdminUser,
) -> ChunkMutationResponse:
    return await admin_service.merge_chunks(
        db, user["tenant_id"], project_id, chunk_id, body.adjacent_chunk_id
    )


@router.delete(
    "/projects/{project_id}/chunks/{chunk_id}",
    status_code=204,
)
async def delete_chunk(
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> None:
    await admin_service.delete_chunk(db, user["tenant_id"], project_id, chunk_id)


@router.post(
    "/projects/{project_id}/documents/{document_id}/rechunk",
    response_model=RechunkResponse,
)
async def rechunk_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
) -> RechunkResponse:
    return await admin_service.rechunk_document(db, user["tenant_id"], project_id, document_id)


@router.get("/projects/{project_id}/sync-check", response_model=SyncCheckResponse)
async def sync_check(
    project_id: uuid.UUID,
    db: DbSession,
    user: AdminUser,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    only_mismatches: bool = False,
) -> SyncCheckResponse:
    return await admin_service.sync_check(
        db,
        user["tenant_id"],
        project_id,
        page=page,
        per_page=per_page,
        only_mismatches=only_mismatches,
    )
