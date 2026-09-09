# Data model

PostgreSQL 16, SQLAlchemy 2.0 async, Alembic migrations (`backend/alembic/`,
11 revisions as of this writing). `TenantMixin` adds an indexed, cascading
`tenant_id` FK; `TimestampMixin` adds `created_at`/`updated_at` with
server-side defaults.

## Entities

| Entity | Table | Tenant-scoped directly? | Notable columns |
| --- | --- | --- | --- |
| Tenant | `tenants` | — | `name`, `plan` |
| User | `users` | yes (`TenantMixin`) | `email` (unique), `hashed_password`, `role`, `token_version` |
| Project | `projects` | yes (`TenantMixin`) | `name`, `phase`, `status`, `address`, `client`, `architect`, `is_favorite` |
| Folder | `folders` | no — via `project_id` | `name`, `lot`, `phase` |
| Document | `documents` | no — via `project_id` | `filename`, `type`, `lot`, `phase`, `status`, `chunk_count`, `ingested_at` |
| Chunk | `chunks` | no — via `document_id` | text, page, position, `qdrant_point_id`, keywords, section metadata |
| ProjectSummary | `project_summaries` | no — via `project_id` (unique) | `status`, `data_json`, `error_message`, `generated_at` |
| Conversation | `conversations` | no — via `project_id` | `title` |
| Message | `messages` | no — via `conversation_id` | `role`, `content`, `sources_json`, `structured_json`, `schema_json` |

## Relationships

```
tenant 1──N user
tenant 1──N project
project 1──N folder
project 1──N document
project 1──N conversation
project 1──1 project_summary
folder  1──N document
document 1──N chunk
user 1──N conversation
conversation 1──N message
```

All FKs cascade on delete (`ondelete="CASCADE"`) except `Document.folder_id`,
which is `SET NULL` — deleting a folder doesn't delete the documents inside
it, it just un-files them.

## Isolation: direct vs. inherited

Only `User` and `Project` carry `tenant_id` directly. Everything below
`Project` — folders, documents, chunks, conversations, messages — is
isolated **transitively**, through the FK chain back to a tenant-scoped
project, rather than by a `tenant_id` column of their own. In practice this
means a service reaching for `Document` has to join through `Project` to
filter by tenant (see the `Folder`/`Document` example in
[`auth-and-tenancy.md`](./auth-and-tenancy.md)) — there's no defensive,
single-column `WHERE tenant_id = ...` available at that level.

`06-database.md`'s convention of a composite `(tenant_id, <frequent filter>)`
index is not implemented anywhere in the current schema — only single-column
indexes exist on FK and unique columns. Every tenant-scoped query today
resolves through a join rather than an index built for the filter shape it
actually runs.

## Project summaries

`ProjectSummary` (`backend/app/models/summary.py`) holds one generated
technical summary per project (`project_id` is unique — one row, overwritten
on regeneration), with `status` moving through
`generating → done | partial | error`. The generated content itself is
stored as `data_json`, a serialized:

```python
ProjectSummaryData(
    description: str,                          # ~4 paragraphs, LLM-written
    systeme_constructif: list[SystemeConstructifItem],  # label, description, kpis, details
    contraintes: list[ContrainteItem],                  # label, kpis, details
)
```

### How a summary gets generated

`backend/app/services/summary.py` runs 16 section-specific searches (9
"système constructif" sections, 7 "contraintes"), each with its own
pre-written set of embedding queries and its own Mistral extraction prompt:

1. Embed each section's search queries, run them against Qdrant
   (`tenant_id` + `project_id` filters, optional doc-type filter/exclusion).
2. Rank and accumulate matching chunks into a context budget that scales
   with corpus size (30k–60k characters).
3. Call `mistral-large-latest` (temperature 0, JSON mode) per section to
   extract `{description, kpis[], details[]}`.
4. Once every section is done, generate a 4-paragraph overview from the
   section results (temperature 0.1).
5. Persist the assembled `ProjectSummaryData` and stream progress over SSE
   as each section completes.

`GET /projects/{id}/summary/status` and `GET /projects/{id}/summary` read
the cached result; `POST /projects/{id}/summary/generate` is the SSE
endpoint that runs the pipeline above. All three require
`Depends(get_current_user)` and filter by `tenant_id`.
