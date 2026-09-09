"""Chunk enrichment — heading expansion and DPGF quantity retrieval."""

import logging
import re
import uuid

from app.core.qdrant import qdrant_client
from app.schemas.search import SearchResult
from app.services.ingestion.classification import TYPE_DPGF

logger = logging.getLogger(__name__)

# ── Heading expansion ────────────────────────────────────────────

_FILLER_RE = re.compile(r"[.\s\-─…]+")


async def expand_heading_chunks(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    search_results: list[SearchResult],
) -> list[SearchResult]:
    """When a heading-only chunk is found, fetch its adjacent children via Qdrant scroll.

    Heading-only chunks (short section titles, ~30 chars) match search queries
    well but lack actual content. Their sub-articles, which carry brand,
    dimensions and quantities, are stored as separate chunks at position+1,
    +2, etc.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from app.services.ingestion.embedding import COLLECTION_NAME

    heading_results: list[SearchResult] = []
    for sr in search_results:
        if not sr.filename:
            continue
        if sr.content_type == "heading":
            heading_results.append(sr)
            continue
        meaningful = _FILLER_RE.sub("", sr.text)
        if len(meaningful) < 150:
            heading_results.append(sr)

    if not heading_results:
        return search_results

    existing_texts = {sr.text[:200] for sr in search_results}
    enriched = list(search_results)

    doc_headings: dict[str, list[SearchResult]] = {}
    for sr in heading_results:
        doc_headings.setdefault(str(sr.document_id), []).append(sr)

    for doc_id_str, headings in doc_headings.items():
        target_positions: set[int] = set()
        for h in headings:
            for offset in range(1, 4):
                target_positions.add(h.position + offset)

        all_records = []
        next_offset = None
        try:
            while True:
                records, next_offset = await qdrant_client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                            FieldCondition(
                                key="project_id", match=MatchValue(value=str(project_id))
                            ),
                            FieldCondition(key="document_id", match=MatchValue(value=doc_id_str)),
                        ]
                    ),
                    limit=100,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                all_records.extend(records)
                if next_offset is None:
                    break
        except Exception:
            logger.exception("Failed to scroll adjacent chunks for doc %s", doc_id_str)
            continue

        added_count = 0
        for record in all_records:
            payload = record.payload or {}
            position = payload.get("position", -1)
            if position not in target_positions:
                continue
            text = payload.get("text", "")
            text_key = text[:200]
            if text_key in existing_texts:
                continue
            if len(text.strip()) < 50:
                continue
            existing_texts.add(text_key)
            added_count += 1
            enriched.append(
                SearchResult(
                    text=text,
                    page=payload.get("page", 0),
                    position=position,
                    filename=payload.get("filename", ""),
                    document_id=uuid.UUID(payload["document_id"]),
                    project_id=uuid.UUID(payload["project_id"]),
                    score=0.45,
                    lot=payload.get("lot", ""),
                    phase=payload.get("phase", ""),
                    type=payload.get("type", ""),
                    heading_prefix=payload.get("heading_prefix"),
                    section_title=payload.get("section_title"),
                    parent_sections=payload.get("parent_sections", []),
                    content_type=payload.get("content_type"),
                    keywords=payload.get("keywords", []),
                    localisation=payload.get("localisation", []),
                    char_count=payload.get("char_count", len(text)),
                )
            )

        if added_count:
            logger.debug(
                f"[CHAT DEBUG] Heading expansion doc={doc_id_str[:8]}: "
                f"added {added_count} adjacent chunks for {len(headings)} heading(s)"
            )

    total_added = len(enriched) - len(search_results)
    if total_added:
        logger.debug(f"[CHAT DEBUG] Heading expansion total: {total_added} new chunks")
    return enriched


# ── DPGF quantity enrichment ─────────────────────────────────────

_DPGF_EXCLUDE_RE = re.compile(
    r"(?:TERRASSEMENT|GROS.?OEUVRE|GROS.?ŒUVRE|VRD)",
    re.IGNORECASE,
)


def _extract_article_prefix(text: str) -> str:
    """Extract the article number prefix (e.g. '7.2.2.1' from '7.2.2.1.1 En 20x120cm')."""
    m = re.match(r"^\s*(\d+(?:\.\d+)+)", text)
    return m.group(1) if m else ""


def _filename_matches_query(filename: str, query_words: set[str]) -> bool:
    """Check if a DPGF filename relates to the question topic."""
    fname_lower = filename.lower().replace("_", " ").replace("-", " ")
    fname_words = set(re.findall(r"[a-zàâéèêëïîôùûüç]{3,}", fname_lower))
    if query_words & fname_words:
        return True
    for qw in query_words:  # noqa: SIM110
        if len(qw) >= 4 and qw in fname_lower:
            return True
    return False


async def enrich_with_dpgf_quantities(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    search_query: str,
    question: str,
    search_results: list[SearchResult],
) -> list[SearchResult]:
    """Scroll ALL DPGF files in the project and keep relevant quantity chunks.

    Uses Qdrant scroll (reliable at any scale since we paginate) with
    tight filtering:
    1. Find matched DPGF files (by filename OR by topical prefix in results)
    2. Scroll only matched files
    3. Filter by article prefix matching (>= 3 levels) + topic keywords
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from app.services.ingestion.embedding import COLLECTION_NAME

    question_words = set(re.findall(r"[a-zàâéèêëïîôùûüç]{4,}", question.lower()))
    query_words = set(question_words)
    query_words.update(re.findall(r"[a-zàâéèêëïîôùûüç]{4,}", search_query.lower()))

    known_prefixes: set[str] = set()
    relevant_lots: set[str] = set()
    for sr in search_results:
        if sr.lot:
            relevant_lots.add(sr.lot)
        if sr.type != TYPE_DPGF:
            continue
        text_lower = sr.text.lower()
        is_topical = any(kw in text_lower for kw in query_words if len(kw) >= 4)
        if not is_topical:
            continue
        prefix = _extract_article_prefix(sr.text)
        if prefix:
            parts = prefix.split(".")
            for i in range(min(3, len(parts)), len(parts) + 1):
                known_prefixes.add(".".join(parts[:i]))

    dpgf_filenames_in_results: dict[str, set[str]] = {}
    dpgf_lots_in_results: dict[str, str] = {}
    for sr in search_results:
        if sr.type == TYPE_DPGF and sr.filename:
            prefix = _extract_article_prefix(sr.text)
            dpgf_filenames_in_results.setdefault(sr.filename, set())
            if prefix:
                dpgf_filenames_in_results[sr.filename].add(prefix)
            if sr.lot:
                dpgf_lots_in_results[sr.filename] = sr.lot

    matched_filenames: set[str] = set()

    for fname in dpgf_filenames_in_results:
        if not _DPGF_EXCLUDE_RE.search(fname) and _filename_matches_query(fname, question_words):
            matched_filenames.add(fname)

    for fname, prefixes in dpgf_filenames_in_results.items():
        if _DPGF_EXCLUDE_RE.search(fname):
            continue
        if fname in matched_filenames:
            continue
        for p in prefixes:
            if any(p.startswith(kp) or kp.startswith(p) for kp in known_prefixes):
                matched_filenames.add(fname)
                break

    try:
        discovery_records = []
        next_offset = None
        while True:
            records, next_offset = await qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                        FieldCondition(key="project_id", match=MatchValue(value=str(project_id))),
                        FieldCondition(key="type", match=MatchValue(value=TYPE_DPGF)),
                    ]
                ),
                limit=100,
                offset=next_offset,
                with_payload=["filename", "lot"],
                with_vectors=False,
            )
            discovery_records.extend(records)
            if next_offset is None:
                break
        all_dpgf_files: dict[str, str] = {}
        for r in discovery_records:
            payload = r.payload or {}
            fname = payload.get("filename", "")
            if fname:
                all_dpgf_files[fname] = payload.get("lot", "")

        for fname, lot in all_dpgf_files.items():
            if fname in matched_filenames or _DPGF_EXCLUDE_RE.search(fname):
                continue
            if _filename_matches_query(fname, question_words) or lot and lot in relevant_lots:
                matched_filenames.add(fname)
    except Exception:
        logger.exception("DPGF filename discovery failed")

    if not matched_filenames:
        logger.debug("[CHAT DEBUG] DPGF enrichment: no matched files")
        return search_results

    logger.debug(
        f"[DPGF DEBUG] matched files={matched_filenames} | "
        f"relevant_lots={relevant_lots} | "
        f"known_prefixes={sorted(known_prefixes)}"
    )

    existing_texts = {sr.text[:200] for sr in search_results}
    enriched = list(search_results)

    for filename in matched_filenames:
        all_records = []
        next_offset = None
        try:
            while True:
                records, next_offset = await qdrant_client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                            FieldCondition(
                                key="project_id", match=MatchValue(value=str(project_id))
                            ),
                            FieldCondition(key="filename", match=MatchValue(value=filename)),
                        ]
                    ),
                    limit=50,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                all_records.extend(records)
                if next_offset is None:
                    break
        except Exception:
            logger.exception("Failed to scroll DPGF chunks for %s", filename)
            continue

        kept = 0
        skipped = 0
        for record in all_records:
            payload = record.payload or {}
            text = payload.get("text", "")
            text_key = text[:200]
            if text_key in existing_texts:
                continue

            chunk_prefix = _extract_article_prefix(text)
            prefix_match = False
            if chunk_prefix and known_prefixes:
                for kp in known_prefixes:
                    if chunk_prefix.startswith(kp) or kp.startswith(chunk_prefix):
                        prefix_match = True
                        break

            text_lower = text.lower()
            has_topic = any(kw in text_lower for kw in query_words if len(kw) >= 4)

            if not prefix_match and not has_topic:
                skipped += 1
                continue

            existing_texts.add(text_key)
            kept += 1
            enriched.append(
                SearchResult(
                    text=text,
                    page=payload.get("page", 0),
                    position=payload.get("position", 0),
                    filename=filename,
                    document_id=uuid.UUID(payload["document_id"]),
                    project_id=uuid.UUID(payload["project_id"]),
                    score=0.5,
                    lot=payload.get("lot", ""),
                    phase=payload.get("phase", ""),
                    type=payload.get("type", TYPE_DPGF),
                    heading_prefix=payload.get("heading_prefix"),
                    section_title=payload.get("section_title"),
                    parent_sections=payload.get("parent_sections", []),
                    content_type=payload.get("content_type"),
                    keywords=payload.get("keywords", []),
                    localisation=payload.get("localisation", []),
                    char_count=payload.get("char_count", len(text)),
                )
            )

        if kept > 0:
            logger.debug(
                f"[CHAT DEBUG] DPGF scroll '{filename}': "
                f"{len(all_records)} total, {kept} kept, {skipped} skipped"
            )

    added = len(enriched) - len(search_results)
    if added:
        for sr in enriched[len(search_results) :]:
            logger.debug(
                f"[CHAT DEBUG]   DPGF kept: p.{sr.page} "
                f"text='{sr.text[:150].replace(chr(10), ' ')}...'"
            )
    else:
        logger.debug("[CHAT DEBUG] DPGF enrichment: no new chunks after filtering")

    return enriched
