"""Proof that the schema's `ondelete=` clauses actually fire in this suite.

`tests/conftest.py` used to build the SQLite test engine with foreign-key
enforcement OFF (SQLite's own default), so `Folder.project_id` CASCADE and
`Document.folder_id` SET NULL were never exercised: a delete that violated one
of those constraints just succeeded silently, leaving orphaned or dangling
rows the app would never see in Postgres. Now that the engine turns FK
enforcement on, these are the first tests that actually walk that path.

Every delete here goes through SQLAlchemy Core (`delete(...)`), not
`AsyncSession.delete(instance)`: the ORM's own `cascade="all, delete-orphan"`
would otherwise do the cleanup itself and the test would pass even with FK
enforcement off, proving nothing about the database constraint.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.folder import Folder
from app.models.project import Project
from app.models.tenant import Tenant
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


class TestFolderDeletionSetsDocumentFolderIdToNull:
    async def test_deleting_a_folder_nulls_the_folder_id_of_its_documents(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """`Document.folder_id` carries `ondelete=SET NULL` — the document itself must survive."""
        project = await _project_of(db, tenant_a)
        folder = await _folder_of(db, project)
        document = Document(project_id=project.id, folder_id=folder.id, filename="cctp.pdf")
        db.add(document)
        await db.commit()
        document_id = document.id

        # Core DELETE bypasses the ORM unit of work entirely: only a real
        # database-level constraint can null the child row from here.
        await db.execute(delete(Folder).where(Folder.id == folder.id))
        await db.commit()

        db.expire_all()
        reloaded = (
            await db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one()
        assert reloaded.folder_id is None

    async def test_a_document_outside_the_folder_is_left_untouched(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """A document that never pointed at the deleted folder keeps its own state."""
        project = await _project_of(db, tenant_a)
        folder = await _folder_of(db, project)
        other_folder = await _folder_of(db, project, name="Lot 02")
        other_folder_id = other_folder.id
        elsewhere = Document(project_id=project.id, folder_id=other_folder_id, filename="dpgf.xlsx")
        db.add(elsewhere)
        await db.commit()
        elsewhere_id = elsewhere.id

        await db.execute(delete(Folder).where(Folder.id == folder.id))
        await db.commit()

        db.expire_all()
        reloaded = (
            await db.execute(select(Document).where(Document.id == elsewhere_id))
        ).scalar_one()
        assert reloaded.folder_id == other_folder_id


class TestProjectDeletionCascadesToFoldersAndDocuments:
    async def test_deleting_a_project_deletes_its_folders_and_documents(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """`Folder.project_id` and `Document.project_id` both carry `ondelete=CASCADE`."""
        project = await _project_of(db, tenant_a)
        folder = await _folder_of(db, project)
        document = Document(project_id=project.id, folder_id=folder.id, filename="cctp.pdf")
        db.add(document)
        await db.commit()
        folder_id, document_id, project_id = folder.id, document.id, project.id

        await db.execute(delete(Project).where(Project.id == project_id))
        await db.commit()

        db.expire_all()
        assert (
            await db.execute(select(Folder.id).where(Folder.id == folder_id))
        ).scalar_one_or_none() is None
        assert (
            await db.execute(select(Document.id).where(Document.id == document_id))
        ).scalar_one_or_none() is None

    async def test_a_folder_of_another_project_survives(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The cascade must stay scoped to the deleted project's own rows."""
        doomed = await _project_of(db, tenant_a, name="Chantier A")
        spared = await _project_of(db, tenant_a, name="Chantier B")
        spared_folder = await _folder_of(db, spared, name="Lot 01")
        spared_folder_id = spared_folder.id

        await db.execute(delete(Project).where(Project.id == doomed.id))
        await db.commit()

        db.expire_all()
        assert (
            await db.execute(select(Folder.id).where(Folder.id == spared_folder_id))
        ).scalar_one() == spared_folder_id
