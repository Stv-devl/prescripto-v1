"""Pydantic schemas for admin chunk inspection endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdjacentChunk(BaseModel):
    id: uuid.UUID
    position: int
    page: int
    text_preview: str
    content_type: str | None = None


class ChunkListItem(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    text_preview: str
    page: int
    position: int
    char_count: int | None = None
    content_type: str | None = None
    keywords: list[str] | None = None
    section_title: str | None = None
    parent_sections: list[str] | None = None
    localisation: list[str] | None = None
    lot: str
    phase: str
    type: str
    qdrant_point_id: str
    created_at: datetime
    quality_score: float | None = None


class PaginatedChunks(BaseModel):
    items: list[ChunkListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


class ChunkDetail(ChunkListItem):
    text: str
    qdrant_payload: dict | None = None
    adjacent_chunks: list[AdjacentChunk] = []


class DocumentStats(BaseModel):
    document_id: uuid.UUID
    filename: str
    type: str
    lot: str
    chunk_count: int
    avg_char_count: float
    min_char_count: int
    max_char_count: int


class QualityAlerts(BaseModel):
    chunks_without_keywords: int
    chunks_heading_only: int
    chunks_very_short: int
    chunks_oversized: int
    documents_with_errors: int


class ChunkStatsResponse(BaseModel):
    total_chunks: int
    total_documents: int
    avg_quality_score: float = 0.0
    by_document: list[DocumentStats]
    by_content_type: dict[str, int]
    by_lot: dict[str, int]
    by_type: dict[str, int]
    size_distribution: dict[str, int]
    quality_alerts: QualityAlerts


class SyncDocumentItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    sql_count: int
    qdrant_count: int
    status: str
    missing_in_qdrant: list[str]


class PaginatedSyncDocuments(BaseModel):
    items: list[SyncDocumentItem]
    total: int
    page: int
    per_page: int


class SyncCheckResponse(BaseModel):
    total_sql: int
    total_qdrant: int
    synced: bool
    documents: PaginatedSyncDocuments


# ── Playground schemas ──


# ── Duplicate detection schemas ──


class DuplicatePair(BaseModel):
    chunk_a_id: uuid.UUID
    chunk_b_id: uuid.UUID
    chunk_a_preview: str
    chunk_b_preview: str
    chunk_a_position: int
    chunk_b_position: int
    chunk_a_page: int
    chunk_b_page: int
    similarity: float


class DuplicateResponse(BaseModel):
    pairs: list[DuplicatePair]
    total_chunks_analyzed: int


# ── Playground schemas ──


class PlaygroundSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    lot: str | None = None
    content_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class PlaygroundSearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    text_preview: str
    text: str
    score: float
    page: int
    position: int
    lot: str
    type: str
    content_type: str | None = None
    keywords: list[str]
    section_title: str | None = None
    parent_sections: list[str]
    localisation: list[str] = []
    char_count: int
    quality_score: float


class PlaygroundSearchResponse(BaseModel):
    results: list[PlaygroundSearchResult]
    query_time_ms: float
    total_results: int


# ── Mutation schemas ──


class ChunkUpdateRequest(BaseModel):
    text: str = Field(min_length=1)


class ChunkSplitRequest(BaseModel):
    split_position: int = Field(ge=1, description="Character index to split at")


class ChunkMergeRequest(BaseModel):
    adjacent_chunk_id: uuid.UUID


class ChunkMutationResponse(BaseModel):
    message: str
    chunk_ids: list[uuid.UUID]


class RechunkResponse(BaseModel):
    old_count: int
    new_count: int
    old_avg_chars: float
    new_avg_chars: float
    message: str


# ── Advanced filter schemas ──


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    lot: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


class SectionNode(BaseModel):
    title: str
    children: list["SectionNode"] = []
    chunk_count: int


class SimilarChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    text_preview: str
    similarity: float
    content_type: str | None = None
    section_title: str | None = None


class BatchEnrichResponse(BaseModel):
    updated_count: int
    message: str


class RepairPayloadsResponse(BaseModel):
    repaired_count: int
    orphan_count: int
    message: str
