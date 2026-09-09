"""Project API endpoints."""

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.project import ProjectCreate, ProjectList, ProjectRead, ProjectUpdate
from app.services import project as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
) -> ProjectRead:
    """Create a new project."""
    proj = await project_service.create_project(
        db, tenant_id=user["tenant_id"], name=body.name, phase=body.phase
    )
    return ProjectRead(**ProjectRead.model_validate(proj).model_dump() | {"document_count": 0})


@router.get("", response_model=ProjectList)
async def list_projects(
    db: DbSession,
    user: CurrentUser,
) -> ProjectList:
    """List all projects for the current tenant."""
    projects, total = await project_service.list_projects(db, tenant_id=user["tenant_id"])
    return ProjectList(
        projects=[
            ProjectRead(
                **ProjectRead.model_validate(p).model_dump() | {"document_count": len(p.documents)}
            )
            for p in projects
        ],
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> ProjectRead:
    """Get a project by ID."""
    proj = await project_service.get_project(db, tenant_id=user["tenant_id"], project_id=project_id)
    return ProjectRead(
        **ProjectRead.model_validate(proj).model_dump() | {"document_count": len(proj.documents)}
    )


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: DbSession,
    user: CurrentUser,
) -> ProjectRead:
    """Update project metadata."""
    proj = await project_service.update_project(
        db, tenant_id=user["tenant_id"], project_id=project_id, data=body
    )
    return ProjectRead(
        **ProjectRead.model_validate(proj).model_dump() | {"document_count": len(proj.documents)}
    )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete a project by ID."""
    await project_service.delete_project(db, tenant_id=user["tenant_id"], project_id=project_id)
