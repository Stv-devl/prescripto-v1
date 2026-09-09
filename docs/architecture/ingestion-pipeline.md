# Document ingestion pipeline

A CCTP upload goes through extraction → cleaning → classification →
chunking → embedding before it's queryable. The pipeline lives in
`backend/app/services/ingestion/`, one file per step, and runs as a FastAPI
background task so the upload request returns immediately.

```
POST /projects/{id}/documents
  → save to disk, create Document(status="uploading")
  → background_tasks.add_task(run_ingestion_background)
  → 201, client polls document status

run_ingestion_background:
  extraction → cleaning/OCR → classification → chunking → embedding → Qdrant upsert
  on any failure: Document(status="error", error_message=...)
```

## Upload

`backend/app/api/documents.py` accepts `.pdf`, `.docx`, `.xlsx`, up to 50 MB,
validated by magic bytes (not just the extension — a renamed `.exe` with a
`.pdf` extension is rejected). The file streams to disk in 1 MB chunks
(`uploads/{project_id}/{document_id}.{ext}`) rather than loading the whole
upload into memory.

## Extraction

Format-specific handlers in `extraction.py`: PyMuPDF (`fitz`) for PDF,
`python-docx` for DOCX, `openpyxl` for XLSX. PDF extraction detects tables
and converts them to markdown, filtering out sparse ones (below 30% filled
cells) to avoid feeding noise to the LLM downstream. Pages with too little
extractable text (under 30 characters/page — a scanned page, typically) fall
back to vision-based OCR classification instead of plain text extraction.

## Classification

`mistral-large-latest`, temperature 0, JSON mode. Each document is tagged
with a `type` (CCTP, CR, fiche_technique, plan, email, estimatif, DPGF,
etude_sol, etude_thermique, rapport_amiante, or autre), a `lot`, and a
`phase` (ESQ/APS/APD/PRO/DCE/EXE). Plans are classified but skip chunking
and embedding entirely — there's nothing useful to retrieve from a drawing's
extracted text.

## Chunking

The chunker is type-aware, not one-size-fits-all: CCTP/DPGF/technical-study
documents split on article numbering (`1.2.3 - Title`, `LOT 03`), meeting
reports split on numbered points, technical sheets split on their own
section markers, and everything else falls back to paragraph splitting.
Target size is 2,500 characters with 300 characters of overlap (~12%), floor
250 characters.

Each chunk keeps its position in the document (page, character offset,
parent section headings) and gets a first pass of keyword extraction —
regex patterns for materials, standards (DTU, NF, Eurocodes), performance
values, and building locations — so the retrieval side can filter or boost
on more than embedding similarity alone.

## Embedding & storage

`mistral-embed`, 1024 dimensions, batched 10 chunks per call with retry on
transient errors (429/503/timeout). Vectors go into a single Qdrant
collection, `documents`, created at startup if it doesn't exist yet — there
is no migration system for the vector store, unlike Postgres.

Every point's payload carries the isolation and filtering keys as indexed
fields:

```python
# backend/app/services/qdrant_payload.py
{
    "tenant_id": ..., "project_id": ..., "document_id": ...,   # indexed
    "type": ..., "lot": ..., "phase": ...,
    "filename": ..., "page": ..., "position": ..., "text": ...,
    "heading_prefix": ..., "section_title": ..., "parent_sections": ...,
    "content_type": ..., "keywords": ..., "char_count": ...,
    "ingested_at": ...,
}
```

`tenant_id` and `project_id` are indexed as keyword fields specifically so
tenant/project-scoped search stays fast as the collection grows.

## Document status

`Document.status` moves through `uploading → processing → ready`, or
`error` (with `error_message` set) if any pipeline step throws, or `empty`
when nothing chunkable came out of extraction. The whole pipeline runs
inside one try/except at the top so a failure at any step still leaves the
document in a legible state instead of stuck mid-flight.

## Where this differs from the original design doc

`docs/architecture-rag.md` was written before the pipeline existed and
describes the intended shape rather than the shipped one. The concrete
differences, for anyone reading both:

| Design doc | Actual code |
| --- | --- |
| `document_type` metadata field | `type` |
| Chunk target "500-1000 tokens" | 2,500 characters (roughly the same range, just specified differently) |
| Cross-encoder re-ranking on global search | Not implemented |
| A `date` field per chunk | Not extracted — only `ingested_at` |
