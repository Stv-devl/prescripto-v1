"""Search service — semantic search over indexed documents via Qdrant."""

import logging
import uuid
from collections import defaultdict

from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    ScoredPoint,
)

from app.core.config import settings
from app.core.qdrant import qdrant_client
from app.schemas.search import SearchFilters, SearchResult
from app.services.ingestion.embedding import COLLECTION_NAME, embed_texts
from app.services.sparse import query_sparse_vector

logger = logging.getLogger(__name__)

# ── Document type deduplication ──
_VERSIONED_TYPES = frozenset(
    {
        "etude_thermique",
        "cctp",
        "dpgf",
        "etude_sol",
        "rapport_amiante",
    }
)

# ── Diagnostic document de-prioritization ──

_DIAGNOSTIC_TYPES = frozenset({"rapport_amiante", "etude_sol", "etude_thermique"})
_DIAGNOSTIC_PENALTY = 0.85

_DIAGNOSTIC_QUERY_TERMS: dict[str, set[str]] = {
    "rapport_amiante": {"amiante", "désamiantage", "diagnostic", "repérage", "dta"},
    "etude_sol": {"sol", "géotechnique", "géotech", "sondage", "fondation", "g1", "g2"},
    "etude_thermique": {"thermique", "rt2012", "re2020", "déperdition", "bbio", "cep"},
}


def _dedup_by_latest_version(
    hits: list[object],
) -> list[object]:
    """Filter hits to keep only the most recently ingested document per versioned type.

    For document types in _VERSIONED_TYPES, groups hits by type and keeps only
    those belonging to the document with the latest `ingested_at` payload field.
    Hits without `ingested_at` or with non-versioned types pass through unchanged.
    """
    type_doc_dates: dict[str, dict[str, str]] = defaultdict(dict)
    for hit in hits:
        payload = hit.payload or {}
        doc_type = payload.get("type", "")
        if doc_type not in _VERSIONED_TYPES:
            continue
        doc_id = payload.get("document_id", "")
        ingested_at = payload.get("ingested_at", "")
        if doc_id and ingested_at:
            existing = type_doc_dates[doc_type].get(doc_id, "")
            if ingested_at > existing:
                type_doc_dates[doc_type][doc_id] = ingested_at

    newest_doc_per_type: dict[str, str] = {}
    for doc_type, doc_dates in type_doc_dates.items():
        if len(doc_dates) <= 1:
            continue
        newest_doc_id = max(doc_dates, key=lambda d: doc_dates[d])
        newest_doc_per_type[doc_type] = newest_doc_id

    if not newest_doc_per_type:
        return hits

    filtered: list[object] = []
    superseded: set[str] = set()
    for hit in hits:
        payload = hit.payload or {}
        doc_type = payload.get("type", "")
        if doc_type in newest_doc_per_type:
            doc_id = payload.get("document_id", "")
            if doc_id != newest_doc_per_type[doc_type]:
                superseded.add(str(doc_id))
                continue
        filtered.append(hit)

    skipped = len(hits) - len(filtered)
    if skipped > 0:
        logger.warning(
            "[SEARCH] Dedup: skipped %d chunks from superseded documents %s (types: %s)",
            skipped,
            sorted(superseded),
            list(newest_doc_per_type.keys()),
        )

    return filtered


def _should_penalize(doc_type: str, query: str) -> bool:
    """Return True if a diagnostic chunk should be penalized for this query."""
    if doc_type not in _DIAGNOSTIC_TYPES:
        return False
    terms = _DIAGNOSTIC_QUERY_TERMS.get(doc_type, set())
    query_lower = query.lower()
    return not any(term in query_lower for term in terms)


def context_score_threshold(base: float) -> float:
    """Cutoff applied to `SearchResult.score` when building the chat context.

    The baseline cutoffs (0.30 / 0.40) are cosine scores. In `v1` a hit carries a
    fused RRF score (`1.0` at best, `0.5` when only one branch ranked it first),
    so the cosine cutoff would drop hits for the wrong reason: `limit` bounds the
    context instead.
    """
    return 0.0 if settings.retrieval_mode == "v1" else base


