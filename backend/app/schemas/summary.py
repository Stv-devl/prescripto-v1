"""Pydantic schemas for project summary generation and retrieval."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class SummarySchemaData(BaseModel):
    schema_type: str
    params: dict[str, str]


class SystemeConstructifItem(BaseModel):
    label: str
    description: str
    kpis: list[str]
    details: list[str]
    schema_: SummarySchemaData | None = None

    model_config = {"populate_by_name": True}


class ContrainteItem(BaseModel):
    label: str
    kpis: list[str]
    details: list[str]


class ProjectSummaryData(BaseModel):
    description: str
    systeme_constructif: list[SystemeConstructifItem]
    contraintes: list[ContrainteItem]


class SummaryRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    data: ProjectSummaryData | None = None
    error_message: str | None = None
    generated_at: datetime | None = None


class SummaryStatusRead(BaseModel):
    has_documents: bool
    has_summary: bool
    status: str | None = None
