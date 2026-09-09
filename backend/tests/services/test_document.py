"""The document service: tenant scoping of its accessor, and upload validation.

`get_document` is the low-level accessor every document operation goes through.
Today it takes no tenant key: the barrier lives in its callers, and nothing
stops a future caller from reading another customer's row. These tests state
the contract it must satisfy on its own — the same one `get_project` already
has: `NotFoundError` when the row does not exist, `ForbiddenError` when it
belongs to someone else.

`TestDocumentOperationsStayIsolated` holds guardrails: `delete_document` and
`move_document` already refuse cross-tenant access through the parent project,
and they must keep refusing once the check moves down into the accessor.

The three upload classes were `test_document_upload.py` until the TDD mirror was
repaired: both files exercised `app/services/document.py`, and the mirror is one
module to one test file. Their cases are carried over unchanged.
"""

import io
import uuid
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.document import Document
from app.models.folder import Folder
from app.models.project import Project
from app.models.tenant import Tenant
from app.services import document as document_service
from app.services import project as project_service

pytestmark = pytest.mark.asyncio

PDF_HEADER = b"%PDF-"


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name)


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never write into the real uploads/ directory from a test."""
    monkeypatch.setattr(document_service, "UPLOAD_DIR", tmp_path)
    return tmp_path


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier") -> Project:
    """Create a project owned by the given tenant."""
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


async def _document_of(
    db: AsyncSession, project: Project, filename: str = "cctp.pdf"
) -> Document:
    """Create a document at the root of the given project."""
    document = Document(project_id=project.id, filename=filename, size=10, status="ready")
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def _reload(db: AsyncSession, document_id: uuid.UUID) -> Document | None:
    """Re-read a document straight from the database, bypassing the identity map."""
    db.expire_all()
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def _document_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Document))).scalar_one()


class TestGetDocumentTenantScope:
    async def test_get_document_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Tenant A asking for a document of tenant B is denied, not served the row."""
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project, "secret.pdf")

        with pytest.raises(ForbiddenError):
            await document_service.get_document(db, tenant_a.id, document.id)

    async def test_get_document_with_its_own_tenant_returns_the_row(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The legitimate owner still gets the document it asked for."""
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf")

        fetched = await document_service.get_document(db, tenant_a.id, document.id)

        assert fetched.id == document.id
        assert fetched.filename == "cctp.pdf"
        assert fetched.project_id == project.id

    async def test_get_document_unknown_id_is_not_found_and_differs_from_refusal(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """An absent row and a foreign row do not answer with the same exception."""
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project, "secret.pdf")

        with pytest.raises(NotFoundError) as absent:
            await document_service.get_document(db, tenant_a.id, uuid.uuid4())

        with pytest.raises(ForbiddenError) as refused:
            await document_service.get_document(db, tenant_a.id, document.id)

        assert type(absent.value) is not type(refused.value)
        assert absent.value.status_code == 404
        assert refused.value.status_code == 403


class TestDocumentOperationsStayIsolated:
    async def test_delete_document_of_another_tenant_is_still_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Deleting across tenants is denied and leaves the row in place."""
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project, "secret.pdf")

        with pytest.raises(ForbiddenError):
            await document_service.delete_document(
                db, tenant_id=tenant_a.id, document_id=document.id
            )

        survivor = await _reload(db, document.id)
        assert survivor is not None
        assert survivor.filename == "secret.pdf"

    async def test_move_document_of_another_tenant_is_still_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Moving across tenants is denied and leaves the document at the root."""
        project = await _project_of(db, tenant_b, "Secret de B")
        folder = Folder(project_id=project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)
        document = await _document_of(db, project, "secret.pdf")

        with pytest.raises(ForbiddenError):
            await document_service.move_document(
                db, tenant_id=tenant_a.id, document_id=document.id, folder_id=folder.id
            )

        unmoved = await _reload(db, document.id)
        assert unmoved is not None
        assert unmoved.folder_id is None


class TestUploadValidation:
    async def test_accepts_a_real_pdf(
        self, db: AsyncSession, tenant_a: Tenant, upload_dir: Path
    ) -> None:
        project = await _project_of(db, tenant_a)
        payload = PDF_HEADER + b"0" * 2048

        doc = await document_service.upload_document(
            db, tenant_a.id, project.id, _upload("plan.pdf", payload)
        )

        assert doc.size == len(payload)
        assert doc.status == "processing"
        stored = upload_dir / str(project.id) / f"{doc.id}.pdf"
        assert stored.read_bytes() == payload

    async def test_rejects_unknown_extension(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)

        with pytest.raises(ValidationError):
            await document_service.upload_document(
                db, tenant_a.id, project.id, _upload("payload.exe", b"MZ")
            )

        assert await _document_count(db) == 0

    async def test_rejects_a_file_over_the_ceiling(
        self, db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ceiling is enforced while streaming, so the bytes never all land."""
        monkeypatch.setattr(document_service, "MAX_FILE_SIZE", 1024)
        monkeypatch.setattr(document_service, "UPLOAD_CHUNK_SIZE", 256)
        project = await _project_of(db, tenant_a)

        with pytest.raises(ValidationError):
            await document_service.upload_document(
                db, tenant_a.id, project.id, _upload("big.pdf", PDF_HEADER + b"0" * 4096)
            )

        assert await _document_count(db) == 0

    async def test_rejects_content_that_is_not_what_the_extension_claims(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)

        with pytest.raises(ValidationError):
            await document_service.upload_document(
                db, tenant_a.id, project.id, _upload("fake.pdf", b"<html>hello</html>")
            )

        assert await _document_count(db) == 0


