"""RAG streaming orchestrator — ties together all chat sub-modules."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mistral import mistral_client
from app.models.message import Message
from app.schemas.chat import Source, StructuredSchema, StructuredTable
from app.schemas.search import SearchFilters, SearchResult
from app.services import project as project_service
from app.services import search as search_service
from app.services.chat import conversation as conversation_mod
from app.services.chat.chunk_enrichment import (
    enrich_with_dpgf_quantities,
    expand_heading_chunks,
)
from app.services.chat.context_enrichment import build_db_context
from app.services.chat.prompts import (
    CONTEXT_MAX_CHARS,
    FORCED_SCHEMA_RE,
    FORCED_SCORE_FLOOR,
    HISTORY_WINDOW,
    LOCALISATION_INSTRUCTION,
    MAX_DISPLAYED_SOURCES,
    MIN_SOURCE_TEXT_LENGTH,
    SYSTEM_PROMPT,
    classify_scope,
    get_forced_related,
    get_ouvrage_instruction,
)
from app.services.chat.query_rewrite import rewrite_query
from app.services.chat.schema_extraction import enrich_schema_with_search, extract_schema
from app.services.chat.table_extraction import extract_table

logger = logging.getLogger(__name__)

# ── Dedup helpers ─────────────────────────────────────────────────

_LOCALIZATION_RE = re.compile(
    r"(?:au droit|localisation\s*:)[^\n]*",
    re.IGNORECASE,
)
_NUMBERS_RE = re.compile(r"[\d.,]+\s*(?:m[²³23]?|ml|kg|l)\b")


def _normalize_for_dedup(text: str) -> str:
    """Normalize chunk text for near-duplicate detection."""
    t = _LOCALIZATION_RE.sub("", text)
    t = _NUMBERS_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip().lower()


# ── Bilan thermique filter ────────────────────────────────────────

_THERMAL_KEYWORDS_RE = re.compile(
    r"re\s*2020|re2020|bbio|cep\b|performance\s+[ée]nerg[ée]tique"
    r"|r[ée]glementation\s+thermique|bilan\s+thermique|[ée]tude\s+thermique"
    r"|consommation\s+[ée]nerg[ée]tique|d[ée]perdition",
    re.IGNORECASE,
)

_BILAN_THERMIQUE_TYPE_RE = re.compile(
    r"fiche.technique|bilan.thermique|etude.thermique",
    re.IGNORECASE,
)

_BILAN_THERMIQUE_FILENAME_RE = re.compile(
    r"bilan|thermique|re2020|bbio",
    re.IGNORECASE,
)


def _filter_bilan_thermique(
    search_results: list[SearchResult],
    question: str,
) -> list[SearchResult]:
    """Remove bilan thermique chunks when the question is not about thermal performance.

    Bilan thermique documents describe construction elements in a simplified way
    that can mislead the LLM into describing elements absent from the actual
    CCTP/DPGF documents.

    Only checks the ORIGINAL question, not the rewritten query, because the
    rewriter often adds thermal-related terms to construction questions, which
    would falsely bypass this filter.
    """
    if _THERMAL_KEYWORDS_RE.search(question):
        return search_results

    filtered: list[SearchResult] = []
    removed = 0
    for sr in search_results:
        is_bilan = False
        if (
            sr.type
            and _BILAN_THERMIQUE_TYPE_RE.search(sr.type)
            or sr.filename
            and _BILAN_THERMIQUE_FILENAME_RE.search(sr.filename)
        ):
            is_bilan = True

        if is_bilan:
            removed += 1
            continue
        filtered.append(sr)

    if removed:
        logger.debug(
            f"[CONTEXT DEBUG] Filtered {removed} bilan thermique chunk(s) (non-thermal question)"
        )

    return filtered


# ── Main stream ──────────────────────────────────────────────────


async def chat_stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a RAG chat response as SSE events.

    1. Resolve or create conversation
    2. Persist user message
    3. Load recent history
    4. Search Qdrant for relevant chunks
    5. Build Mistral prompt (system + history + context + question)
    6. Stream response tokens as SSE
    7. Persist assistant message with sources
    """
    await project_service.get_project(db, tenant_id, project_id)

    if conversation_id:
        conv = await conversation_mod.get_conversation(db, tenant_id, conversation_id)
    else:
        title = question[:60].strip()
        conv = await conversation_mod.create_conversation(db, tenant_id, project_id, user_id, title)

    user_msg = Message(conversation_id=conv.id, role="user", content=question)
    db.add(user_msg)
    await db.commit()

    yield f"data: {json.dumps({'conversation_id': str(conv.id)})}\n\n"

    history_query = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_WINDOW + 1)
    )
    result = await db.execute(history_query)
    recent_messages = list(reversed(list(result.scalars().all())))

    history_for_rewrite = recent_messages[:-1]
    search_query, related_queries, _llm_scope, structured, schema_flag = await rewrite_query(
        question, history_for_rewrite
    )

    scope = classify_scope(question)

    if scope == "broad":
        search_limit = 20
        context_max = 48000
        score_threshold = 0.30
        max_sources = 10
        structured = "none"
        schema_flag = "none"
    else:
        search_limit = 20
        context_max = CONTEXT_MAX_CHARS
        score_threshold = 0.40
        max_sources = MAX_DISPLAYED_SOURCES

    logger.debug(
        f"[CHAT DEBUG] original='{question}' | rewritten='{search_query}' | scope={scope} | structured={structured} | schema={schema_flag}"
    )

    if schema_flag == "none" and (
        FORCED_SCHEMA_RE.search(question)
        or (search_query and FORCED_SCHEMA_RE.search(search_query))
    ):
        schema_flag = "schema"
        logger.debug("[CHAT DEBUG] Schema forced by keyword match")

    try:
        search_results = await _run_search(
            tenant_id=tenant_id,
            project_id=project_id,
            search_query=search_query,
            question=question,
            related_queries=related_queries,
            scope=scope,
            search_limit=search_limit,
        )
    except Exception:
        logger.exception("Search failed")
        yield f"data: {json.dumps({'error': 'Le service de recherche est temporairement indisponible. Veuillez réessayer dans quelques instants.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    db_context = ""
    if scope == "broad" and search_query is not None:
        db_context = await build_db_context(db, tenant_id, project_id)

    search_results = _filter_bilan_thermique(search_results, question)

    context_block, sources = _build_context_and_sources(
        search_results,
        score_threshold=score_threshold,
        context_max=context_max,
        max_sources=max_sources,
    )

    if db_context:
        context_block = f"{db_context}\n\n---\n\n{context_block}" if context_block else db_context

    mistral_messages = _build_mistral_messages(
        context_block=context_block,
        question=question,
        recent_messages=recent_messages,
        scope=scope,
        structured=structured,
        schema_flag=schema_flag,
        sources=sources,
    )

    if not context_block:
        sources = []

    table_task: asyncio.Task[StructuredTable | None] | None = None
    if structured == "table" and context_block:
        table_task = asyncio.create_task(extract_table(context_block, question))

    schema_task: asyncio.Task[StructuredSchema | None] | None = None
    if schema_flag == "schema" and context_block:
        logger.debug(
            f"[SCHEMA DEBUG] Launching schema extraction (context={len(context_block)} chars)"
        )
        schema_task = asyncio.create_task(extract_schema(context_block, question))
    else:
        logger.debug(
            f"[SCHEMA DEBUG] Schema extraction SKIPPED: flag='{schema_flag}', context={'yes' if context_block else 'no'}"
        )

    full_response = ""

    stream = await mistral_client.chat.stream_async(
        model="mistral-large-latest",
        messages=mistral_messages,
        temperature=0.1,
    )

    async for event in stream:
        token = event.data.choices[0].delta.content
        if token:
            full_response += token
            yield f"data: {json.dumps({'text': token})}\n\n"

    table: StructuredTable | None = None
    if table_task is not None:
        table = await table_task
        if table:
            yield f"data: {json.dumps({'structured': table.model_dump()})}\n\n"

    schema: StructuredSchema | None = None
    if schema_task is not None:
        schema = await schema_task
        logger.debug(
            f"[SCHEMA DEBUG] Extraction result: {schema.schema_type if schema else 'None'} | params={dict(schema.params) if schema else '{{}}'}"
        )
        if schema and schema.schema_type == "semelle_filante":
            missing = {"fond_fouille", "gros_beton", "bon_sol"} - set(schema.params)
            if missing or "fond_fouille" in schema.params:
                schema = await enrich_schema_with_search(
                    schema,
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
        if schema:
            yield f"data: {json.dumps({'schema': schema.model_dump()})}\n\n"

    if sources:
        yield f"data: {json.dumps({'sources': [s.model_dump(mode='json') for s in sources]})}\n\n"

    sources_json = json.dumps([s.model_dump(mode="json") for s in sources])
    structured_json_str = table.model_dump_json() if table else None
    schema_json_str = schema.model_dump_json() if schema else None
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=full_response,
        sources_json=sources_json,
        structured_json=structured_json_str,
        schema_json=schema_json_str,
    )
    db.add(assistant_msg)
    await db.commit()

    yield "data: [DONE]\n\n"


