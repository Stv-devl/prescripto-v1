"""Document API endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Form, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.schemas.document import DocumentList, DocumentMove, DocumentRead
from app.services import document as document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentRead,
    status_code=201,
)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile,
    db: DbSession,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    folder_id: uuid.UUID | None = Form(default=None),
) -> DocumentRead:
    """Upload a document to a project (PDF, DOCX, XLSX — max 50 MB).

    The ingestion pipeline (extraction, classification, chunking, embedding)
    runs as a background task. Document status: processing → ready | error.
    """
    doc = await document_service.upload_document(
        db, tenant_id=user["tenant_id"], project_id=project_id, file=file, folder_id=folder_id
    )
    background_tasks.add_task(document_service.run_ingestion_background, doc.id, user["tenant_id"])
    return DocumentRead.model_validate(doc)


@router.get("/projects/{project_id}/documents", response_model=DocumentList)
async def list_documents(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> DocumentList:
    """List all documents for a project."""
    documents, total = await document_service.list_documents(
        db, tenant_id=user["tenant_id"], project_id=project_id
    )
    return DocumentList(
        documents=[DocumentRead.model_validate(d) for d in documents],
        total=total,
    )


@router.patch("/documents/{document_id}/move", response_model=DocumentRead)
async def move_document(
    document_id: uuid.UUID,
    body: DocumentMove,
    db: DbSession,
    user: CurrentUser,
) -> DocumentRead:
    """Move a document to a folder or back to root."""
    doc = await document_service.move_document(
        db, tenant_id=user["tenant_id"], document_id=document_id, folder_id=body.folder_id
    )
    return DocumentRead.model_validate(doc)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete a document by ID."""
    await document_service.delete_document(db, tenant_id=user["tenant_id"], document_id=document_id)