class TestUploadCleanup:
    async def test_a_rejected_upload_leaves_no_file_and_no_row(
        self, db: AsyncSession, tenant_a: Tenant, upload_dir: Path
    ) -> None:
        project = await _project_of(db, tenant_a)

        with pytest.raises(ValidationError):
            await document_service.upload_document(
                db, tenant_a.id, project.id, _upload("fake.pdf", b"not a pdf at all")
            )

        assert await _document_count(db) == 0
        project_dir = upload_dir / str(project.id)
        assert not project_dir.exists() or list(project_dir.iterdir()) == []


class TestUploadIsolation:
    async def test_upload_into_another_tenant_project_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b)

        with pytest.raises(ForbiddenError):
            await document_service.upload_document(
                db, tenant_a.id, project.id, _upload("plan.pdf", PDF_HEADER + b"0" * 16)
            )

        assert await _document_count(db) == 0

    async def test_unknown_project_is_refused(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        with pytest.raises(NotFoundError):
            await document_service.upload_document(
                db, tenant_a.id, uuid.uuid4(), _upload("plan.pdf", PDF_HEADER)
            )


class _ReuseSession:
    """Hands the background task the test's own session instead of a fresh one.

    `run_ingestion_background` opens its session through
    `app.core.database.async_session`, bound to the real database URL.
    Swapping it for this wrapper lets the background task see the exact rows
    the test set up on the in-memory `db` fixture, and lets the test read back
    what the task wrote — same connection, no second database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class TestRunIngestionBackground:
    async def test_uses_document_id_and_tenant_id_in_call_order(
        self,
        db: AsyncSession,
        tenant_a: Tenant,
        upload_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The call site passes `(doc.id, tenant_id)` positionally
        (`app/api/documents.py`). A swap in either the signature or the call
        would make `get_document` look up a document id that is really a
        tenant id (or the reverse) — never a real row in practice — so the
        pipeline would never run and the document would stay untouched.
        """
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf")
        project_dir = upload_dir / str(project.id)
        project_dir.mkdir(parents=True)
        (project_dir / f"{document.id}.pdf").write_bytes(PDF_HEADER + b"0" * 16)

        async def fake_run_ingestion(
            session: AsyncSession, doc: Document, file_path: Path, tenant_id: uuid.UUID
        ) -> None:
            doc.status = "ready"
            await session.commit()

        monkeypatch.setattr("app.services.ingestion.pipeline.run_ingestion", fake_run_ingestion)
        monkeypatch.setattr("app.core.database.async_session", lambda: _ReuseSession(db))

        await document_service.run_ingestion_background(document.id, tenant_a.id)

        processed = await _reload(db, document.id)
        assert processed is not None
        assert processed.status == "ready"

    async def test_marks_document_as_error_when_ingestion_raises_unexpectedly(
        self,
        db: AsyncSession,
        tenant_a: Tenant,
        upload_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failure the pipeline itself never gets a chance to handle — inside
        `get_document`, the disk lookup, or anywhere before its own try/except
        takes over — used to leave the document stuck at `status="processing"`
        forever, with no `error_message`. It must now land in the same failure
        state the pipeline uses for its own errors.
        """
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf")
        project_dir = upload_dir / str(project.id)
        project_dir.mkdir(parents=True)
        (project_dir / f"{document.id}.pdf").write_bytes(PDF_HEADER + b"0" * 16)

        async def boom(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("ingestion exploded")

        monkeypatch.setattr("app.services.ingestion.pipeline.run_ingestion", boom)
        monkeypatch.setattr("app.core.database.async_session", lambda: _ReuseSession(db))

        await document_service.run_ingestion_background(document.id, tenant_a.id)

        failed = await _reload(db, document.id)
        assert failed is not None
        assert failed.status == "error"
        assert failed.error_message is not None
        assert "RuntimeError" in failed.error_message


class TestFolderOwnershipOracle:
    async def test_upload_document_with_nonexistent_folder_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)

        with pytest.raises(NotFoundError):
            await document_service.upload_document(
                db,
                tenant_a.id,
                project.id,
                _upload("plan.pdf", PDF_HEADER),
                folder_id=uuid.uuid4(),
            )

    async def test_upload_document_with_folder_from_another_project_is_forbidden(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """A folder that exists, just not under this project, is a 403 — not
        the blanket 422 this used to answer with, and not a 404 either: the
        row is real, it just belongs elsewhere."""
        project = await _project_of(db, tenant_a, "Chantier A")
        other_project = await _project_of(db, tenant_a, "Chantier B")
        folder = Folder(project_id=other_project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(ForbiddenError) as exc_info:
            await document_service.upload_document(
                db,
                tenant_a.id,
                project.id,
                _upload("plan.pdf", PDF_HEADER),
                folder_id=folder.id,
            )

        assert exc_info.value.status_code == 403

    async def test_move_document_with_nonexistent_folder_is_not_found(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project)

        with pytest.raises(NotFoundError):
            await document_service.move_document(
                db, tenant_id=tenant_a.id, document_id=document.id, folder_id=uuid.uuid4()
            )

    async def test_move_document_with_folder_from_another_project_is_forbidden(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a, "Chantier A")
        document = await _document_of(db, project)
        other_project = await _project_of(db, tenant_a, "Chantier B")
        folder = Folder(project_id=other_project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(ForbiddenError) as exc_info:
            await document_service.move_document(
                db, tenant_id=tenant_a.id, document_id=document.id, folder_id=folder.id
            )

        assert exc_info.value.status_code == 403

    async def test_get_folder_for_tenant_rejects_a_folder_owned_by_another_tenant(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """The two tests above never leave `tenant_a`: `other_project` is still
        `tenant_a`'s own, so the `ForbiddenError` they observe is proved by the
        caller's own `folder.project_id != project_id` check, not by
        `_get_folder_for_tenant`'s tenant-scoped query — that query still
        matches, same tenant on both sides. Calling the oracle directly, on a
        folder genuinely owned by `tenant_b`, is the only way to exercise its
        own `Project.tenant_id == tenant_id` predicate rather than the
        caller's redundant project-id equality check."""
        other_tenant_project = await _project_of(db, tenant_b, "Chantier de B")
        folder = Folder(project_id=other_tenant_project.id, name="Lot 01")
        db.add(folder)
        await db.commit()
        await db.refresh(folder)

        with pytest.raises(ForbiddenError) as exc_info:
            await document_service._get_folder_for_tenant(db, tenant_a.id, folder.id)

        assert exc_info.value.status_code == 403
