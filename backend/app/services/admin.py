"""Admin service — chunk inspection, statistics, and sync checking."""

import asyncio
import logging
import math
import time
import uuid

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    OverwritePayloadOperation,
    PointStruct,
    SetPayload,
    SetPayloadOperation,
    UpdateOperation,
)
from sqlalchemy import String, case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import ConflictError, NotFoundError
from app.core.qdrant import qdrant_client
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.project import Project
from app.schemas.admin import (
    AdjacentChunk,
    BatchEnrichResponse,
    ChunkDetail,
    ChunkListItem,
    ChunkMutationResponse,
    ChunkStatsResponse,
    DocumentStats,
    DuplicatePair,
    DuplicateResponse,
    PaginatedChunks,
    PaginatedSyncDocuments,
    PlaygroundSearchResponse,
    PlaygroundSearchResult,
    QualityAlerts,
    RechunkResponse,
    RepairPayloadsResponse,
    SectionNode,
    SimilarChunkResult,
    SyncCheckResponse,
    SyncDocumentItem,
)
from app.services.ingestion.chunking import _extract_keywords, _extract_localisation
from app.services.ingestion.embedding import (
    COLLECTION_NAME,
    delete_document_vectors,
    embed_texts,
)
from app.services.qdrant_payload import ChunkPayloadFields, build_chunk_payload
from app.services.search import (
    count_document_points,
    retrieve_point_payload,
    scroll_document_point_ids,
)

logger = logging.getLogger(__name__)


def compute_quality_score(
    char_count: int | None,
    content_type: str | None,
    keywords: list[str] | None,
    section_title: str | None,
    localisation: list[str] | None = None,
) -> float:
    """Compute a quality score (0.0–1.0) for a chunk based on its metadata.

    Scoring:
    - char_count: 0.4 weight — ideal range 200–2000, penalise <100 or >2500
    - keywords: 0.2 weight — bonus if present (up to 10)
    - content_type: 0.2 weight — penalise heading-only
    - section_title: 0.1 weight — bonus if present
    - localisation: 0.1 weight — bonus if spatial context present
    """
    score = 0.0
    chars = char_count or 0

    if 200 <= chars <= 2000:
        score += 0.4
    elif 100 <= chars < 200 or 2000 < chars <= 2500:
        score += 0.2
    elif chars < 100 or chars > 2500:
        score += 0.0

    if keywords and len(keywords) > 0:
        score += min(0.2, 0.02 * len(keywords))

    ct_scores = {
        "specification": 0.2,
        "description": 0.2,
        "mixed": 0.15,
        "quantity": 0.1,
        "admin": 0.1,
        "heading": 0.0,
    }
    score += ct_scores.get(content_type or "", 0.1)

    if section_title:
        score += 0.1

    if localisation and len(localisation) > 0:
        score += 0.1

    return round(min(score, 1.0), 2)


def _verify_tenant_filter(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[ColumnElement[bool]]:
    """Return base WHERE conditions for tenant-isolated project queries."""
    return [
        Document.project_id == project_id,
        Project.id == project_id,
        Project.tenant_id == tenant_id,
    ]


async def list_chunks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    page: int = 1,
    per_page: int = 50,
    document_id: uuid.UUID | None = None,
    lot: str | None = None,
    doc_type: str | None = None,
    content_type: str | None = None,
    min_chars: int | None = None,
    max_chars: int | None = None,
    has_keywords: bool | None = None,
    search: str | None = None,
    orphan: bool | None = None,
    parent_section: str | None = None,
    sort_by: str = "position",
    sort_order: str = "asc",
) -> PaginatedChunks:
    """List chunks with filters, pagination, and sorting."""
    base_conditions = _verify_tenant_filter(tenant_id, project_id)
    conditions = list(base_conditions)

    if document_id:
        conditions.append(Chunk.document_id == document_id)
    if lot:
        conditions.append(Document.lot == lot)
    if doc_type:
        conditions.append(Document.type == doc_type)
    if content_type:
        conditions.append(Chunk.content_type == content_type)
    if min_chars is not None:
        conditions.append(Chunk.char_count >= min_chars)
    if max_chars is not None:
        conditions.append(Chunk.char_count <= max_chars)
    if has_keywords is True:
        conditions.append(Chunk.keywords.isnot(None))
    elif has_keywords is False:
        conditions.append(or_(Chunk.keywords.is_(None), Chunk.keywords.cast(String) == "[]"))
    if search:
        conditions.append(Chunk.text.ilike(f"%{search}%"))
    if orphan is True:
        conditions.append(or_(Chunk.qdrant_point_id.is_(None), Chunk.qdrant_point_id == ""))
    if parent_section:
        conditions.append(Chunk.parent_sections.cast(String).ilike(f"%{parent_section}%"))

    sort_columns = {
        "position": Chunk.position,
        "page": Chunk.page,
        "char_count": Chunk.char_count,
        "created_at": Chunk.created_at,
    }
    sort_col = sort_columns.get(sort_by, Chunk.position)
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    count_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*conditions)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.text,
            Chunk.page,
            Chunk.position,
            Chunk.char_count,
            Chunk.content_type,
            Chunk.keywords,
            Chunk.section_title,
            Chunk.parent_sections,
            Chunk.localisation,
            Document.lot,
            Document.phase,
            Document.type,
            Chunk.qdrant_point_id,
            Chunk.created_at,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*conditions)
        .order_by(order)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()

    items = [
        ChunkListItem(
            id=row.id,
            document_id=row.document_id,
            filename=row.filename,
            text_preview=row.text[:150] if row.text else "",
            page=row.page,
            position=row.position,
            char_count=row.char_count,
            content_type=row.content_type,
            keywords=row.keywords,
            section_title=row.section_title,
            parent_sections=row.parent_sections,
            localisation=row.localisation,
            lot=row.lot,
            phase=row.phase,
            type=row.type,
            qdrant_point_id=row.qdrant_point_id,
            created_at=row.created_at,
            quality_score=compute_quality_score(
                row.char_count,
                row.content_type,
                row.keywords,
                row.section_title,
                row.localisation,
            ),
        )
        for row in rows
    ]

    return PaginatedChunks(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if total > 0 else 0,
    )


