"""Pydantic schemas for semantic search endpoints."""

import uuid

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    lot: str | None = None
    phase: str | None = None
    type: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    text: str
    page: int
    position: int
    filename: str
    document_id: uuid.UUID
    project_id: uuid.UUID
    score: float
    lot: str
    phase: str
    type: str
    heading_prefix: str | None = None
    section_title: str | None = None
    parent_sections: list[str] = Field(default_factory=list)
    content_type: str | None = None
    keywords: list[str] = Field(default_factory=list)
    localisation: list[str] = Field(default_factory=list)
    char_count: int = 0


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
