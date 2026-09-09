"""Ingestion pipeline orchestrator: extraction → classification → chunking → embedding."""

import asyncio
import logging
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.admin import compute_quality_score
from app.services.ingestion.chunking import TextChunk, chunk_document
from app.services.ingestion.classification import classify_document
from app.services.ingestion.cleaning import clean_pages
from app.services.ingestion.embedding import index_chunks
from app.services.ingestion.extraction import extract

logger = logging.getLogger(__name__)


def _log_chunk_analysis(
    chunks: list[TextChunk],
    filename: str,
    doc_type: str,
    lot: str,
) -> dict[str, object]:
    """Log a detailed quality analysis of generated chunks.

    Returns a summary dict for potential storage/API exposure.
    """
    if not chunks:
        logger.warning(
            "[CHUNK ANALYSIS] %s — 0 chunks generated (type=%s, lot=%s)",
            filename,
            doc_type,
            lot,
        )
        return {"total": 0}

    char_counts = [c.char_count or len(c.text) for c in chunks]
    total = len(chunks)
    avg_chars = sum(char_counts) / total
    min_chars = min(char_counts)
    max_chars = max(char_counts)

    tiny = sum(1 for c in char_counts if c < 100)
    small = sum(1 for c in char_counts if 100 <= c < 500)
    medium = sum(1 for c in char_counts if 500 <= c < 1500)
    large = sum(1 for c in char_counts if 1500 <= c < 2500)
    oversized = sum(1 for c in char_counts if c >= 2500)

    ct_dist = Counter(c.content_type for c in chunks)

    with_kw = sum(1 for c in chunks if c.keywords)
    total_kw = sum(len(c.keywords) for c in chunks)
    unique_kw = len({kw for c in chunks for kw in c.keywords})

    q_scores = [
        compute_quality_score(
            c.char_count or len(c.text),
            c.content_type,
            c.keywords,
            c.section_title,
            c.localisation,
        )
        for c in chunks
    ]
    avg_quality = sum(q_scores) / len(q_scores)
    low_quality = sum(1 for s in q_scores if s < 0.4)

    with_section = sum(1 for c in chunks if c.section_title)
    with_parents = sum(1 for c in chunks if c.parent_sections)

    heading_only = sum(1 for c in chunks if c.content_type == "heading")

    logger.info(
        "[CHUNK ANALYSIS] %s | type=%s lot=%s | %d chunks, avg=%d chars (min=%d, max=%d)",
        filename,
        doc_type,
        lot or "—",
        total,
        avg_chars,
        min_chars,
        max_chars,
    )

    logger.info(
        "[CHUNK ANALYSIS] %s | size distribution: "
        "tiny(<100)=%d, small(100-500)=%d, medium(500-1500)=%d, "
        "large(1500-2500)=%d, oversized(>2500)=%d",
        filename,
        tiny,
        small,
        medium,
        large,
        oversized,
    )

    logger.info(
        "[CHUNK ANALYSIS] %s | content types: %s",
        filename,
        ", ".join(f"{ct}={n}" for ct, n in ct_dist.most_common()),
    )

    with_loc = sum(1 for c in chunks if c.localisation)

    logger.info(
        "[CHUNK ANALYSIS] %s | keywords: %d/%d chunks have keywords "
        "(%d total, %d unique) | sections: %d/%d with title, %d/%d with hierarchy "
        "| localisation: %d/%d",
        filename,
        with_kw,
        total,
        total_kw,
        unique_kw,
        with_section,
        total,
        with_parents,
        total,
        with_loc,
        total,
    )

    logger.info(
        "[CHUNK ANALYSIS] %s | quality: avg=%.0f%%, low_quality(<40%%)=%d/%d, heading_only=%d",
        filename,
        avg_quality * 100,
        low_quality,
        total,
        heading_only,
    )

    if tiny > 0:
        tiny_examples = [
            f"pos={c.position} ({c.char_count or len(c.text)} chars): {c.text[:60]!r}"
            for c in chunks
            if (c.char_count or len(c.text)) < 100
        ][:3]
        logger.warning(
            "[CHUNK QUALITY] %s — %d tiny chunks (<100 chars): %s",
            filename,
            tiny,
            " | ".join(tiny_examples),
        )

    if oversized > 0:
        oversized_examples = [
            f"pos={c.position} ({c.char_count or len(c.text)} chars)"
            for c in chunks
            if (c.char_count or len(c.text)) >= 2500
        ][:3]
        logger.warning(
            "[CHUNK QUALITY] %s — %d oversized chunks (>2500 chars): %s",
            filename,
            oversized,
            ", ".join(oversized_examples),
        )

    if heading_only > total * 0.15:
        logger.warning(
            "[CHUNK QUALITY] %s — %d/%d chunks are heading-only (%.0f%%)",
            filename,
            heading_only,
            total,
            heading_only / total * 100,
        )

    if with_kw < total * 0.3:
        logger.warning(
            "[CHUNK QUALITY] %s — only %d/%d chunks have keywords (%.0f%%)",
            filename,
            with_kw,
            total,
            with_kw / total * 100,
        )

    if avg_quality < 0.5:
        logger.warning(
            "[CHUNK QUALITY] %s — low average quality score: %.0f%%",
            filename,
            avg_quality * 100,
        )

    return {
        "total": total,
        "avg_chars": round(avg_chars),
        "min_chars": min_chars,
        "max_chars": max_chars,
        "size_distribution": {
            "tiny": tiny,
            "small": small,
            "medium": medium,
            "large": large,
            "oversized": oversized,
        },
        "content_types": dict(ct_dist),
        "keywords": {"with": with_kw, "total": total_kw, "unique": unique_kw},
        "avg_quality": round(avg_quality, 2),
        "low_quality_count": low_quality,
        "heading_only": heading_only,
    }


