"""The project service — the pivot of tenant verification in this backend.

`folder`, `document` and `conversation` all delegate their tenant check to
`get_project`. Nothing else enforces isolation: there is no RLS and no Postgres
policy, so a dropped `WHERE tenant_id` here opens every service above it at once.

Two exceptions carry different meanings and must keep doing so: `NotFoundError`
when the row exists for nobody, `ForbiddenError` when it belongs to someone else.
Collapsing them into one would hide a missing check behind a plausible 404.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.project import Project
from app.models.tenant import Tenant
from app.schemas.project import ProjectUpdate
from app.services import project as project_service

pytestmark = pytest.mark.asyncio


async def _reload(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """Re-read straight from the database, bypassing the identity map."""
    db.expire_all()
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def _stamp(db: AsyncSession, project: Project, when: datetime) -> None:
    """Pin `created_at` explicitly.

    SQLite resolves `server_default=func.now()` to CURRENT_TIMESTAMP, which has
    one-second resolution: three rows created in a row share one timestamp, and
    an ordering assertion then passes on scan order instead of on the ORDER BY.
    """
    project.created_at = when
    await db.commit()


class TestProjectCrud:
    async def test_create_project_stores_it_under_the_calling_tenant(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await project_service.create_project(
            db, tenant_a.id, name="Chantier Nord", phase="PRO"
        )

        assert project.id is not None
        assert project.tenant_id == tenant_a.id
        assert project.name == "Chantier Nord"
        assert project.phase == "PRO"

    async def test_get_project_returns_a_project_of_the_calling_tenant(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        created = await project_service.create_project(
            db, tenant_a.id, name="Chantier Nord", phase="PRO"
        )

        fetched = await project_service.get_project(db, tenant_a.id, created.id)

        assert fetched.id == created.id
        assert fetched.name == "Chantier Nord"

    async def test_list_projects_returns_only_the_calling_tenants_projects(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        await project_service.create_project(db, tenant_a.id, name="À moi", phase="PRO")
        await project_service.create_project(db, tenant_b.id, name="Au voisin", phase="PRO")

        projects, _ = await project_service.list_projects(db, tenant_a.id)

        assert [p.name for p in projects] == ["À moi"]

    async def test_list_projects_total_counts_exactly_what_it_returns(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        for name in ("Un", "Deux", "Trois"):
            await project_service.create_project(db, tenant_a.id, name=name, phase="PRO")
        await project_service.create_project(db, tenant_b.id, name="Au voisin", phase="PRO")

        projects, total = await project_service.list_projects(db, tenant_a.id)

        assert total == len(projects) == 3

    async def test_update_project_applies_only_the_fields_present_in_the_payload(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        created = await project_service.create_project(
            db, tenant_a.id, name="Ancien nom", phase="PRO"
        )

        updated = await project_service.update_project(
            db, tenant_a.id, created.id, ProjectUpdate(name="Nouveau nom")
        )

        assert updated.name == "Nouveau nom"
        assert updated.phase == "PRO"

    async def test_delete_project_removes_it_and_a_later_get_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        created = await project_service.create_project(
            db, tenant_a.id, name="Éphémère", phase="PRO"
        )

        await project_service.delete_project(db, tenant_a.id, created.id)

        with pytest.raises(NotFoundError):
            await project_service.get_project(db, tenant_a.id, created.id)


class TestProjectIsolation:
    async def test_get_project_of_another_tenant_is_forbidden_not_not_found(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """The two answers must stay distinguishable — a 404 here would hide the check."""
        foreign = await project_service.create_project(
            db, tenant_b.id, name="Secret de B", phase="PRO"
        )

        with pytest.raises(ForbiddenError) as refused:
            await project_service.get_project(db, tenant_a.id, foreign.id)

        assert refused.value.status_code == 403

    async def test_get_project_unknown_id_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        with pytest.raises(NotFoundError) as absent:
            await project_service.get_project(db, tenant_a.id, uuid.uuid4())

        assert absent.value.status_code == 404

    async def test_update_project_of_another_tenant_is_refused_and_changes_nothing(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        foreign = await project_service.create_project(
            db, tenant_b.id, name="Secret de B", phase="PRO"
        )

        with pytest.raises(ForbiddenError):
            await project_service.update_project(
                db, tenant_a.id, foreign.id, ProjectUpdate(name="Détourné")
            )

        survivor = await _reload(db, foreign.id)
        assert survivor is not None
        assert survivor.name == "Secret de B"

    async def test_delete_project_of_another_tenant_is_refused_and_the_row_survives(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        foreign = await project_service.create_project(
            db, tenant_b.id, name="Secret de B", phase="PRO"
        )

        with pytest.raises(ForbiddenError):
            await project_service.delete_project(db, tenant_a.id, foreign.id)

        survivor = await _reload(db, foreign.id)
        assert survivor is not None
        assert survivor.name == "Secret de B"

    async def test_list_projects_is_empty_for_a_tenant_that_owns_nothing(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        for name in ("Un", "Deux"):
            await project_service.create_project(db, tenant_b.id, name=name, phase="PRO")

        projects, total = await project_service.list_projects(db, tenant_a.id)

        assert projects == []
        assert total == 0


class TestProjectEdgeCases:
    async def test_update_project_with_an_empty_payload_changes_nothing(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """`exclude_none` drops every field, so the row must come back untouched."""
        created = await project_service.create_project(
            db, tenant_a.id, name="Intact", phase="PRO"
        )

        updated = await project_service.update_project(
            db, tenant_a.id, created.id, ProjectUpdate()
        )

        assert updated.name == "Intact"
        assert updated.phase == "PRO"

    async def test_list_projects_orders_most_recent_first(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        first = await project_service.create_project(db, tenant_a.id, name="p1", phase="PRO")
        second = await project_service.create_project(db, tenant_a.id, name="p2", phase="PRO")
        third = await project_service.create_project(db, tenant_a.id, name="p3", phase="PRO")
        await _stamp(db, first, datetime(2026, 1, 1, 10, 0, 0))
        await _stamp(db, second, datetime(2026, 1, 2, 10, 0, 0))
        await _stamp(db, third, datetime(2026, 1, 3, 10, 0, 0))

        projects, _ = await project_service.list_projects(db, tenant_a.id)

        assert [p.name for p in projects] == ["p3", "p2", "p1"]