async def get_chunk_stats(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ChunkStatsResponse:
    """Compute chunk statistics for a project."""
    base_conditions = _verify_tenant_filter(tenant_id, project_id)
    base_join = (
        select(Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
    )

    total_stmt = select(func.count()).select_from(base_join.subquery())
    total_chunks = (await db.execute(total_stmt)).scalar_one()

    doc_count_stmt = (
        select(func.count(func.distinct(Chunk.document_id)))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
    )
    total_documents = (await db.execute(doc_count_stmt)).scalar_one()

    by_doc_stmt = (
        select(
            Chunk.document_id,
            Document.filename,
            Document.type,
            Document.lot,
            func.count(Chunk.id).label("chunk_count"),
            func.avg(Chunk.char_count).label("avg_char_count"),
            func.min(Chunk.char_count).label("min_char_count"),
            func.max(Chunk.char_count).label("max_char_count"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
        .group_by(Chunk.document_id, Document.filename, Document.type, Document.lot)
    )
    by_doc_rows = (await db.execute(by_doc_stmt)).all()
    by_document = [
        DocumentStats(
            document_id=row.document_id,
            filename=row.filename,
            type=row.type,
            lot=row.lot,
            chunk_count=row.chunk_count,
            avg_char_count=round(float(row.avg_char_count or 0), 1),
            min_char_count=row.min_char_count or 0,
            max_char_count=row.max_char_count or 0,
        )
        for row in by_doc_rows
    ]

    ct_stmt = (
        select(Chunk.content_type, func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
        .group_by(Chunk.content_type)
    )
    ct_rows = (await db.execute(ct_stmt)).all()
    by_content_type = {row[0] or "unknown": row[1] for row in ct_rows}

    lot_stmt = (
        select(Document.lot, func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
        .group_by(Document.lot)
    )
    lot_rows = (await db.execute(lot_stmt)).all()
    by_lot = {row[0] or "unknown": row[1] for row in lot_rows}

    type_stmt = (
        select(Document.type, func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
        .group_by(Document.type)
    )
    type_rows = (await db.execute(type_stmt)).all()
    by_type = {row[0] or "unknown": row[1] for row in type_rows}

    size_stmt = (
        select(
            func.sum(case((Chunk.char_count < 100, 1), else_=0)).label("tiny_lt_100"),
            func.sum(
                case(
                    (
                        (Chunk.char_count >= 100) & (Chunk.char_count < 500),
                        1,
                    ),
                    else_=0,
                )
            ).label("small_100_500"),
            func.sum(
                case(
                    (
                        (Chunk.char_count >= 500) & (Chunk.char_count < 1500),
                        1,
                    ),
                    else_=0,
                )
            ).label("medium_500_1500"),
            func.sum(
                case(
                    (
                        (Chunk.char_count >= 1500) & (Chunk.char_count < 2500),
                        1,
                    ),
                    else_=0,
                )
            ).label("large_1500_2500"),
            func.sum(case((Chunk.char_count >= 2500, 1), else_=0)).label("oversized_gt_2500"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
    )
    size_row = (await db.execute(size_stmt)).one()
    size_distribution = {
        "tiny_lt_100": size_row.tiny_lt_100 or 0,
        "small_100_500": size_row.small_100_500 or 0,
        "medium_500_1500": size_row.medium_500_1500 or 0,
        "large_1500_2500": size_row.large_1500_2500 or 0,
        "oversized_gt_2500": size_row.oversized_gt_2500 or 0,
    }

    no_kw_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions, or_(Chunk.keywords.is_(None), Chunk.keywords.cast(String) == "[]"))
    )
    chunks_without_keywords = (await db.execute(no_kw_stmt)).scalar_one()

    heading_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions, Chunk.content_type == "heading")
    )
    chunks_heading_only = (await db.execute(heading_stmt)).scalar_one()

    short_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions, Chunk.char_count < 100)
    )
    chunks_very_short = (await db.execute(short_stmt)).scalar_one()

    oversized_stmt = (
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions, Chunk.char_count >= 2500)
    )
    chunks_oversized = (await db.execute(oversized_stmt)).scalar_one()

    error_stmt = (
        select(func.count(Document.id))
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
            Document.status == "error",
        )
    )
    documents_with_errors = (await db.execute(error_stmt)).scalar_one()

    sample_stmt = (
        select(
            Chunk.char_count,
            Chunk.content_type,
            Chunk.keywords,
            Chunk.section_title,
            Chunk.localisation,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(*base_conditions)
        .limit(500)
    )
    sample_rows = (await db.execute(sample_stmt)).all()
    if sample_rows:
        scores = [
            compute_quality_score(
                r.char_count,
                r.content_type,
                r.keywords,
                r.section_title,
                r.localisation,
            )
            for r in sample_rows
        ]
        avg_quality = round(sum(scores) / len(scores), 2)
    else:
        avg_quality = 0.0

    return ChunkStatsResponse(
        total_chunks=total_chunks,
        total_documents=total_documents,
        avg_quality_score=avg_quality,
        by_document=by_document,
        by_content_type=by_content_type,
        by_lot=by_lot,
        by_type=by_type,
        size_distribution=size_distribution,
        quality_alerts=QualityAlerts(
            chunks_without_keywords=chunks_without_keywords,
            chunks_heading_only=chunks_heading_only,
            chunks_very_short=chunks_very_short,
            chunks_oversized=chunks_oversized,
            documents_with_errors=documents_with_errors,
        ),
    )


async def get_chunk_detail(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
) -> ChunkDetail:
    """Get full chunk detail including Qdrant payload and adjacent chunks."""
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.text,
            Chunk.page,
            Chunk.position,
            Chunk.char_count,
            Chunk.content_type,
            Chunk.keywords,
            Chunk.section_title,
            Chunk.parent_sections,
            Chunk.localisation,
            Document.lot,
            Document.phase,
            Document.type,
            Chunk.qdrant_point_id,
            Chunk.created_at,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.id == chunk_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundError("Chunk not found")

    qdrant_payload = await retrieve_point_payload(row.qdrant_point_id, tenant_id)

    adj_stmt = (
        select(
            Chunk.id,
            Chunk.position,
            Chunk.page,
            Chunk.text,
            Chunk.content_type,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.document_id == row.document_id,
            Chunk.position.in_([row.position - 1, row.position + 1]),
            Project.tenant_id == tenant_id,
        )
        .order_by(Chunk.position)
    )
    adj_rows = (await db.execute(adj_stmt)).all()
    adjacent_chunks = [
        AdjacentChunk(
            id=adj.id,
            position=adj.position,
            page=adj.page,
            text_preview=adj.text[:150] if adj.text else "",
            content_type=adj.content_type,
        )
        for adj in adj_rows
    ]

    return ChunkDetail(
        id=row.id,
        document_id=row.document_id,
        filename=row.filename,
        text_preview=row.text[:150] if row.text else "",
        text=row.text,
        page=row.page,
        position=row.position,
        char_count=row.char_count,
        content_type=row.content_type,
        keywords=row.keywords,
        section_title=row.section_title,
        parent_sections=row.parent_sections,
        localisation=row.localisation,
        lot=row.lot,
        phase=row.phase,
        type=row.type,
        qdrant_point_id=row.qdrant_point_id,
        created_at=row.created_at,
        qdrant_payload=qdrant_payload,
        adjacent_chunks=adjacent_chunks,
        quality_score=compute_quality_score(
            row.char_count,
            row.content_type,
            row.keywords,
            row.section_title,
            row.localisation,
        ),
    )


async def list_document_chunks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
) -> list[ChunkListItem]:
    """List all chunks of a document ordered by position."""
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.text,
            Chunk.page,
            Chunk.position,
            Chunk.char_count,
            Chunk.content_type,
            Chunk.keywords,
            Chunk.section_title,
            Chunk.parent_sections,
            Chunk.localisation,
            Document.lot,
            Document.phase,
            Document.type,
            Chunk.qdrant_point_id,
            Chunk.created_at,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.document_id == document_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
        .order_by(Chunk.position.asc())
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        doc_check = await db.execute(
            select(Document.id)
            .join(Project, Document.project_id == Project.id)
            .where(
                Document.id == document_id,
                Document.project_id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        if not doc_check.first():
            raise NotFoundError("Document not found")

    return [
        ChunkListItem(
            id=row.id,
            document_id=row.document_id,
            filename=row.filename,
            text_preview=row.text[:150] if row.text else "",
            page=row.page,
            position=row.position,
            char_count=row.char_count,
            content_type=row.content_type,
            keywords=row.keywords,
            section_title=row.section_title,
            parent_sections=row.parent_sections,
            localisation=row.localisation,
            lot=row.lot,
            phase=row.phase,
            type=row.type,
            qdrant_point_id=row.qdrant_point_id,
            created_at=row.created_at,
            quality_score=compute_quality_score(
                row.char_count,
                row.content_type,
                row.keywords,
                row.section_title,
                row.localisation,
            ),
        )
        for row in rows
    ]


async def sync_check(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    page: int = 1,
    per_page: int = 20,
    only_mismatches: bool = False,
) -> SyncCheckResponse:
    """Compare SQL chunk counts vs Qdrant point counts per document."""
    doc_stmt = (
        select(Document.id, Document.filename)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
            Document.status == "ready",
        )
        .order_by(Document.filename)
    )
    all_docs = (await db.execute(doc_stmt)).all()

    sql_counts_stmt = (
        select(Chunk.document_id, func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
        .group_by(Chunk.document_id)
    )
    sql_counts_rows = (await db.execute(sql_counts_stmt)).all()
    sql_counts = {row[0]: row[1] for row in sql_counts_rows}

    total_sql = sum(sql_counts.values())

    all_items: list[SyncDocumentItem] = []
    total_qdrant = 0

    for doc in all_docs:
        sql_count = sql_counts.get(doc.id, 0)
        qdrant_count = await count_document_points(doc.id, tenant_id)
        total_qdrant += qdrant_count

        if sql_count == qdrant_count:
            status = "synced"
            missing: list[str] = []
        else:
            status = "mismatch"
            sql_point_ids_stmt = select(Chunk.qdrant_point_id).where(
                Chunk.document_id == doc.id,
                Chunk.qdrant_point_id != "",
            )
            sql_point_ids = {row[0] for row in (await db.execute(sql_point_ids_stmt)).all()}
            qdrant_point_ids = await scroll_document_point_ids(doc.id, tenant_id)
            missing = list(sql_point_ids - qdrant_point_ids)

        if only_mismatches and status == "synced":
            continue

        all_items.append(
            SyncDocumentItem(
                document_id=doc.id,
                filename=doc.filename,
                sql_count=sql_count,
                qdrant_count=qdrant_count,
                status=status,
                missing_in_qdrant=missing,
            )
        )

    total_items = len(all_items)
    start = (page - 1) * per_page
    paginated_items = all_items[start : start + per_page]

    synced = total_sql == total_qdrant and all(item.status == "synced" for item in all_items)

    return SyncCheckResponse(
        total_sql=total_sql,
        total_qdrant=total_qdrant,
        synced=synced,
        documents=PaginatedSyncDocuments(
            items=paginated_items,
            total=total_items,
            page=page,
            per_page=per_page,
        ),
    )


async def playground_search(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    query: str,
    lot: str | None = None,
    content_type: str | None = None,
    limit: int = 20,
) -> PlaygroundSearchResponse:
    """Search chunks via Qdrant semantic search for the admin playground."""
    start = time.perf_counter()

    vectors = await embed_texts([query])
    query_vector = vectors[0]

    must_conditions: list[FieldCondition] = [
        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
    ]
    if lot:
        must_conditions.append(FieldCondition(key="lot", match=MatchValue(value=lot)))
    if content_type:
        must_conditions.append(
            FieldCondition(key="content_type", match=MatchValue(value=content_type))
        )

    hits = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=limit,
        score_threshold=0.25,
    )

    point_ids = [str(hit.id) for hit in hits]
    score_map = {str(hit.id): hit.score for hit in hits}

    if point_ids:
        chunk_stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Document.filename,
                Chunk.text,
                Chunk.page,
                Chunk.position,
                Chunk.char_count,
                Chunk.content_type,
                Chunk.keywords,
                Chunk.section_title,
                Chunk.parent_sections,
                Chunk.localisation,
                Document.lot,
                Document.type,
                Chunk.qdrant_point_id,
            )
            .join(Document, Chunk.document_id == Document.id)
            .join(Project, Document.project_id == Project.id)
            .where(
                Chunk.qdrant_point_id.in_(point_ids),
                Document.project_id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        rows = (await db.execute(chunk_stmt)).all()
    else:
        rows = []

    row_map = {row.qdrant_point_id: row for row in rows}
    results: list[PlaygroundSearchResult] = []
    for pid in point_ids:
        row = row_map.get(pid)
        if not row:
            continue
        q_score = compute_quality_score(
            row.char_count,
            row.content_type,
            row.keywords,
            row.section_title,
            row.localisation,
        )
        results.append(
            PlaygroundSearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                filename=row.filename,
                text_preview=row.text[:200] if row.text else "",
                text=row.text or "",
                score=round(score_map[pid], 4),
                page=row.page,
                position=row.position,
                lot=row.lot,
                type=row.type,
                content_type=row.content_type,
                keywords=row.keywords or [],
                section_title=row.section_title,
                parent_sections=row.parent_sections or [],
                localisation=row.localisation or [],
                char_count=row.char_count or len(row.text or ""),
                quality_score=q_score,
            )
        )

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "Playground search query='%s' results=%d time=%.1fms",
        query[:80],
        len(results),
        elapsed_ms,
    )

    return PlaygroundSearchResponse(
        results=results,
        query_time_ms=elapsed_ms,
        total_results=len(results),
    )


