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
  extraction → cleaning → page OCR → classification → chunking
    → embedding → Qdrant upsert → injection marking → chunk rows saved
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
cells) to avoid feeding noise to the LLM downstream.

Extraction output then goes through `cleaning.py`, which strips table-of-contents
pages, repeated headers and footers, and near-empty pages (under 50
characters). For PDFs, `ocr_sparse_pages` in `vision.py` then renders the
remaining pages with fewer than 50 characters of text and sends them to
Pixtral Large for OCR; it is skipped when the document is almost entirely
image-based.

## Classification

`mistral-large-latest`, temperature 0, JSON mode. When a PDF averages under
30 characters per page (a scanned drawing, typically), classification falls
back to a vision call on Pixtral instead of the text excerpt. Each document is tagged
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
transient errors (429/503/timeout). Vectors go into a Qdrant collection
created at startup if it doesn't exist yet (`ensure_collection` in
`embedding.py`) — there is no migration system for the vector store, unlike
Postgres.

Two collections exist, selected by the `RETRIEVAL_MODE` setting. `baseline`
uses `documents`: a single unnamed 1024-dimension cosine vector per point.
`v1` — the production pipeline — uses `documents_v1`, whose points carry two
named vectors: `dense` (the same `mistral-embed` vector) and `sparse`, a BM25
vector computed by `backend/app/services/sparse.py`. The baseline collection
is kept as the A/B reference and is never overwritten by `v1` data.

The sparse side is pure code, with no model call: text is lowercased,
accent-folded and tokenized so that references such as `DTU 20.1` stay whole;
each token maps to a stable 32-bit hash index, and a chunk's weights are BM25
term frequencies. The `sparse` vector is declared with Qdrant's IDF modifier,
so the inverse-document-frequency factor is applied server-side. `to_hybrid_point`
builds a `documents_v1` point from a dense vector and a payload, deriving the
sparse vector from the payload `text`; `hybrid_copy.py` uses it to copy a
collection into its hybrid twin (dense vectors reused, no re-embedding). At
query time the same module builds the sparse query vector, and
dense and sparse results are fused (see [`rag-chat.md`](./rag-chat.md)).

Every point's payload carries the isolation and filtering keys:

```python
# backend/app/services/qdrant_payload.py
{
    "tenant_id": ..., "project_id": ..., "document_id": ...,
    "type": ..., "lot": ..., "phase": ...,
    "filename": ..., "page": ..., "position": ..., "text": ...,
    "heading_prefix": ..., "section_title": ..., "parent_sections": ...,
    "content_type": ..., "keywords": ..., "char_count": ...,
    "localisation": ..., "ingested_at": ...,
}
```

`ensure_collection` also creates keyword payload indexes at every startup
(idempotent): `tenant_id`, `project_id`, `type`, `lot`, `phase`,
`content_type`, `document_id` and `filename` — every field used in a filter —
so tenant/project-scoped search stays fast as the collection grows.

### Prompt-injection flag

Retrieved passages are third-party text, so each upserted batch is scanned by
`mark_suspect_points` (`injection_marking.py`), which applies the heuristic
`looks_like_injection` from `backend/app/services/injection_guard.py` (no model
call). Suspect points get `injection_suspect: true` in their payload, written
with a set-payload operation that leaves vectors and other keys untouched;
clean points carry no such key. A maintenance script can backfill the flag on
an existing collection without re-embedding. How the flag is used at retrieval
time is described in [`mcp.md`](./mcp.md#prompt-injection-defences).

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
