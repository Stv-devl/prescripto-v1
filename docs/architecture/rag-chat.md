# RAG chat: retrieval, generation, streaming

`POST /projects/{project_id}/chat` streams a Mistral answer back over SSE,
grounded in the project's ingested corpus. Chat is always project-scoped —
see [Scope, honestly](#scope-honestly) below.

```
question
  → embed (mistral-embed)
  → Qdrant search, tenant_id + project_id filter, score threshold 0.55
  → enrichment (expand heading-only chunks, pull in DPGF quantity chunks)
  → context assembly (group by lot, cap at 20k/48k chars)
  → Mistral (mistral-large-latest, streamed)
  → SSE: conversation_id → tokens → structured/schema (if any) → sources → [DONE]
  → persist assistant Message
```

The pipeline lives in `backend/app/services/chat/`, split by concern:
`stream.py` (orchestrator), `conversation.py` (CRUD + deserialization),
`prompts.py` (system prompt, constants), `query_rewrite.py`,
`chunk_enrichment.py`, `context_enrichment.py`, `schema_extraction.py`,
`table_extraction.py`.

## Retrieval

Every search carries both `tenant_id` and `project_id` as Qdrant filter
conditions — never one without the other. Score threshold starts at 0.55 and
falls back to 0.35 if nothing clears the bar. A few deliberate adjustments
happen before the top results are used:

- **Version dedup** — when a document type is versioned (a CCTP re-uploaded
  with corrections, say), only the latest ingested version's chunks are
  kept; older ones are silently excluded from results.
- **Score penalties** — diagnostic-report chunks (asbestos, soil, thermal
  studies) are penalized 0.85× unless the question is clearly about that
  topic; admin-only chunks are penalized 0.80×. Both penalties are logged at
  DEBUG, not INFO — a chunk that got suppressed this way doesn't show up
  anywhere an operator would normally look.
- **Enrichment** — heading-only chunks get expanded with their following
  content, and DPGF (quantity schedule) chunks relevant to the question are
  pulled in even if they scored below threshold on their own.

## Prompt construction

Retrieved chunks are grouped by `lot` (`=== Lot Name ===` sections),
formatted as `[filename, p.page]\ntext`, deduplicated by normalized text,
and capped at 20,000 characters for a focused question or 48,000 for a
broad one. The system prompt branches on scope: broad questions get
instructions to enumerate exhaustively and format as bullet points with a
disclaimer footer; focused questions get instructions to always cite page
and section. The last 6 messages of conversation history are included on
every call.

## Generation & streaming

`mistral-large-latest`, temperature 0.1, streamed token-by-token via
`mistral_client.chat.stream_async()`. Structured extraction (a data table,
a technical schema) runs in parallel background tasks while text is still
streaming, not after. The SSE event sequence:

```
data: {"conversation_id": "..."}
data: {"text": "token"}          # repeated per token
data: {"structured": {...}}      # optional — table extraction result
data: {"schema": {...}}          # optional — schema extraction result
data: {"sources": [...]}
data: [DONE]
```

## Source traceability

Sources are built from the chunks actually used in the answer, not from the
raw retrieval set: filtered by a minimum text length, deduplicated by
normalized content, grouped by `(document_id, page)` so multiple fragments
from the same page collapse into one entry, and capped at 5 displayed
sources. Each carries `document_id`, `filename`, `page`, `lot`, `phase`, and
the underlying chunk text — enough for the frontend to link an answer
straight back to the document and page it came from.

## Persistence

The user's message is saved to Postgres **before** retrieval starts; the
assistant's message is saved **after** streaming completes, together with
its `sources_json`, `structured_json`, and `schema_json`. If retrieval or
generation fails partway, the user message is already committed — the
conversation shows a question with no answer rather than losing the
question.

## Scope, honestly

The early design doc for this system (`docs/architecture-rag.md`) describes
two search modes: project-scoped and a tenant-wide "global" mode for
cross-project questions, plus a cross-encoder re-ranking step on retrieved
chunks. Neither exists in the current implementation — every search is
project-scoped, and ranking is Qdrant's cosine similarity alone, with the
score penalties described above layered on top. Both are the design doc's
intended direction, not yet built.
