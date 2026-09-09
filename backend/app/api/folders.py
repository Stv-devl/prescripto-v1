"""Folder API endpoints."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.folder import FolderCreate, FolderList, FolderRead, FolderUpdate
from app.services import folder as folder_service

router = APIRouter(tags=["folders"])


@router.post(
    "/projects/{project_id}/folders",
    response_model=FolderRead,
    status_code=201,
)
async def create_folder(
    project_id: uuid.UUID,
    body: FolderCreate,
    db: DbSession,
    user: CurrentUser,
) -> FolderRead:
    """Create a new folder in a project."""
    folder = await folder_service.create_folder(
        db,
        tenant_id=user["tenant_id"],
        project_id=project_id,
        name=body.name,
        lot=body.lot,
        phase=body.phase,
    )
    return FolderRead(
        id=folder.id,
        project_id=folder.project_id,
        name=folder.name,
        lot=folder.lot,
        phase=folder.phase,
        document_count=0,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.get("/projects/{project_id}/folders", response_model=FolderList)
async def list_folders(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> FolderList:
    """List all folders for a project."""
    folders = await folder_service.list_folders(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )
    return FolderList(
        folders=[FolderRead(**f) for f in folders],
        total=len(folders),
    )


@router.patch("/folders/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    db: DbSession,
    user: CurrentUser,
) -> FolderRead:
    """Update a folder (name, lot, phase)."""
    folder = await folder_service.update_folder(
        db,
        tenant_id=user["tenant_id"],
        folder_id=folder_id,
        name=body.name,
        lot=body.lot,
        phase=body.phase,
    )
    return FolderRead(
        id=folder.id,
        project_id=folder.project_id,
        name=folder.name,
        lot=folder.lot,
        phase=folder.phase,
        document_count=0,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete a folder and all documents inside it."""
    await folder_service.delete_folder(db, tenant_id=user["tenant_id"], folder_id=folder_id)
