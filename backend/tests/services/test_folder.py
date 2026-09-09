"""Tenant scoping of the folder service accessor.

`get_folder` is the low-level accessor every folder operation goes through.
Today it takes no tenant key: the barrier lives in its callers, and nothing
stops a future caller from reading another customer's row. These tests state
the contract it must satisfy on its own — the same one `get_project` already
has: `NotFoundError` when the row does not exist, `ForbiddenError` when it
belongs to someone else.

The cross-tenant guardrails for `update_folder` and `delete_folder` are not
repeated here: `test_tenant_isolation.py` already carries them, and a twin
assertion would drift the day one of the two signatures moves.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.document import Document
from app.models.folder import Folder
from app.models.project import Project
from app.models.tenant import Tenant
from app.services import folder as folder_service
from app.services import project as project_service


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier") -> Project:
    """Create a project owned by the given tenant."""
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


async def _folder_of(db: AsyncSession, project: Project, name: str = "Lot 01") -> Folder:
    """Create a folder inside the given project."""
    folder = Folder(project_id=project.id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


class TestGetFolderTenantScope:
    async def test_get_folder_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """An exact id for a folder that really exists still buys tenant A nothing."""
        project = await _project_of(db, tenant_b, "Secret de B")
        folder = await _folder_of(db, project, "Lot 07 - Carrelage")

        with pytest.raises(ForbiddenError):
            await folder_service.get_folder(db, tenant_a.id, folder.id)

    async def test_get_folder_with_its_own_tenant_returns_the_row(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The legitimate owner still gets the folder it asked for."""
        project = await _project_of(db, tenant_a)
        folder = await _folder_of(db, project, "Lot 01")

        fetched = await folder_service.get_folder(db, tenant_a.id, folder.id)

        assert fetched.id == folder.id
        assert fetched.name == "Lot 01"
        assert fetched.project_id == project.id

    async def test_get_folder_unknown_id_is_not_found_and_differs_from_refusal(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """An absent row and a foreign row do not answer with the same exception."""
        project = await _project_of(db, tenant_b, "Secret de B")
        folder = await _folder_of(db, project, "Lot 07 - Carrelage")

        with pytest.raises(NotFoundError) as absent:
            await folder_service.get_folder(db, tenant_a.id, uuid.uuid4())

        with pytest.raises(ForbiddenError) as refused:
            await folder_service.get_folder(db, tenant_a.id, folder.id)

        assert type(absent.value) is not type(refused.value)
        assert absent.value.status_code == 404
        assert refused.value.status_code == 403


class TestDeleteFolderNominalPath:
    """The half of delete_folder that no cross-tenant test can reach.

    Every existing case stops at the ForbiddenError, so the body of the
    function — the loop that removes the documents it contains — has never
    been executed by the suite. Dropping that loop would leave orphan rows in
    the database and orphan vectors in Qdrant, and every test would stay green.
    """

    async def test_delete_folder_removes_the_documents_it_contains(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        folder = await _folder_of(db, project)
        inside = Document(
            project_id=project.id, folder_id=folder.id, filename="cctp.pdf", type="CCTP"
        )
        outside = Document(project_id=project.id, filename="dpgf.xlsx", type="DPGF")
        db.add_all([inside, outside])
        await db.commit()
        await db.refresh(inside)
        await db.refresh(outside)
        inside_id, outside_id = inside.id, outside.id

        # The vector store is the one side effect with no local double.
        with patch(
            "app.services.document.delete_document_vectors", new=AsyncMock()
        ) as drop_vectors:
            await folder_service.delete_folder(db, tenant_a.id, folder.id)

        db.expire_all()
        assert (await db.execute(select(Folder.id).where(Folder.id == folder.id))).scalar_one_or_none() is None
        assert (
            await db.execute(select(Document.id).where(Document.id == inside_id))
        ).scalar_one_or_none() is None
        # A document of the same project but outside the folder must survive.
        assert (
            await db.execute(select(Document.id).where(Document.id == outside_id))
        ).scalar_one_or_none() == outside_id
        assert drop_vectors.await_count == 1