async def detect_duplicates(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    threshold: float = 0.92,
) -> DuplicateResponse:
    """Detect near-duplicate chunks within a document using cosine similarity."""
    import numpy as np

    doc_check = await db.execute(
        select(Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.id == document_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    if not doc_check.first():
        raise NotFoundError("Document not found")

    doc_filter = Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
            FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
        ]
    )
    all_records = []
    offset = None
    while True:
        records, next_offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=doc_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        all_records.extend(records)
        if next_offset is None:
            break
        offset = next_offset

    if len(all_records) < 2:
        return DuplicateResponse(pairs=[], total_chunks_analyzed=len(all_records))

    point_ids = [str(r.id) for r in all_records]
    vectors = np.array([r.vector for r in all_records], dtype=np.float32)

    chunk_stmt = (
        select(Chunk.id, Chunk.qdrant_point_id, Chunk.text, Chunk.page, Chunk.position)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.document_id == document_id,
            Chunk.qdrant_point_id.in_(point_ids),
            Project.tenant_id == tenant_id,
        )
    )
    chunk_rows = (await db.execute(chunk_stmt)).all()
    chunk_map = {row.qdrant_point_id: row for row in chunk_rows}

    similarity_matrix = vectors @ vectors.T

    pairs: list[DuplicatePair] = []
    n = len(all_records)
    for i in range(n):
        for j in range(i + 1, n):
            sim = float(similarity_matrix[i, j])
            if sim >= threshold:
                chunk_a = chunk_map.get(point_ids[i])
                chunk_b = chunk_map.get(point_ids[j])
                if not chunk_a or not chunk_b:
                    continue
                pairs.append(
                    DuplicatePair(
                        chunk_a_id=chunk_a.id,
                        chunk_b_id=chunk_b.id,
                        chunk_a_preview=(chunk_a.text or "")[:150],
                        chunk_b_preview=(chunk_b.text or "")[:150],
                        chunk_a_position=chunk_a.position,
                        chunk_b_position=chunk_b.position,
                        chunk_a_page=chunk_a.page,
                        chunk_b_page=chunk_b.page,
                        similarity=round(sim, 4),
                    )
                )

    pairs.sort(key=lambda p: p.similarity, reverse=True)

    return DuplicateResponse(pairs=pairs, total_chunks_analyzed=n)


