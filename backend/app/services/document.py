"""Document service — upload, list, delete with file storage."""

import re
import unicodedata
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.document import Document
from app.models.folder import Folder
from app.models.project import Project
from app.services import project as project_service
from app.services.ingestion.embedding import delete_document_vectors

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAX_FILE_SIZE = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024

_MAGIC_BYTES: dict[str, bytes] = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
}


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _assert_magic_bytes(file_path: Path, ext: str) -> None:
    """Reject a file whose real content does not match its extension.

    PDFs are checked leniently — a few producers emit bytes before `%PDF-`, and
    readers accept it — while zip containers must start with their signature.
    """
    expected = _MAGIC_BYTES.get(ext)
    if expected is None:
        return

    with file_path.open("rb") as handle:
        header = handle.read(1024)

    matches = expected in header if ext == ".pdf" else header.startswith(expected)
    if not matches:
        raise ValidationError(f"File content does not match its {ext} extension")


async def _get_folder_for_tenant(
    db: AsyncSession, tenant_id: uuid.UUID, folder_id: uuid.UUID
) -> Folder:
    """Get a folder scoped to the tenant, mirroring `folder_service.get_folder`.

    Duplicated rather than imported: `app.services.folder` imports this module
    (for `delete_folder`'s cascade), so importing it back would be a cycle.
    Same split as `get_document` — `NotFoundError` when the row is absent,
    `ForbiddenError` when it exists under another tenant.
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


def _sanitize_filename(filename: str) -> str:
    """Replace accented characters with ASCII equivalents and remove unsafe chars."""
    nfkd = unicodedata.normalize("NFKD", filename)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace(" ", "_")
    stem = Path(ascii_name).stem
    ext = Path(ascii_name).suffix
    stem = re.sub(r"[^\w\-.]", "", stem)
    return f"{stem}{ext}" if stem else f"document{ext}"


async def upload_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    file: UploadFile,
    folder_id: uuid.UUID | None = None,
) -> Document:
    """Validate, save file to disk, and create DB record."""
    await project_service.get_project(db, tenant_id, project_id)

    raw_filename = file.filename or "unknown"
    filename = _sanitize_filename(raw_filename)
    ext = _get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Format not allowed: {ext}. Accepted: PDF, DOCX, XLSX")

    if folder_id is not None:
        folder = await _get_folder_for_tenant(db, tenant_id, folder_id)
        if folder.project_id != project_id:
            raise ForbiddenError("Folder does not belong to this project")

    doc = Document(
        project_id=project_id,
        folder_id=folder_id,
        filename=filename,
        size=0,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / f"{doc.id}{ext}"

    written = 0
    try:
        with file_path.open("wb") as out:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                written += len(chunk)
                if written > MAX_FILE_SIZE:
                    raise ValidationError(f"File too large: over {MAX_FILE_SIZE} bytes")
                out.write(chunk)
        _assert_magic_bytes(file_path, ext)
    except Exception:
        file_path.unlink(missing_ok=True)
        await db.delete(doc)
        await db.commit()
        raise

    doc.size = written
    await db.commit()
    await db.refresh(doc)

    return doc


async def list_documents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> tuple[list[Document], int]:
    """List all documents for a project (verifies tenant access)."""
    await project_service.get_project(db, tenant_id, project_id)

    query = (
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(query)
    documents = list(result.scalars().all())

    count_query = (
        select(func.count()).select_from(Document).where(Document.project_id == project_id)
    )
    total = (await db.execute(count_query)).scalar_one()

    return documents, total


async def get_document(db: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    """Get a single document by ID, scoped to the tenant.

    Raises NotFoundError when no such row exists, ForbiddenError when it
    belongs to another tenant — the same split as project_service.get_project,
    which is the only precedent in this repo.
    """
    scoped = (
        select(Document)
        .join(Project, Document.project_id == Project.id)
        .where(Document.id == document_id, Project.tenant_id == tenant_id)
    )
    doc = (await db.execute(scoped)).scalar_one_or_none()
    if doc is not None:
        return doc

    exists = await db.execute(select(Document.id).where(Document.id == document_id))
    if exists.scalar_one_or_none() is None:
        raise NotFoundError(f"Document {document_id} not found")
    raise ForbiddenError("Access denied to this document")


async def delete_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """Delete document from DB and remove file from disk."""
    doc = await get_document(db, tenant_id, document_id)

    await delete_document_vectors(document_id, tenant_id)

    project_dir = UPLOAD_DIR / str(doc.project_id)
    for ext in ALLOWED_EXTENSIONS:
        file_path = project_dir / f"{doc.id}{ext}"
        if file_path.exists():
            file_path.unlink()
            break

    await db.delete(doc)
    await db.commit()


async def move_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    folder_id: uuid.UUID | None,
) -> Document:
    """Move a document to a folder (or to root if folder_id is None)."""
    doc = await get_document(db, tenant_id, document_id)

    if folder_id is not None:
        folder = await _get_folder_for_tenant(db, tenant_id, folder_id)
        if folder.project_id != doc.project_id:
            raise ForbiddenError("Folder does not belong to the same project as the document")

    doc.folder_id = folder_id
    await db.commit()
    await db.refresh(doc)
    return doc


async def run_ingestion_background(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> None:
    """Run ingestion in a background task with its own DB session.

    Everything below `get_document` is wrapped: `ingestion_pipeline.run_ingestion`
    already turns its own failures into `status="error"`, but a failure ABOVE
    it — the accessor itself, the disk lookup — was not caught anywhere, and
    left the document stuck at `status="processing"` forever with no
    `error_message`, invisible to the client. Same failure shape as
    `ingestion_pipeline.run_ingestion`'s own except clause, reused rather than
    invented.
    """
    import logging

    from app.core.database import async_session
    from app.services.ingestion import pipeline as ingestion_pipeline

    logger = logging.getLogger(__name__)
    doc: Document | None = None

    async with async_session() as db:
        try:
            doc = await get_document(db, tenant_id, document_id)
            project_dir = UPLOAD_DIR / str(doc.project_id)
            file_path = None
            for ext in (".pdf", ".docx", ".xlsx"):
                candidate = project_dir / f"{doc.id}{ext}"
                if candidate.exists():
                    file_path = candidate
                    break

            if file_path is None:
                logger.error(
                    "File not found on disk for document %s (project_dir=%s)",
                    document_id,
                    project_dir,
                )
                doc.status = "error"
                doc.error_message = "Fichier introuvable sur le disque après upload"
                await db.commit()
                return

            await ingestion_pipeline.run_ingestion(db, doc, file_path, tenant_id)
        except Exception as exc:
            logger.exception("Background ingestion failed for document %s", document_id)
            if doc is not None:
                doc.status = "error"
                doc.error_message = f"{type(exc).__name__}: {exc}"[:500]
                await db.commit()
