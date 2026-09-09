"""Pydantic schemas for chat and conversation endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Source(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int
    lot: str
    phase: str
    text: str = ""
    section_title: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: uuid.UUID | None = None


class StructuredTable(BaseModel):
    title: str
    columns: list[str]
    rows: list[dict[str, str]]


class StructuredSchema(BaseModel):
    schema_type: str
    title: str
    params: dict[str, str]


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: list[Source]
    structured: StructuredTable | None = None
    schema_: StructuredSchema | None = Field(None, alias="schema", serialization_alias="schema")
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "serialize_by_alias": True,
    }


class ConversationRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationList(BaseModel):
    conversations: list[ConversationRead]
    total: int