# ── Mutation helpers ──


async def _get_chunk_with_tenant_check(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
) -> Chunk:
    """Fetch a Chunk row and verify it belongs to the given project/tenant."""
    stmt = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.id == chunk_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise NotFoundError("Chunk not found")
    return chunk


def _build_qdrant_payload(
    chunk: Chunk,
    document: Document,
    tenant_id: uuid.UUID,
) -> dict[str, object]:
    """Build the Qdrant payload dict for a chunk.

    Delegates to the shared builder, which the ingestion pipeline uses too: the
    two constructions used to be separate and had drifted on six points.
    """
    return build_chunk_payload(
        ChunkPayloadFields.from_chunk(chunk),
        tenant_id=tenant_id,
        project_id=document.project_id,
        document_id=document.id,
        doc_type=document.type or "",
        filename=document.filename,
        phase=document.phase or "",
        document_lot=document.lot or "",
        ingested_at=document.ingested_at,
    )


# ── Mutation service functions ──


async def update_chunk(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    new_text: str,
) -> ChunkMutationResponse:
    """Update a chunk's text, re-extract keywords, and re-embed in Qdrant."""
    chunk = await _get_chunk_with_tenant_check(db, tenant_id, project_id, chunk_id)

    doc_stmt = select(Document).where(Document.id == chunk.document_id)
    document = (await db.execute(doc_stmt)).scalar_one()

    chunk.text = new_text
    chunk.char_count = len(new_text)
    chunk.keywords = _extract_keywords(new_text)
    chunk.localisation = _extract_localisation(new_text)

    vectors = await embed_texts([new_text])
    payload = _build_qdrant_payload(chunk, document, tenant_id)

    await qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=chunk.qdrant_point_id,
                vector=vectors[0],
                payload=payload,
            )
        ],
    )

    await db.commit()
    return ChunkMutationResponse(message="Chunk mis à jour", chunk_ids=[chunk.id])


