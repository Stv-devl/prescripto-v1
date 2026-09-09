"""Pydantic schemas for project endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phase: str = Field(default="", max_length=50)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phase: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    client: str | None = Field(default=None, max_length=255)
    architect: str | None = Field(default=None, max_length=255)
    architect_address: str | None = Field(default=None, max_length=500)
    bureau_thermique: str | None = Field(default=None, max_length=255)
    bureau_thermique_address: str | None = Field(default=None, max_length=500)
    bureau_vrd: str | None = Field(default=None, max_length=255)
    bureau_vrd_address: str | None = Field(default=None, max_length=500)
    bureau_beton: str | None = Field(default=None, max_length=255)
    bureau_beton_address: str | None = Field(default=None, max_length=500)
    economiste: str | None = Field(default=None, max_length=255)
    economiste_address: str | None = Field(default=None, max_length=500)
    controleur_technique: str | None = Field(default=None, max_length=255)
    controleur_technique_address: str | None = Field(default=None, max_length=500)
    is_favorite: bool | None = Field(default=None)


class ProjectRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    phase: str
    status: str
    address: str
    client: str
    architect: str
    architect_address: str
    bureau_thermique: str
    bureau_thermique_address: str
    bureau_vrd: str
    bureau_vrd_address: str
    bureau_beton: str
    bureau_beton_address: str
    economiste: str
    economiste_address: str
    controleur_technique: str
    controleur_technique_address: str
    is_favorite: bool
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    projects: list[ProjectRead]
    total: int