async def _ranked_hits(
    *,
    query_vector: list[float],
    query_text: str,
    query_filter: Filter,
    limit: int,
    score_threshold: float,
) -> list[ScoredPoint]:
    """Dense search in `baseline`; dense + BM25 fused by RRF in `v1`.

    The tenant filter is written on **both** prefetch branches and again on the
    fused query: a prefetch without it would spend its `limit` on other tenants'
    points. `score_threshold` keeps the baseline meaning — it only admits dense
    candidates the baseline would have admitted; the sparse branch has none.
    """
    if settings.retrieval_mode != "v1":
        return await qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

    branches = [
        Prefetch(
            query=query_vector,
            using="dense",
            filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
    ]
    sparse_query = query_sparse_vector(query_text)
    if sparse_query is not None:
        branches.append(
            Prefetch(query=sparse_query, using="sparse", filter=query_filter, limit=limit)
        )
    response = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=branches,
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=query_filter,
        limit=limit,
    )
    return response.points


async def search_documents(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    filters: SearchFilters,
    limit: int = 5,
) -> list[SearchResult]:
    """Search indexed documents in Qdrant using semantic similarity.

    Embeds the query via Mistral Embed, then searches the Qdrant collection
    with tenant/project isolation and optional lot/phase/type filters.
    """
    vectors = await embed_texts([query])
    query_vector = vectors[0]

    must_conditions: list[FieldCondition] = [
        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
    ]

    if filters.lot:
        must_conditions.append(FieldCondition(key="lot", match=MatchValue(value=filters.lot)))
    if filters.phase:
        must_conditions.append(FieldCondition(key="phase", match=MatchValue(value=filters.phase)))
    if filters.type:
        must_conditions.append(FieldCondition(key="type", match=MatchValue(value=filters.type)))

    fetch_limit = limit * 3
    hits = await _ranked_hits(
        query_vector=query_vector,
        query_text=query,
        query_filter=Filter(must=must_conditions),
        limit=fetch_limit,
        score_threshold=0.55,
    )

    if not hits:
        hits = await _ranked_hits(
            query_vector=query_vector,
            query_text=query,
            query_filter=Filter(must=must_conditions),
            limit=max(fetch_limit, 20),
            score_threshold=0.35,
        )

    hits = _dedup_by_latest_version(hits)

    logger.debug(
        f"[SEARCH DEBUG] query='{query}' | hits={len(hits)} | "
        f"scores={[round(h.score, 3) for h in hits]}"
    )

    results: list[SearchResult] = []
    for hit in hits:
        payload = hit.payload or {}
        doc_type = payload.get("type", "")
        content_type = payload.get("content_type", "mixed")
        score = hit.score
        if _should_penalize(doc_type, query):
            score *= _DIAGNOSTIC_PENALTY
        if content_type == "admin":
            score *= 0.80
        results.append(
            SearchResult(
                text=payload.get("text", ""),
                page=payload.get("page", 0),
                position=payload.get("position", 0),
                filename=payload.get("filename", ""),
                document_id=uuid.UUID(payload["document_id"]),
                project_id=uuid.UUID(payload["project_id"]),
                score=score,
                lot=payload.get("lot", ""),
                phase=payload.get("phase", ""),
                type=doc_type,
                heading_prefix=payload.get("heading_prefix"),
                section_title=payload.get("section_title"),
                parent_sections=payload.get("parent_sections", []),
                content_type=payload.get("content_type"),
                keywords=payload.get("keywords", []),
                localisation=payload.get("localisation", []),
                char_count=payload.get("char_count", len(payload.get("text", ""))),
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


async def search_diverse(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    limit: int = 20,
    per_document: int = 2,
) -> list[SearchResult]:
    """Search with diversity: return top chunks per document, not just globally.

    Fetches a large pool of candidates, then picks the best `per_document`
    chunks from each unique document to ensure broad coverage across all
    project documents. Useful for broad questions (summaries, enumerations).
    """
    vectors = await embed_texts([query])
    query_vector = vectors[0]

    must_conditions: list[FieldCondition] = [
        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
    ]

    hits = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=100,
        score_threshold=0.35,
    )

    hits = _dedup_by_latest_version(hits)

    logger.debug(
        f"[SEARCH DEBUG diverse] query='{query}' | pool={len(hits)} | "
        f"top_scores={[round(h.score, 3) for h in hits[:5]]}"
    )

    doc_buckets: dict[str, list[SearchResult]] = {}
    for hit in hits:
        payload = hit.payload or {}
        doc_id = payload.get("document_id", "")
        bucket = doc_buckets.setdefault(doc_id, [])
        if len(bucket) >= per_document:
            continue
        doc_type = payload.get("type", "")
        content_type = payload.get("content_type", "mixed")
        score = hit.score
        if _should_penalize(doc_type, query):
            score *= _DIAGNOSTIC_PENALTY
        if content_type == "admin":
            score *= 0.80
        bucket.append(
            SearchResult(
                text=payload.get("text", ""),
                page=payload.get("page", 0),
                position=payload.get("position", 0),
                filename=payload.get("filename", ""),
                document_id=uuid.UUID(doc_id),
                project_id=uuid.UUID(payload["project_id"]),
                score=score,
                lot=payload.get("lot", ""),
                phase=payload.get("phase", ""),
                type=doc_type,
                heading_prefix=payload.get("heading_prefix"),
                section_title=payload.get("section_title"),
                parent_sections=payload.get("parent_sections", []),
                content_type=payload.get("content_type"),
                keywords=payload.get("keywords", []),
                localisation=payload.get("localisation", []),
                char_count=payload.get("char_count", len(payload.get("text", ""))),
            )
        )

    results: list[SearchResult] = []
    for bucket in doc_buckets.values():
        results.extend(bucket)
    results.sort(key=lambda r: r.score, reverse=True)

    return results[:limit]


async def search_by_lot(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    extra_queries: list[str] | None = None,
    scroll_per_lot: int = 5,
    semantic_per_lot: int = 8,
    semantic_pool: int = 250,
) -> list[SearchResult]:
    """Hybrid search for broad queries: scroll-based coverage + semantic relevance.

    1. Scroll: fetches all distinct lots, gets first chunks by position per lot
       (no embedding cost — guarantees coverage of every lot).
    2. Semantic: one embedding search, grouped by lot, picks best semantic matches
       (captures cross-lot docs like bilan thermique + relevant chunks).
    3. Merge & deduplicate by Qdrant point ID.
    """
    content_priority = {
        "description": 0,
        "specification": 1,
        "mixed": 2,
        "heading": 3,
        "quantity": 4,
        "admin": 5,
    }

    base_filter = Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
            FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
        ]
    )

    # ── Step 1: Discover all distinct lots via scroll ──
    all_records = []
    next_offset = None
    while True:
        records, next_offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=base_filter,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        all_records.extend(records)
        if next_offset is None:
            break

    all_records = _dedup_by_latest_version(all_records)

    lot_records: dict[str, list[tuple[int, str, object]]] = {}
    for record in all_records:
        payload = record.payload or {}
        lot = payload.get("lot", "") or "unknown"
        position = payload.get("position", 0)
        content_type = payload.get("content_type", "mixed")
        priority = content_priority.get(content_type, 2)
        lot_records.setdefault(lot, []).append((position, priority, record))

    scroll_point_ids: set[str] = set()
    scroll_results: list[SearchResult] = []
    for lot in sorted(lot_records.keys()):
        candidates = lot_records[lot]
        candidates.sort(key=lambda x: (x[1], x[0]))
        picked = 0
        for _, priority, record in candidates:
            if picked >= scroll_per_lot:
                break
            if priority >= 3:
                continue
            payload = record.payload or {}
            point_id = str(record.id)
            scroll_point_ids.add(point_id)
            scroll_results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    page=payload.get("page", 0),
                    position=payload.get("position", 0),
                    filename=payload.get("filename", ""),
                    document_id=uuid.UUID(payload["document_id"]),
                    project_id=uuid.UUID(payload["project_id"]),
                    score=0.5,
                    lot=lot,
                    phase=payload.get("phase", ""),
                    type=payload.get("type", ""),
                    heading_prefix=payload.get("heading_prefix"),
                    section_title=payload.get("section_title"),
                    parent_sections=payload.get("parent_sections", []),
                    content_type=payload.get("content_type"),
                    keywords=payload.get("keywords", []),
                    localisation=payload.get("localisation", []),
                    char_count=payload.get("char_count", len(payload.get("text", ""))),
                )
            )
            picked += 1

    logger.debug(
        f"[SEARCH DEBUG by_lot scroll] lots={list(sorted(lot_records.keys()))} | "
        f"scroll_results={len(scroll_results)}"
    )

    # ── Step 2: Semantic search for relevance ──
    all_queries = [query]
    if extra_queries:
        all_queries.extend(extra_queries)

    vectors = await embed_texts(all_queries)
    seen_point_ids: set[str] = set(scroll_point_ids)
    hits: list[object] = []

    for query_index, qvec in enumerate(vectors):
        q_hits = await _ranked_hits(
            query_vector=qvec,
            query_text=all_queries[query_index],
            query_filter=base_filter,
            limit=semantic_pool,
            score_threshold=0.30,
        )
        q_hits = _dedup_by_latest_version(q_hits)
        for h in q_hits:
            pid = str(h.id)
            if pid not in seen_point_ids:
                seen_point_ids.add(pid)
                hits.append(h)

    logger.debug(
        f"[SEARCH DEBUG by_lot semantic] queries={len(all_queries)} | "
        f"pool={len(hits)} | "
        f"top_scores={[round(h.score, 3) for h in hits[:5]]}"
    )

    sem_buckets: dict[str, list[tuple[int, float, str, SearchResult]]] = {}
    for hit in hits:
        point_id = str(hit.id)
        if point_id in scroll_point_ids:
            continue
        payload = hit.payload or {}
        lot = payload.get("lot", "") or "unknown"
        content_type = payload.get("content_type", "mixed")
        doc_type = payload.get("type", "")
        priority = content_priority.get(content_type, 2)
        score = hit.score
        if _should_penalize(doc_type, query):
            score *= _DIAGNOSTIC_PENALTY
        result = SearchResult(
            text=payload.get("text", ""),
            page=payload.get("page", 0),
            position=payload.get("position", 0),
            filename=payload.get("filename", ""),
            document_id=uuid.UUID(payload["document_id"]),
            project_id=uuid.UUID(payload["project_id"]),
            score=score,
            lot=lot,
            phase=payload.get("phase", ""),
            type=doc_type,
            heading_prefix=payload.get("heading_prefix"),
            section_title=payload.get("section_title"),
            parent_sections=payload.get("parent_sections", []),
            content_type=content_type,
            keywords=payload.get("keywords", []),
            localisation=payload.get("localisation", []),
            char_count=payload.get("char_count", len(payload.get("text", ""))),
        )
        sem_buckets.setdefault(lot, []).append((priority, -score, point_id, result))

    semantic_results: list[SearchResult] = []
    for lot in sorted(sem_buckets.keys()):
        bucket = sem_buckets[lot]
        bucket.sort(key=lambda x: (x[0], x[1]))
        for _, _, _, result in bucket[:semantic_per_lot]:
            semantic_results.append(result)

    logger.debug(
        f"[SEARCH DEBUG by_lot semantic] sem_lots={list(sorted(sem_buckets.keys()))} | "
        f"sem_results={len(semantic_results)}"
    )

    # ── Step 3: Merge scroll (coverage) + semantic (relevance) ──
    merged = scroll_results + semantic_results

    logger.debug(
        f"[SEARCH DEBUG by_lot] total_merged={len(merged)} "
        f"(scroll={len(scroll_results)} + semantic={len(semantic_results)})"
    )

    return merged