async def split_chunk(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    split_position: int,
) -> ChunkMutationResponse:
    """Split a chunk at the given character position into two new chunks."""
    chunk = await _get_chunk_with_tenant_check(db, tenant_id, project_id, chunk_id)

    if split_position >= len(chunk.text):
        raise NotFoundError("Split position exceeds chunk text length")

    text_a = chunk.text[:split_position].strip()
    text_b = chunk.text[split_position:].strip()

    if not text_a or not text_b:
        raise NotFoundError("Split would produce an empty chunk")

    doc_stmt = select(Document).where(Document.id == chunk.document_id)
    document = (await db.execute(doc_stmt)).scalar_one()

    old_position = chunk.position
    old_point_id = chunk.qdrant_point_id
    document_id = chunk.document_id
    page = chunk.page
    content_type = chunk.content_type
    section_title = chunk.section_title
    parent_sections = chunk.parent_sections
    lot = chunk.lot
    phase = chunk.phase
    doc_type = chunk.type
    heading_prefix = chunk.heading_prefix

    shift_stmt = (
        update(Chunk)
        .where(
            Chunk.document_id == document_id,
            Chunk.position > old_position,
        )
        .values(position=Chunk.position + 1)
    )
    await db.execute(shift_stmt)

    await db.delete(chunk)
    await db.flush()

    await qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=[old_point_id],
    )

    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    point_id_a = str(uuid.uuid4())
    point_id_b = str(uuid.uuid4())

    chunk_a = Chunk(
        id=id_a,
        document_id=document_id,
        text=text_a,
        page=page,
        position=old_position,
        qdrant_point_id=point_id_a,
        content_type=content_type,
        keywords=_extract_keywords(text_a),
        localisation=_extract_localisation(text_a),
        section_title=section_title,
        parent_sections=parent_sections,
        char_count=len(text_a),
        lot=lot,
        phase=phase,
        type=doc_type,
        heading_prefix=heading_prefix,
    )
    chunk_b = Chunk(
        id=id_b,
        document_id=document_id,
        text=text_b,
        page=page,
        position=old_position + 1,
        qdrant_point_id=point_id_b,
        content_type=content_type,
        keywords=_extract_keywords(text_b),
        localisation=_extract_localisation(text_b),
        section_title=section_title,
        parent_sections=parent_sections,
        char_count=len(text_b),
        lot=lot,
        phase=phase,
        type=doc_type,
        heading_prefix=heading_prefix,
    )
    db.add(chunk_a)
    db.add(chunk_b)
    await db.flush()

    vectors = await embed_texts([text_a, text_b])
    payload_a = _build_qdrant_payload(chunk_a, document, tenant_id)
    payload_b = _build_qdrant_payload(chunk_b, document, tenant_id)

    await qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(id=point_id_a, vector=vectors[0], payload=payload_a),
            PointStruct(id=point_id_b, vector=vectors[1], payload=payload_b),
        ],
    )

    await db.commit()
    return ChunkMutationResponse(
        message="Chunk découpé en 2",
        chunk_ids=[id_a, id_b],
    )


