"""Embedding with Mistral Embed and indexing in Qdrant."""

import asyncio
import logging
import uuid
from datetime import datetime

from qdrant_client.models import (
    Distance,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import settings
from app.core.mistral import mistral_client
from app.core.qdrant import qdrant_client
from app.services.ingestion.chunking import TextChunk
from app.services.qdrant_payload import ChunkPayloadFields, build_chunk_payload

logger = logging.getLogger(__name__)


def collection_name_for(retrieval_mode: str) -> str:
    """Resolve the Qdrant collection name for a retrieval mode."""
    return "documents" if retrieval_mode == "baseline" else f"documents_{retrieval_mode}"


COLLECTION_NAME = collection_name_for(settings.retrieval_mode)
EMBEDDING_MODEL = "mistral-embed"
VECTOR_SIZE = 1024
BATCH_SIZE = 10

INDEXED_PAYLOAD_FIELDS = (
    "tenant_id",
    "project_id",
    "type",
    "lot",
    "phase",
    "content_type",
    "document_id",
    "filename",
)

_EMBED_MAX_RETRIES = 3
_EMBED_RETRY_BASE_DELAY = 1.0


async def ensure_collection() -> None:
    """Create the Qdrant collection if it doesn't exist, and ensure its payload indexes.

    Runs on every app startup, so both steps must tolerate being re-run: the
    collection-existence check already did. `create_payload_index` needs no
    such guard of its own — verified against a real `qdrant:v1.13.2` server
    (this repo's pin), a repeat call for a field already indexed answers
    `200 {"status":"ok",...}`, not an error, on both an empty collection and
    one with 20k points. So a pre-existing collection missing the index gets
    it, and one that already has it is a no-op on the next startup.
    """
    collections = await qdrant_client.get_collections()
    existing = [c.name for c in collections.collections]
    if COLLECTION_NAME not in existing:
        dense = VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        if settings.retrieval_mode == "v1":
            await qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={"dense": dense},
                sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
            )
        else:
            await qdrant_client.create_collection(
                collection_name=COLLECTION_NAME, vectors_config=dense
            )
        logger.info("Created Qdrant collection '%s'", COLLECTION_NAME)

    for field_name in INDEXED_PAYLOAD_FIELDS:
        await _ensure_payload_index(field_name)


async def _ensure_payload_index(field_name: str) -> None:
    """Create a keyword payload index on `field_name`.

    Every field in `INDEXED_PAYLOAD_FIELDS` — UUID strings (`tenant_id`,
    `project_id`, `document_id`) and plain strings (`type`, `lot`, `phase`,
    `content_type`, `filename`) alike — is matched everywhere with
    `MatchValue`, so a keyword index serves every existing filter with no
    query change. No try/except here: real Qdrant is
    already idempotent for this call, and any error it does raise here — auth
    rejected, a malformed field name, the server unreachable — is a genuine
    startup failure that must propagate, not be silently swallowed into an
    unindexed collection.
    """
    await qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name=field_name,
        field_schema=PayloadSchemaType.KEYWORD,
    )


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Mistral Embed (with retry on transient errors)."""
    last_exc: Exception | None = None
    for attempt in range(_EMBED_MAX_RETRIES):
        try:
            response = await mistral_client.embeddings.create_async(
                model=EMBEDDING_MODEL,
                inputs=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            last_exc = exc
            err_msg = str(exc)
            is_transient = "503" in err_msg or "429" in err_msg or "timeout" in err_msg.lower()
            if not is_transient or attempt == _EMBED_MAX_RETRIES - 1:
                raise
            delay = _EMBED_RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "Mistral embed transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                _EMBED_MAX_RETRIES,
                delay,
                err_msg,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def index_chunks(
    chunks: list[TextChunk],
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
    lot: str,
    phase: str,
    filename: str,
    ingested_at: datetime | None = None,
) -> list[str]:
    """Embed chunks and store them in Qdrant. Returns list of qdrant point IDs."""
    await ensure_collection()

    point_ids: list[str] = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [f"{c.heading_prefix}\n\n{c.text}" if c.heading_prefix else c.text for c in batch]
        vectors = await embed_texts(texts)

        points: list[PointStruct] = []

        for chunk, vector in zip(batch, vectors, strict=True):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)

            payload = build_chunk_payload(
                ChunkPayloadFields(
                    text=chunk.text,
                    page=chunk.page,
                    position=chunk.position,
                    parent_sections=chunk.parent_sections,
                    section_title=chunk.section_title,
                    heading_prefix=chunk.heading_prefix,
                    content_type=chunk.content_type,
                    keywords=chunk.keywords,
                    localisation=chunk.localisation,
                    char_count=chunk.char_count,
                    lot=chunk.chunk_lot,
                ),
                tenant_id=tenant_id,
                project_id=project_id,
                document_id=document_id,
                doc_type=doc_type,
                filename=filename,
                phase=phase,
                document_lot=lot,
                ingested_at=ingested_at,
            )

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        await qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

    return point_ids


async def delete_document_vectors(document_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Delete all vectors of a document, scoped to its tenant.

    The tenant condition is not redundant: a delete without it would remove points
    on a document_id collision or a mistaken id, across tenants, with no error.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    await qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
            ]
        ),
    )
