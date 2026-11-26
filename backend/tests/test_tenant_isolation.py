"""Cross-tenant isolation tests.

Nothing in this stack enforces isolation on its own: there is no RLS, the
database happily returns any row, and a service that forgets its
`WHERE tenant_id = …` leaks another customer's data with no error and a green
type check. These tests are the barrier's only proof.

One rule when adding a service that takes a tenant key: it gets a test here.

A resource of another tenant answers `NotFoundError` (404), exactly like one
that does not exist — a distinct 403 would confirm the id is live elsewhere.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AppException, NotFoundError
from app.main import app
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

        with pytest.raises(NotFoundError):
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

        with pytest.raises(NotFoundError):
            await project_service.update_project(
                db, tenant_a.id, project.id, ProjectUpdate(name="volé")
            )

        await db.refresh(project)
        assert project.name == "Chantier"

    async def test_delete_project_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)

        with pytest.raises(NotFoundError):
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

        with pytest.raises(NotFoundError):
            await folder_service.list_folders(db, tenant_a.id, project.id)

    async def test_update_folder_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)
        folder = Folder(project_id=project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(NotFoundError):
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

        with pytest.raises(NotFoundError):
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

        with pytest.raises(NotFoundError):
            await document_service.list_documents(db, tenant_a.id, project.id)


@pytest_asyncio.fixture
async def client_as_a(db: AsyncSession, tenant_a: Tenant) -> AsyncIterator[AsyncClient]:
    """An HTTP client authenticated as a member of tenant_a, reading the test session."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": uuid.uuid4(),
        "tenant_id": tenant_a.id,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _shape(exc: AppException, resource_id: uuid.UUID) -> tuple[type, int, str]:
    """What a caller can observe of a refusal, with the requested id blanked out."""
    return type(exc), exc.status_code, exc.message.replace(str(resource_id), "<id>")


class TestForeignAndUnknownAreIndistinguishable:
    """A foreign resource must answer exactly like one that does not exist.

    Any difference — class, status, wording — tells the caller that the id is
    live in some other tenant. The foreign row does exist, so a dropped
    `tenant_id` filter would return it and fail these cases as surely as a 403.
    """

    async def test_project(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        foreign = await _project_of(db, tenant_b, "Secret de B")
        unknown_id = uuid.uuid4()

        with pytest.raises(AppException) as on_foreign:
            await project_service.get_project(db, tenant_a.id, foreign.id)
        with pytest.raises(AppException) as on_unknown:
            await project_service.get_project(db, tenant_a.id, unknown_id)

        assert _shape(on_foreign.value, foreign.id) == (NotFoundError, 404, "Project <id> not found")
        assert _shape(on_unknown.value, unknown_id) == (NotFoundError, 404, "Project <id> not found")

    async def test_folder(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)
        foreign = Folder(project_id=project.id, name="Lot 01")
        db.add(foreign)
        await db.commit()
        await db.refresh(foreign)
        unknown_id = uuid.uuid4()

        with pytest.raises(AppException) as on_foreign:
            await folder_service.get_folder(db, tenant_a.id, foreign.id)
        with pytest.raises(AppException) as on_unknown:
            await folder_service.get_folder(db, tenant_a.id, unknown_id)

        assert _shape(on_foreign.value, foreign.id) == (NotFoundError, 404, "Folder <id> not found")
        assert _shape(on_unknown.value, unknown_id) == (NotFoundError, 404, "Folder <id> not found")

    async def test_document(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        from app.services import document as document_service

        project = await _project_of(db, tenant_b)
        foreign = Document(project_id=project.id, filename="cctp.pdf", size=10, status="ready")
        db.add(foreign)
        await db.commit()
        await db.refresh(foreign)
        unknown_id = uuid.uuid4()

        with pytest.raises(AppException) as on_foreign:
            await document_service.get_document(db, tenant_a.id, foreign.id)
        with pytest.raises(AppException) as on_unknown:
            await document_service.get_document(db, tenant_a.id, unknown_id)

        assert _shape(on_foreign.value, foreign.id) == (NotFoundError, 404, "Document <id> not found")
        assert _shape(on_unknown.value, unknown_id) == (
            NotFoundError,
            404,
            "Document <id> not found",
        )

    async def test_foreign_project_over_http_answers_like_an_unknown_one(
        self, client_as_a: AsyncClient, db: AsyncSession, tenant_b: Tenant
    ) -> None:
        client = client_as_a
        foreign = await _project_of(db, tenant_b, "Secret de B")
        unknown_id = uuid.uuid4()

        on_foreign = await client.get(f"/api/projects/{foreign.id}")
        on_unknown = await client.get(f"/api/projects/{unknown_id}")

        assert on_foreign.status_code == on_unknown.status_code == 404
        assert on_foreign.json()["detail"].replace(str(foreign.id), "<id>") == on_unknown.json()[
            "detail"
        ].replace(str(unknown_id), "<id>")