async def merge_chunks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    adjacent_chunk_id: uuid.UUID,
) -> ChunkMutationResponse:
    """Merge two adjacent chunks from the same document into one."""
    chunk_a = await _get_chunk_with_tenant_check(db, tenant_id, project_id, chunk_id)
    chunk_b = await _get_chunk_with_tenant_check(db, tenant_id, project_id, adjacent_chunk_id)

    if chunk_a.document_id != chunk_b.document_id:
        raise NotFoundError("Chunks must belong to the same document")

    if chunk_a.position > chunk_b.position:
        chunk_a, chunk_b = chunk_b, chunk_a

    combined_text = chunk_a.text + "\n\n" + chunk_b.text
    keep_position = chunk_a.position
    document_id = chunk_a.document_id

    doc_stmt = select(Document).where(Document.id == document_id)
    document = (await db.execute(doc_stmt)).scalar_one()

    old_point_a = chunk_a.qdrant_point_id
    old_point_b = chunk_b.qdrant_point_id

    await db.delete(chunk_a)
    await db.delete(chunk_b)
    await db.flush()

    await qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=[old_point_a, old_point_b],
    )

    shift_stmt = (
        update(Chunk)
        .where(
            Chunk.document_id == document_id,
            Chunk.position > keep_position + 1,
        )
        .values(position=Chunk.position - 1)
    )
    await db.execute(shift_stmt)

    new_id = uuid.uuid4()
    new_point_id = str(uuid.uuid4())

    merged_chunk = Chunk(
        id=new_id,
        document_id=document_id,
        text=combined_text,
        page=chunk_a.page,
        position=keep_position,
        qdrant_point_id=new_point_id,
        content_type=chunk_a.content_type,
        keywords=_extract_keywords(combined_text),
        localisation=_extract_localisation(combined_text),
        section_title=chunk_a.section_title,
        parent_sections=chunk_a.parent_sections,
        char_count=len(combined_text),
        lot=chunk_a.lot,
        phase=chunk_a.phase,
        type=chunk_a.type,
        heading_prefix=chunk_a.heading_prefix,
    )
    db.add(merged_chunk)
    await db.flush()

    vectors = await embed_texts([combined_text])
    payload = _build_qdrant_payload(merged_chunk, document, tenant_id)

    await qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(id=new_point_id, vector=vectors[0], payload=payload),
        ],
    )

    await db.commit()
    return ChunkMutationResponse(
        message="Chunks fusionnés",
        chunk_ids=[new_id],
    )


async def delete_chunk(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
) -> None:
    """Delete a single chunk from both SQL and Qdrant."""
    chunk = await _get_chunk_with_tenant_check(db, tenant_id, project_id, chunk_id)

    position = chunk.position
    document_id = chunk.document_id
    point_id = chunk.qdrant_point_id

    await qdrant_client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=[point_id],
    )

    await db.delete(chunk)
    await db.flush()

    shift_stmt = (
        update(Chunk)
        .where(
            Chunk.document_id == document_id,
            Chunk.position > position,
        )
        .values(position=Chunk.position - 1)
    )
    await db.execute(shift_stmt)

    await db.commit()


async def rechunk_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
) -> RechunkResponse:
    """Delete all chunks for a document and re-run the ingestion pipeline.

    Refuses a second run while one is in flight. Nothing else stops it: the
    chunk delete and the Qdrant purge are not one transaction, so a second run
    wipes what the first has already written and the two pipelines then upsert
    the same document's vectors against each other. The client makes this easy
    to reach — the panel stays open when the request exceeds its deadline, the
    refetch shows the old list because the first run has only flushed, and it
    reads as if nothing happened, so the operator clicks again.
    """
    lock = _rechunk_locks.setdefault(document_id, asyncio.Lock())
    if lock.locked():
        raise ConflictError("a re-chunk is already running for this document")
    async with lock:
        return await _rechunk_document_locked(db, tenant_id, project_id, document_id)