# ── Private helpers ──────────────────────────────────────────────


async def _run_search(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    search_query: str | None,
    question: str,
    related_queries: list[str],
    scope: str,
    search_limit: int,
) -> list[SearchResult]:
    """Execute search strategy based on scope and return results."""
    if search_query is None:
        return []

    if scope == "broad":
        broad_extra = [question] if question != search_query else []
        broad_extra.extend(related_queries)
        return await search_service.search_by_lot(
            tenant_id=tenant_id,
            project_id=project_id,
            query=search_query,
            extra_queries=broad_extra or None,
        )

    # ── Main queries (rewritten + original + LLM related) ────────
    main_queries = [search_query]
    if search_query != question:
        main_queries.append(question)
    main_queries.extend(related_queries)

    # ── Forced queries (deterministic, separate search) ──────────
    forced_queries = get_forced_related(search_query)
    logger.debug(
        f"[FORCED DEBUG] query='{search_query}' → "
        f"{len(forced_queries)} forced queries: {forced_queries}"
    )

    main_limit = max(search_limit, len(main_queries) * 5)
    search_results = await search_service.search_merged(
        tenant_id=tenant_id,
        project_id=project_id,
        queries=main_queries,
        filters=SearchFilters(),
        limit=main_limit,
    )
    logger.debug(
        f"[SEARCH DEBUG] Main search: {len(main_queries)} queries → {len(search_results)} chunks"
    )
    for i, sr in enumerate(search_results[:5]):
        logger.debug(f"  main[{i}] score={sr.score:.3f} | {sr.text[:100].replace(chr(10), ' ')}")

    if forced_queries:
        forced_results = await search_service.search_merged(
            tenant_id=tenant_id,
            project_id=project_id,
            queries=forced_queries,
            filters=SearchFilters(),
            limit=max(search_limit, len(forced_queries) * 5),
            score_threshold=0.30,
        )
        logger.debug(
            f"[FORCED DEBUG] Forced search: {len(forced_queries)} queries → "
            f"{len(forced_results)} chunks"
        )
        for i, fr in enumerate(forced_results[:8]):
            logger.debug(
                f"  forced[{i}] score={fr.score:.3f} | {fr.text[:100].replace(chr(10), ' ')}"
            )

        main_texts = {sr.text[:200] for sr in search_results}
        added = 0
        for fr in forced_results:
            if fr.text[:200] not in main_texts:
                fr.score = max(fr.score, FORCED_SCORE_FLOOR)
                search_results.append(fr)
                main_texts.add(fr.text[:200])
                added += 1
        logger.debug(
            f"[FORCED DEBUG] After dedup: {added} new chunks added, total={len(search_results)}"
        )

    search_results = await expand_heading_chunks(tenant_id, project_id, search_results)

    search_results = await enrich_with_dpgf_quantities(
        tenant_id,
        project_id,
        search_query,
        question,
        search_results,
    )

    return search_results


