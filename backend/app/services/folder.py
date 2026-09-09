"""Folder service — CRUD operations for document folders within projects."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.document import Document
from app.models.folder import Folder
from app.models.project import Project
from app.services import document as document_service
from app.services import project as project_service


async def create_folder(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    name: str,
    lot: str = "",
    phase: str = "",
) -> Folder:
    """Create a new folder in a project."""
    await project_service.get_project(db, tenant_id, project_id)

    folder = Folder(project_id=project_id, name=name, lot=lot, phase=phase)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def list_folders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[dict[str, object]]:
    """List all folders for a project with document counts."""
    await project_service.get_project(db, tenant_id, project_id)

    count_subq = (
        select(func.count())
        .where(Document.folder_id == Folder.id)
        .correlate(Folder)
        .scalar_subquery()
    )

    query = (
        select(Folder, count_subq.label("document_count"))
        .where(Folder.project_id == project_id)
        .order_by(Folder.name)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": folder.id,
            "project_id": folder.project_id,
            "name": folder.name,
            "lot": folder.lot,
            "phase": folder.phase,
            "document_count": doc_count,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
        }
        for folder, doc_count in rows
    ]


async def get_folder(db: AsyncSession, tenant_id: uuid.UUID, folder_id: uuid.UUID) -> Folder:
    """Get a single folder by ID, scoped to the tenant.

    Raises NotFoundError when no such row exists, ForbiddenError when it
    belongs to another tenant. Folder carries no tenant_id of its own, so the
    scope travels through the parent project — same split as get_project.
    """
    scoped = (
        select(Folder)
        .join(Project, Folder.project_id == Project.id)
        .where(Folder.id == folder_id, Project.tenant_id == tenant_id)
    )
    folder = (await db.execute(scoped)).scalar_one_or_none()
    if folder is not None:
        return folder

    exists = await db.execute(select(Folder.id).where(Folder.id == folder_id))
    if exists.scalar_one_or_none() is None:
        raise NotFoundError(f"Folder {folder_id} not found")
    raise ForbiddenError("Access denied to this folder")


async def update_folder(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    folder_id: uuid.UUID,
    name: str | None = None,
    lot: str | None = None,
    phase: str | None = None,
) -> Folder:
    """Update a folder (name, lot, phase)."""
    folder = await get_folder(db, tenant_id, folder_id)

    if name is not None:
        folder.name = name
    if lot is not None:
        folder.lot = lot
    if phase is not None:
        folder.phase = phase

    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    folder_id: uuid.UUID,
) -> None:
    """Delete a folder and all documents inside it."""
    folder = await get_folder(db, tenant_id, folder_id)

    docs_query = select(Document).where(Document.folder_id == folder_id)
    result = await db.execute(docs_query)
    documents = result.scalars().all()

    for doc in documents:
        await document_service.delete_document(db, tenant_id, doc.id)

    await db.delete(folder)
    await db.commit()