async def _rechunk_document_locked(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
) -> RechunkResponse:
    doc_stmt = (
        select(Document)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.id == document_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    document = (await db.execute(doc_stmt)).scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    old_stats_stmt = select(
        func.count(Chunk.id).label("count"),
        func.coalesce(func.avg(Chunk.char_count), 0).label("avg_chars"),
    ).where(Chunk.document_id == document_id)
    old_row = (await db.execute(old_stats_stmt)).one()
    old_count = old_row.count
    old_avg_chars = float(old_row.avg_chars)

    del_stmt = delete(Chunk).where(Chunk.document_id == document_id)
    await db.execute(del_stmt)
    await db.flush()

    await delete_document_vectors(document_id, tenant_id)

    from app.services.document import UPLOAD_DIR

    file_path = UPLOAD_DIR / str(document.project_id) / document.filename
    if not file_path.exists():
        await db.commit()
        raise NotFoundError(f"File not found on disk: {document.filename}")

    from app.services.ingestion.pipeline import run_ingestion

    await run_ingestion(db, document, file_path, tenant_id)

    new_stats_stmt = select(
        func.count(Chunk.id).label("count"),
        func.coalesce(func.avg(Chunk.char_count), 0).label("avg_chars"),
    ).where(Chunk.document_id == document_id)
    new_row = (await db.execute(new_stats_stmt)).one()
    new_count = new_row.count
    new_avg_chars = float(new_row.avg_chars)

    return RechunkResponse(
        old_count=old_count,
        new_count=new_count,
        old_avg_chars=round(old_avg_chars, 1),
        new_avg_chars=round(new_avg_chars, 1),
        message=f"Re-chunking terminé : {old_count} → {new_count} chunks",
    )


# ── Advanced filter / analysis functions ──


async def semantic_search_chunks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    query: str,
    lot: str | None = None,
    limit: int = 50,
) -> PaginatedChunks:
    """Semantic search over project chunks via Qdrant, returning paginated results."""
    vectors = await embed_texts([query])
    query_vector = vectors[0]

    must_conditions: list[FieldCondition] = [
        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
    ]
    if lot:
        must_conditions.append(FieldCondition(key="lot", match=MatchValue(value=lot)))

    hits = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=limit,
        score_threshold=0.25,
    )

    point_ids = [str(hit.id) for hit in hits]

    if not point_ids:
        return PaginatedChunks(items=[], total=0, page=1, per_page=limit, total_pages=1)

    chunk_stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.text,
            Chunk.page,
            Chunk.position,
            Chunk.char_count,
            Chunk.content_type,
            Chunk.keywords,
            Chunk.section_title,
            Chunk.parent_sections,
            Chunk.localisation,
            Document.lot,
            Document.phase,
            Document.type,
            Chunk.qdrant_point_id,
            Chunk.created_at,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.qdrant_point_id.in_(point_ids),
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    rows = (await db.execute(chunk_stmt)).all()
    row_map = {row.qdrant_point_id: row for row in rows}

    items: list[ChunkListItem] = []
    for pid in point_ids:
        row = row_map.get(pid)
        if not row:
            continue
        items.append(
            ChunkListItem(
                id=row.id,
                document_id=row.document_id,
                filename=row.filename,
                text_preview=row.text[:150] if row.text else "",
                page=row.page,
                position=row.position,
                char_count=row.char_count,
                content_type=row.content_type,
                keywords=row.keywords,
                section_title=row.section_title,
                parent_sections=row.parent_sections,
                localisation=row.localisation,
                lot=row.lot,
                phase=row.phase,
                type=row.type,
                qdrant_point_id=row.qdrant_point_id,
                created_at=row.created_at,
                quality_score=compute_quality_score(
                    row.char_count,
                    row.content_type,
                    row.keywords,
                    row.section_title,
                    row.localisation,
                ),
            )
        )

    return PaginatedChunks(
        items=items,
        total=len(items),
        page=1,
        per_page=limit,
        total_pages=1,
    )


async def get_section_tree(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> list[SectionNode]:
    """Build a hierarchical section tree from chunk parent_sections metadata."""
    stmt = (
        select(Chunk.parent_sections)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
            Chunk.parent_sections.isnot(None),
        )
    )
    rows = (await db.execute(stmt)).all()

    tree: dict[str, dict] = {}

    for (parent_sections,) in rows:
        if not parent_sections:
            continue
        current_level = tree
        for section in parent_sections:
            if section not in current_level:
                current_level[section] = {"_children": {}, "_count": 0}
            current_level = current_level[section]
        current_level["_count"] = current_level.get("_count", 0) + 1

    def _build_nodes(level: dict[str, dict]) -> list[SectionNode]:
        nodes: list[SectionNode] = []
        for title, data in level.items():
            if title.startswith("_"):
                continue
            children = _build_nodes(data.get("_children", {}))
            direct_count = data.get("_count", 0)
            nodes.append(
                SectionNode(
                    title=title,
                    children=children,
                    chunk_count=direct_count,
                )
            )
        return nodes

    root: dict[str, dict] = {}

    for (parent_sections,) in rows:
        if not parent_sections:
            continue
        node = root
        for i, section in enumerate(parent_sections):
            if section not in node:
                node[section] = {"_children": {}, "_count": 0}
            if i == len(parent_sections) - 1:
                node[section]["_count"] += 1
            node = node[section]["_children"]

    def _to_nodes(level: dict[str, dict]) -> list[SectionNode]:
        result: list[SectionNode] = []
        for title, data in level.items():
            children = _to_nodes(data["_children"])
            result.append(
                SectionNode(
                    title=title,
                    children=children,
                    chunk_count=data["_count"],
                )
            )
        return result

    return _to_nodes(root)