def _build_context_and_sources(
    search_results: list[SearchResult],
    *,
    score_threshold: float,
    context_max: int,
    max_sources: int,
) -> tuple[str, list[Source]]:
    """Build context string grouped by lot and deduplicated source list."""

    # ── Phase 1: Filter ──────────────────────────────────────────
    seen_texts: set[str] = set()
    valid_chunks: list[SearchResult] = []
    skipped_score = 0
    skipped_dedup = 0

    for sr in search_results:
        if sr.score < score_threshold and sr.type != "DPGF":
            skipped_score += 1
            continue
        text_key = sr.text[:200]
        if text_key in seen_texts:
            skipped_dedup += 1
            continue
        seen_texts.add(text_key)
        valid_chunks.append(sr)

    # ── Phase 2: Group by lot, sort by document order ────────────
    lot_groups: dict[str, list[SearchResult]] = {}
    for sr in valid_chunks:
        lot_key = sr.lot or "unknown"
        lot_groups.setdefault(lot_key, []).append(sr)

    for chunks in lot_groups.values():
        chunks.sort(key=lambda s: (s.filename or "", s.position))

    # ── Phase 3: Build context string ────────────────────────────
    context_parts: list[str] = []
    total_chars = 0
    kept_count = 0
    context_full = False
    multiple_lots = len(lot_groups) > 1
    included_chunks: list[SearchResult] = []

    for lot_key in sorted(lot_groups.keys()):
        if context_full:
            break
        if multiple_lots:
            separator = f"\n=== {lot_key} ===\n"
            if total_chars + len(separator) > context_max:
                logger.debug(
                    f"[CONTEXT DEBUG] Context full at {total_chars} chars, {kept_count} chunks kept"
                )
                break
            context_parts.append(separator)
            total_chars += len(separator)

        for sr in lot_groups[lot_key]:
            chunk_text = f"[{sr.filename}, p.{sr.page}]\n{sr.text}"
            if total_chars + len(chunk_text) > context_max:
                logger.debug(
                    f"[CONTEXT DEBUG] Context full at {total_chars} chars, {kept_count} chunks kept"
                )
                context_full = True
                break
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
            kept_count += 1
            included_chunks.append(sr)
            logger.debug(
                f"[CONTEXT DEBUG] chunk#{kept_count}: score={sr.score:.2f} lot='{lot_key}' "
                f"type={sr.type or '?'} file='{sr.filename}' p.{sr.page} "
                f"— '{sr.text[:80].replace(chr(10), ' ')}'"
            )

    # ── Phase 4: Build sources (same logic) ──────────────────────
    seen_source_keys: dict[tuple[uuid.UUID, int], int] = {}
    source_chunks: dict[int, list[tuple[int, str]]] = {}
    sources: list[Source] = []

    for sr in included_chunks:
        if len(sr.text.strip()) < MIN_SOURCE_TEXT_LENGTH:
            continue

        normalized = _normalize_for_dedup(sr.text)
        is_duplicate = False
        for _idx, chunks in source_chunks.items():
            for _, existing_text in chunks:
                if _normalize_for_dedup(existing_text) == normalized:
                    is_duplicate = True
                    break
            if is_duplicate:
                break
        if is_duplicate:
            continue

        key = (sr.document_id, sr.page)
        if key in seen_source_keys:
            idx = seen_source_keys[key]
            source_chunks[idx].append((sr.position, sr.text))
        else:
            idx = len(sources)
            seen_source_keys[key] = idx
            source_chunks[idx] = [(sr.position, sr.text)]
            sources.append(
                Source(
                    document_id=sr.document_id,
                    filename=sr.filename,
                    page=sr.page,
                    lot=sr.lot,
                    phase=sr.phase,
                    text=sr.text,
                    section_title=sr.section_title,
                )
            )

    lot_count = len(lot_groups)
    logger.debug(
        f"[CONTEXT DEBUG] Summary: {kept_count} kept, {skipped_score} below threshold, "
        f"{skipped_dedup} deduped, {total_chars} total chars, {lot_count} lot(s)"
    )

    for idx, chunks in source_chunks.items():
        chunks.sort(key=lambda c: c[0])
        sources[idx].text = "\n\n".join(text for _, text in chunks)

    sources = sources[:max_sources]

    context_block = "\n---\n".join(context_parts)
    return context_block, sources