async def run_ingestion(
    db: AsyncSession,
    document: Document,
    file_path: Path,
    tenant_id: uuid.UUID,
) -> None:
    """Run the full ingestion pipeline for a document.

    Steps: extract → classify → chunk → embed → save chunks → update status.
    On error: sets document status to 'error'.
    """
    try:
        pipeline_start = time.perf_counter()

        logger.info("[PIPELINE] %s — step 1/5: extraction", file_path.name)
        t0 = time.perf_counter()
        extraction = await asyncio.to_thread(extract, file_path)

        extraction.pages = await asyncio.to_thread(clean_pages, extraction.pages)
        extraction.full_text = "\n\n".join(p.text for p in extraction.pages)

        if file_path.suffix.lower() == ".pdf":
            from app.services.ingestion.vision import ocr_sparse_pages

            extraction.pages = await ocr_sparse_pages(file_path, extraction.pages)
            extraction.full_text = "\n\n".join(p.text for p in extraction.pages)

        extract_time = time.perf_counter() - t0
        total_chars = sum(len(p.text) for p in extraction.pages)
        logger.info(
            "[PIPELINE] %s — extraction done: %d pages, %d chars (%.1fs)",
            document.filename,
            len(extraction.pages),
            total_chars,
            extract_time,
        )

        logger.info("[PIPELINE] %s — step 2/5: classification", document.filename)
        t0 = time.perf_counter()
        classification = await classify_document(
            extraction.full_text,
            file_path=file_path,
            nb_pages=max(len(extraction.pages), 1),
        )
        classify_time = time.perf_counter() - t0
        document.type = classification["type"]
        document.lot = classification["lot"]
        document.phase = classification["phase"]
        logger.info(
            "[PIPELINE] %s — classified: type=%s, lot=%s, phase=%s (%.1fs)",
            document.filename,
            classification["type"],
            classification["lot"],
            classification["phase"],
            classify_time,
        )

        if classification["type"] == "plan":
            document.status = "ready"
            document.chunk_count = 0
            document.ingested_at = datetime.now(UTC)
            await db.commit()
            logger.info(
                "[PIPELINE] %s — plan detected, skipping chunking/embedding",
                document.filename,
            )
            return

        if not extraction.full_text.strip():
            document.status = "error"
            document.error_message = "No text could be extracted from file"
            await db.commit()
            logger.warning("No text extracted from %s", file_path.name)
            return

        strategy = classification["type"]
        logger.info("[PIPELINE] %s — step 3/5: chunking (strategy=%s)", document.filename, strategy)
        t0 = time.perf_counter()
        text_chunks = await asyncio.to_thread(
            chunk_document, extraction.pages, classification["type"]
        )
        chunk_time = time.perf_counter() - t0
        logger.info(
            "[PIPELINE] %s — chunking done: %d chunks (%.1fs)",
            document.filename,
            len(text_chunks),
            chunk_time,
        )

        chunk_report = _log_chunk_analysis(
            text_chunks,
            document.filename,
            classification["type"],
            classification["lot"],
        )

        if not text_chunks:
            document.status = "empty"
            document.chunk_count = 0
            document.error_message = "Chunking produced 0 chunks from extracted text"
            document.ingested_at = datetime.now(UTC)
            await db.commit()
            logger.warning(
                "[PIPELINE] %s — 0 chunks generated, marking as 'empty'",
                document.filename,
            )
            return

        n_chunks = len(text_chunks)
        logger.info("[PIPELINE] %s — step 4/5: embedding %d chunks", document.filename, n_chunks)
        t0 = time.perf_counter()
        ingestion_timestamp = datetime.now(UTC)
        point_ids = await index_chunks(
            text_chunks,
            tenant_id=tenant_id,
            project_id=document.project_id,
            document_id=document.id,
            doc_type=classification["type"],
            lot=classification["lot"],
            phase=classification["phase"],
            filename=document.filename,
            ingested_at=ingestion_timestamp,
        )

        embed_time = time.perf_counter() - t0
        logger.info(
            "[PIPELINE] %s — embedding done: %d points indexed (%.1fs)",
            document.filename,
            len(point_ids),
            embed_time,
        )

        logger.info("[PIPELINE] %s — step 5/5: saving to DB", document.filename)
        resolved_lot = classification["lot"]
        resolved_phase = classification["phase"]
        resolved_type = classification["type"]
        for text_chunk, qdrant_id in zip(text_chunks, point_ids, strict=True):
            chunk = Chunk(
                document_id=document.id,
                text=text_chunk.text,
                page=text_chunk.page,
                position=text_chunk.position,
                qdrant_point_id=qdrant_id,
                lot=text_chunk.chunk_lot or resolved_lot,
                phase=resolved_phase,
                type=resolved_type,
                heading_prefix=text_chunk.heading_prefix or None,
                content_type=text_chunk.content_type,
                keywords=text_chunk.keywords or None,
                section_title=text_chunk.section_title or None,
                parent_sections=text_chunk.parent_sections or None,
                char_count=text_chunk.char_count or len(text_chunk.text),
                localisation=text_chunk.localisation or None,
            )
            db.add(chunk)

        document.status = "ready"
        document.chunk_count = len(point_ids)
        document.ingested_at = ingestion_timestamp
        document.error_message = None
        await db.commit()

        total_time = time.perf_counter() - pipeline_start
        logger.info(
            "[PIPELINE COMPLETE] %s | %d chunks | quality=%.0f%% | "
            "times: extract=%.1fs classify=%.1fs chunk=%.1fs embed=%.1fs total=%.1fs",
            document.filename,
            len(point_ids),
            chunk_report.get("avg_quality", 0) * 100,
            extract_time,
            classify_time,
            chunk_time,
            embed_time,
            total_time,
        )

    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document.id)
        document.status = "error"
        document.error_message = f"{type(exc).__name__}: {exc}"[:500]
        await db.commit()