async def find_similar_chunks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    chunk_id: uuid.UUID,
    *,
    limit: int = 10,
) -> list[SimilarChunkResult]:
    """Find chunks similar to a given chunk using its Qdrant vector."""
    chunk_stmt = (
        select(Chunk.qdrant_point_id)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.id == chunk_id,
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(chunk_stmt)).scalar_one_or_none()
    if not row:
        raise NotFoundError("Chunk not found")

    point_id = row

    records = await qdrant_client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_vectors=True,
    )
    if not records:
        raise NotFoundError("Chunk vector not found in Qdrant")

    vector = records[0].vector

    hits = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        query_filter=Filter(
            must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
            ]
        ),
        limit=limit + 1,
        score_threshold=0.25,
    )

    hit_point_ids = [str(hit.id) for hit in hits if str(hit.id) != point_id]
    hit_point_ids = hit_point_ids[:limit]
    score_map = {str(hit.id): hit.score for hit in hits}

    if not hit_point_ids:
        return []

    meta_stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Document.filename,
            Chunk.text,
            Chunk.content_type,
            Chunk.section_title,
            Chunk.qdrant_point_id,
        )
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Chunk.qdrant_point_id.in_(hit_point_ids),
            Project.tenant_id == tenant_id,
        )
    )
    meta_rows = (await db.execute(meta_stmt)).all()
    meta_map = {r.qdrant_point_id: r for r in meta_rows}

    results: list[SimilarChunkResult] = []
    for pid in hit_point_ids:
        meta = meta_map.get(pid)
        if not meta:
            continue
        results.append(
            SimilarChunkResult(
                chunk_id=meta.id,
                document_id=meta.document_id,
                filename=meta.filename,
                text_preview=meta.text[:200] if meta.text else "",
                similarity=round(score_map.get(pid, 0.0), 4),
                content_type=meta.content_type,
                section_title=meta.section_title,
            )
        )

    return results


_ENRICH_BATCH_SIZE = 100

_LEGACY_MARKER = "doc_type"

_rechunk_locks: dict[uuid.UUID, asyncio.Lock] = {}


async def _project_chunks_by_point_id(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, tuple[Chunk, Document]]:
    """Every chunk of one project that has a vector, keyed by its point id.

    Joined to `Project.tenant_id`: the point ids come back from a filtered
    Qdrant scroll, but the rows they are rebuilt from must carry the isolation
    key of their own accord.
    """
    stmt = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
            Chunk.qdrant_point_id.is_not(None),
        )
    )
    rows = await db.execute(stmt)
    return {str(chunk.qdrant_point_id): (chunk, document) for chunk, document in rows}


async def _flush_enrichment(db: AsyncSession, operations: list[UpdateOperation]) -> None:
    """Write one batch: the vector payloads first, the rows after.

    That order is the resilient one and it is not an accident. Interrupted
    between the two, Qdrant carries keywords the database does not — and the
    next run picks those chunks up again, because the query selects on the
    database being empty, so it repairs itself. Committing first would leave
    Qdrant permanently behind: the rows would look enriched and never be
    revisited.
    """
    if operations:
        await qdrant_client.batch_update_points(
            collection_name=COLLECTION_NAME, update_operations=operations
        )
    await db.commit()


async def repair_legacy_payloads(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> RepairPayloadsResponse:
    """Rewrite payloads written before the unified builder existed.

    Those carry `doc_type` and no `type`, so they fall out of every
    type-filtered query. Rebuilt via the same builder the pipeline uses and
    written back with an overwrite, so the legacy marker cannot survive.

    A point whose chunk row is gone is counted and left alone rather than
    deleted.
    """
    chunks = await _project_chunks_by_point_id(db, tenant_id, project_id)

    repaired = 0
    orphans = 0
    operations: list[UpdateOperation] = []
    offset = None

    while True:
        records, offset = await qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                    FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
                ]
            ),
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for record in records:
            payload = record.payload or {}
            if _LEGACY_MARKER not in payload or "type" in payload:
                continue
            pair = chunks.get(str(record.id))
            if pair is None:
                orphans += 1
                continue
            chunk, document = pair
            operations.append(
                OverwritePayloadOperation(
                    overwrite_payload=SetPayload(
                        payload=_build_qdrant_payload(chunk, document, tenant_id),
                        points=[record.id],
                    )
                )
            )
            repaired += 1

        if operations:
            await qdrant_client.batch_update_points(
                collection_name=COLLECTION_NAME, update_operations=operations
            )
            operations = []
        if offset is None:
            break

    return RepairPayloadsResponse(
        repaired_count=repaired,
        orphan_count=orphans,
        message=f"{repaired} payloads réparés, {orphans} points sans chunk correspondant.",
    )


async def batch_enrich_keywords(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> BatchEnrichResponse:
    """Extract and set keywords + localisation for all chunks that currently lack them."""
    stmt = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(
            Document.project_id == project_id,
            Project.tenant_id == tenant_id,
            or_(
                Chunk.keywords.is_(None),
                Chunk.keywords.cast(String) == "[]",
            ),
        )
    )
    result = await db.execute(stmt)
    chunks = list(result.scalars().all())

    if not chunks:
        return BatchEnrichResponse(
            updated_count=0,
            message="Aucun chunk sans mots-clés trouvé.",
        )

    updated = 0
    operations: list[UpdateOperation] = []
    since_commit = 0

    for chunk in chunks:
        keywords = _extract_keywords(chunk.text)
        localisation = _extract_localisation(chunk.text)
        if not keywords and not localisation:
            continue
        chunk.keywords = keywords
        chunk.localisation = localisation

        if chunk.qdrant_point_id:
            operations.append(
                SetPayloadOperation(
                    set_payload=SetPayload(
                        payload={"keywords": keywords, "localisation": localisation},
                        points=[chunk.qdrant_point_id],
                    )
                )
            )
        updated += 1
        since_commit += 1

        if since_commit >= _ENRICH_BATCH_SIZE:
            await _flush_enrichment(db, operations)
            operations = []
            since_commit = 0

    await _flush_enrichment(db, operations)

    return BatchEnrichResponse(
        updated_count=updated,
        message=f"{updated} chunks enrichis avec mots-clés et localisation.",
    )
