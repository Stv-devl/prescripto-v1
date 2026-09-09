"""Project service — CRUD operations with tenant isolation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.project import Project
from app.schemas.project import ProjectUpdate


async def create_project(db: AsyncSession, tenant_id: uuid.UUID, name: str, phase: str) -> Project:
    """Create a new project for the given tenant."""
    project = Project(tenant_id=tenant_id, name=name, phase=phase)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, tenant_id: uuid.UUID) -> tuple[list[Project], int]:
    """List all projects for the given tenant. Returns (projects, total)."""
    query = (
        select(Project)
        .where(Project.tenant_id == tenant_id)
        .options(selectinload(Project.documents))
        .order_by(Project.created_at.desc())
    )
    result = await db.execute(query)
    projects = list(result.scalars().all())

    count_query = select(func.count()).select_from(Project).where(Project.tenant_id == tenant_id)
    total = (await db.execute(count_query)).scalar_one()

    return projects, total


async def get_project(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    """Get a single project by ID, scoped to the tenant."""
    query = select(Project).where(Project.id == project_id).options(selectinload(Project.documents))
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if project is None:
        raise NotFoundError(f"Project {project_id} not found")
    if project.tenant_id != tenant_id:
        raise ForbiddenError("Access denied to this project")

    return project


async def update_project(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate
) -> Project:
    """Update a project's metadata, scoped to the tenant."""
    project = await get_project(db, tenant_id, project_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    return await get_project(db, tenant_id, project_id)


async def delete_project(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> None:
    """Delete a project by ID, scoped to the tenant."""
    project = await get_project(db, tenant_id, project_id)
    await db.delete(project)
    await db.commit()
