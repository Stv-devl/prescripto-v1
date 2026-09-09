"""Pydantic schemas for folder endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lot: str = Field(default="", max_length=100)
    phase: str = Field(default="", max_length=50)


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    lot: str | None = Field(default=None, max_length=100)
    phase: str | None = Field(default=None, max_length=50)


class FolderRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    lot: str
    phase: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderList(BaseModel):
    folders: list[FolderRead]
    total: int