def _build_mistral_messages(
    *,
    context_block: str,
    question: str,
    recent_messages: list[Message],
    scope: str,
    structured: str,
    schema_flag: str,
    sources: list[Source],
) -> list[dict[str, str]]:
    """Build the Mistral message list for the RAG answer."""
    system_content = SYSTEM_PROMPT
    if scope == "broad":
        system_content += (
            "\n\nQUESTION GÉNÉRALE :\n"
            "Cette question demande une vue d'ensemble. "
            "Réponds DIRECTEMENT à ce qui est demandé, sans ajouter d'informations "
            "techniques non sollicitées. "
            "PAS de bloc Localisation ni Normes pour les questions générales.\n"
            "FORMAT OBLIGATOIRE pour les questions générales :\n"
            "1. UNE phrase d'introduction courte résumant la réponse.\n"
            "2. Liste à puces (- **Élément** : détails) — un élément par ligne.\n"
            "3. OBLIGATOIRE — Terminer par une ligne vide puis la phrase EXACTE :\n"
            "   *Cette liste est basée sur les extraits consultés et peut ne pas "
            "être exhaustive.*\n\n"
            "- Si on demande une LISTE (lots, matériaux, ouvrages) : "
            "liste EXHAUSTIVE de TOUS les éléments trouvés dans le contexte, "
            "un par ligne. Pour chaque élément, inclure UNIQUEMENT les caractéristiques "
            "PRÉSENTES dans le contexte (dimensions, marque, référence, classe, norme). "
            "Si une caractéristique n'est pas dans le contexte, NE PAS la mentionner — "
            "INTERDIT d'écrire 'non précisé', 'non mentionné', 'épaisseur non précisée'. "
            "INTERDIT de déduire ou sous-entendre des matériaux absents du contexte "
            "(pas de 'sous-entendu', 'probablement', 'non explicitement cité'). "
            "Inclure UNIQUEMENT ce qui est EXPLICITEMENT écrit dans les extraits. "
            "Parcourir TOUT le contexte et extraire CHAQUE élément distinct.\n"
            "- Si on demande un RÉSUMÉ ou une VUE D'ENSEMBLE : "
            "3-5 phrases synthétiques, pas de développement par lot/ouvrage."
        )
    else:
        system_content += LOCALISATION_INSTRUCTION
    system_content += get_ouvrage_instruction(question)

    has_table = structured == "table" and context_block
    has_schema = schema_flag == "schema" and context_block
    if has_table or has_schema:
        extras: list[str] = []
        if has_table:
            extras.append(
                "un tableau récapitulatif des données chiffrées sera affiché automatiquement"
            )
        if has_schema:
            extras.append("un schéma technique en coupe sera affiché automatiquement")
        system_content += (
            "\n\nIMPORTANT — Compléments visuels : " + " et ".join(extras) + " après ta réponse. "
            "Les QUANTITÉS et MÉTRÉS (m³, m², ml, kg, U, prix) seront dans le tableau — "
            "ne les répète PAS dans ton texte. "
            "En revanche, GARDE les dimensions descriptives (section, épaisseur, format, entraxe, "
            "cotes altimétriques) dans le texte : elles caractérisent l'ouvrage.\n"
            "PERTINENCE STRICTE : n'inclus que les ouvrages du MÊME corps d'état que la question. "
            "Fondations = semelles, béton de propreté, fouilles. PAS la mise à la terre, "
            "le drainage, l'assainissement (autres lots).\n"
            "COHÉRENCE : si le contexte contient PLUSIEURS ouvrages pertinents "
            "(ex: plancher hourdis + dallage terrasse), décris-les TOUS dans le texte. "
            "Un ouvrage ne doit pas apparaître uniquement dans le tableau sans être "
            "mentionné dans ta réponse textuelle."
        )

    mistral_messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    for msg in recent_messages[:-1]:
        mistral_messages.append({"role": msg.role, "content": msg.content})

    user_turn = (
        f"Contexte extrait des documents :\n\n{context_block}\n\n---\n\nQuestion : {question}"
        if context_block
        else (
            "Aucun document pertinent n'a été trouvé dans le projet pour cette question. "
            "Réponds uniquement que tu n'as pas trouvé d'information pertinente dans les documents du projet, "
            "et suggère à l'utilisateur de reformuler sa question ou de vérifier que les documents ont bien été importés.\n\n"
            f"Question originale : {question}"
        )
    )
    mistral_messages.append({"role": "user", "content": user_turn})

    return mistral_messages
