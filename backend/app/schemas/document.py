"""Pydantic schemas for document endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    folder_id: uuid.UUID | None = None
    filename: str
    type: str
    lot: str
    phase: str
    size: int
    status: str
    error_message: str | None = None
    chunk_count: int | None = None
    ingested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    documents: list[DocumentRead]
    total: int


class DocumentMove(BaseModel):
    folder_id: uuid.UUID | None = None
