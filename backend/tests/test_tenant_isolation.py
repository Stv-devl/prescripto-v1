"""Cross-tenant isolation tests.

Nothing in this stack enforces isolation on its own: there is no RLS, the
database happily returns any row, and a service that forgets its
`WHERE tenant_id = …` leaks another customer's data with no error and a green
type check. These tests are the barrier's only proof.

One rule when adding a service that takes a tenant key: it gets a test here.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.document import Document
from app.models.folder import Folder
from app.models.tenant import Tenant
from app.schemas.project import ProjectUpdate
from app.services import folder as folder_service
from app.services import project as project_service

pytestmark = pytest.mark.asyncio


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier"):
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


class TestProjectIsolation:
    async def test_get_project_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")

        with pytest.raises(ForbiddenError):
            await project_service.get_project(db, tenant_a.id, project.id)

    async def test_list_projects_only_returns_own_tenant(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        await _project_of(db, tenant_a, "À moi")
        await _project_of(db, tenant_b, "À l'autre")

        projects, total = await project_service.list_projects(db, tenant_a.id)

        assert total == 1
        assert [p.name for p in projects] == ["À moi"]

    async def test_update_project_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)

        with pytest.raises(ForbiddenError):
            await project_service.update_project(
                db, tenant_a.id, project.id, ProjectUpdate(name="volé")
            )

        await db.refresh(project)
        assert project.name == "Chantier"

    async def test_delete_project_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)

        with pytest.raises(ForbiddenError):
            await project_service.delete_project(db, tenant_a.id, project.id)

        assert await project_service.get_project(db, tenant_b.id, project.id) is not None

    async def test_unknown_project_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        with pytest.raises(NotFoundError):
            await project_service.get_project(db, tenant_a.id, uuid.uuid4())


class TestFolderIsolation:
    async def test_list_folders_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)
        db.add(Folder(project_id=project.id, name="Lot 01"))
        await db.commit()

        with pytest.raises(ForbiddenError):
            await folder_service.list_folders(db, tenant_a.id, project.id)

    async def test_update_folder_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)
        folder = Folder(project_id=project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(ForbiddenError):
            await folder_service.update_folder(db, tenant_a.id, folder.id, name="volé")

        await db.refresh(folder)
        assert folder.name == "Lot 01"

    async def test_delete_folder_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)
        folder = Folder(project_id=project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(ForbiddenError):
            await folder_service.delete_folder(db, tenant_a.id, folder.id)

    # `get_folder` used to be exercised here by a case documenting that it took
    # no tenant argument. It takes one now, and its contract lives in
    # tests/services/test_folder.py, at the mirror path. Re-asserting it here
    # would be a twin that drifts at the next signature change.


class TestDocumentIsolation:
    async def test_list_documents_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        from app.services import document as document_service

        project = await _project_of(db, tenant_b)
        db.add(Document(project_id=project.id, filename="cctp.pdf", size=10, status="ready"))
        await db.commit()

        with pytest.raises(ForbiddenError):
            await document_service.list_documents(db, tenant_a.id, project.id)