async def search_merged(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    queries: list[str],
    filters: SearchFilters,
    limit: int = 12,
    score_threshold: float = 0.40,
) -> list[SearchResult]:
    """Run multiple semantic searches and merge results, deduplicated by Qdrant point ID.

    Embeds all queries in a single Mistral API call, runs one Qdrant search per
    query vector, then deduplicates by point ID keeping the highest score.
    Useful when a single rewritten query misses chunks that the original phrasing
    would have matched.
    """
    if not queries:
        return []

    vectors_list = await embed_texts(queries)

    must_conditions: list[FieldCondition] = [
        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
    ]

    if filters.lot:
        must_conditions.append(FieldCondition(key="lot", match=MatchValue(value=filters.lot)))
    if filters.phase:
        must_conditions.append(FieldCondition(key="phase", match=MatchValue(value=filters.phase)))
    if filters.type:
        must_conditions.append(FieldCondition(key="type", match=MatchValue(value=filters.type)))

    qfilter = Filter(must=must_conditions)

    best_hits: dict[str, tuple[float, object]] = {}
    query_best: list[tuple[str, float, object] | None] = [None] * len(vectors_list)

    for i, vector in enumerate(vectors_list):
        hits = await _ranked_hits(
            query_vector=vector,
            query_text=queries[i],
            query_filter=qfilter,
            limit=limit * 3,
            score_threshold=score_threshold,
        )
        hits = _dedup_by_latest_version(hits)
        for hit in hits:
            point_id = str(hit.id)
            if point_id not in best_hits or hit.score > best_hits[point_id][0]:
                best_hits[point_id] = (hit.score, hit)
            if query_best[i] is None or hit.score > query_best[i][1]:
                query_best[i] = (point_id, hit.score, hit)

        logger.debug(
            f"[SEARCH DEBUG merged] query[{i}]='{queries[i][:80]}' | "
            f"hits={len(hits)} | scores={[round(h.score, 3) for h in hits]}"
        )

    if not best_hits:
        for i, vector in enumerate(vectors_list):
            hits = await _ranked_hits(
                query_vector=vector,
                query_text=queries[i],
                query_filter=qfilter,
                limit=max(limit * 3, 20),
                score_threshold=0.35,
            )
            hits = _dedup_by_latest_version(hits)
            for hit in hits:
                point_id = str(hit.id)
                if point_id not in best_hits or hit.score > best_hits[point_id][0]:
                    best_hits[point_id] = (hit.score, hit)
                if query_best[i] is None or hit.score > query_best[i][1]:
                    query_best[i] = (point_id, hit.score, hit)

    reserved_ids: set[str] = set()
    reserved: list[tuple[float, object]] = []
    for qb in query_best:
        if qb is not None:
            pid, score, hit = qb
            if pid not in reserved_ids:
                reserved_ids.add(pid)
                reserved.append((score, hit))

    remaining = [(s, h) for pid, (s, h) in best_hits.items() if pid not in reserved_ids]
    remaining.sort(key=lambda x: x[0], reverse=True)

    reserved.sort(key=lambda x: x[0], reverse=True)
    deduped = reserved + remaining
    deduped = deduped[:limit]

    logger.debug(
        f"[SEARCH DEBUG merged] total deduped={len(deduped)} "
        f"(reserved={len(reserved)}) | "
        f"scores={[round(s, 3) for s, _ in deduped]}"
    )

    primary_query = queries[0] if queries else ""

    results: list[SearchResult] = []
    for _, hit in deduped:
        payload = hit.payload or {}
        doc_type = payload.get("type", "")
        content_type = payload.get("content_type", "mixed")
        score = hit.score
        if _should_penalize(doc_type, primary_query):
            score *= _DIAGNOSTIC_PENALTY
        if content_type == "admin":
            score *= 0.80
        results.append(
            SearchResult(
                text=payload.get("text", ""),
                page=payload.get("page", 0),
                position=payload.get("position", 0),
                filename=payload.get("filename", ""),
                document_id=uuid.UUID(payload["document_id"]),
                project_id=uuid.UUID(payload["project_id"]),
                score=score,
                lot=payload.get("lot", ""),
                phase=payload.get("phase", ""),
                type=doc_type,
                heading_prefix=payload.get("heading_prefix"),
                section_title=payload.get("section_title"),
                parent_sections=payload.get("parent_sections", []),
                content_type=payload.get("content_type"),
                keywords=payload.get("keywords", []),
                localisation=payload.get("localisation", []),
                char_count=payload.get("char_count", len(payload.get("text", ""))),
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ── Admin helpers (Qdrant access for admin service) ──


async def retrieve_point_payload(point_id: str, tenant_id: uuid.UUID) -> dict[str, object] | None:
    """Retrieve the full Qdrant payload for a single point, scoped to the tenant.

    Qdrant's `retrieve` takes IDs, not a filter, so the isolation check happens on
    the returned payload: a point owned by another tenant is reported as missing.
    """
    results = await qdrant_client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
        with_vectors=False,
    )
    if not results:
        return None

    payload = results[0].payload or {}
    if payload.get("tenant_id") != str(tenant_id):
        logger.warning(
            "[SEARCH] Point %s requested by tenant %s belongs to another tenant",
            point_id,
            tenant_id,
        )
        return None
    return payload


async def count_document_points(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> int:
    """Count the number of Qdrant points for a given document."""
    result = await qdrant_client.count(
        collection_name=COLLECTION_NAME,
        count_filter=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
            ]
        ),
        exact=True,
    )
    return result.count


async def scroll_document_point_ids(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> set[str]:
    """Scroll all Qdrant point IDs for a given document."""
    point_ids: set[str] = set()
    offset = None
    doc_filter = Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
            FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
        ]
    )
    while True:
        records, next_offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=doc_filter,
            limit=100,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for record in records:
            point_ids.add(str(record.id))
        if next_offset is None:
            break
        offset = next_offset
    return point_ids
