"""RAG chat orchestrator, built as a LangGraph state graph (J1 port).

Topology: rewrite_node -> search_node -> (error_node | enrich_node);
enrich_node fans out to generate_node + extract_table_node? + extract_schema_node?,
all three join on join_node. Steps 1/7 (conversation + message persistence)
stay outside the graph, in chat_stream() — see
docs/work/j1-langgraph-orchestration/plan.md, Decisions: db/tenant_id/project_id
are closures bound per request in _build_graph(), never state fields.
"""

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from mistralai.models import UsageInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.langsmith import configure_langsmith
from app.core.mistral import (
    MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS,
    mistral_client,
    mistral_large_limiter,
)
from app.models.message import Message
from app.schemas.chat import Source, StructuredSchema, StructuredTable
from app.schemas.search import SearchFilters, SearchResult
from app.services import project as project_service
from app.services import search as search_service
from app.services.chat import conversation as conversation_mod
from app.services.chat.chunk_enrichment import enrich_with_dpgf_quantities, expand_heading_chunks
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

configure_langsmith(settings)

logger = logging.getLogger(__name__)

SEARCH_ERROR_MESSAGE = (
    "Le service de recherche est temporairement indisponible. "
    "Veuillez réessayer dans quelques instants."
)

# ── Pure helpers, migrated unchanged from stream.py ─────────────────

_LOCALIZATION_RE = re.compile(r"(?:au droit|localisation\s*:)[^\n]*", re.IGNORECASE)
_NUMBERS_RE = re.compile(r"[\d.,]+\s*(?:m[²³23]?|ml|kg|l)\b")


def _usage_leg(usage: UsageInfo | None) -> dict[str, int | float]:
    """Token counts and USD cost for one Mistral call, zeroed if none was made."""
    input_tokens = usage.prompt_tokens or 0 if usage else 0
    output_tokens = usage.completion_tokens or 0 if usage else 0
    price = MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS
    cost_usd = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost_usd}


def _usage_event(rewrite: UsageInfo | None, generation: UsageInfo | None) -> dict[str, object]:
    """Build the {rewrite, generation, total} usage payload for the SSE stream."""
    rewrite_leg = _usage_leg(rewrite)
    generation_leg = _usage_leg(generation)
    total = {
        "input_tokens": rewrite_leg["input_tokens"] + generation_leg["input_tokens"],
        "output_tokens": rewrite_leg["output_tokens"] + generation_leg["output_tokens"],
        "cost_usd": rewrite_leg["cost_usd"] + generation_leg["cost_usd"],
    }
    return {"rewrite": rewrite_leg, "generation": generation_leg, "total": total}


def _normalize_for_dedup(text: str) -> str:
    """Normalize chunk text for near-duplicate detection."""
    t = _LOCALIZATION_RE.sub("", text)
    t = _NUMBERS_RE.sub("", t)
    return re.sub(r"\s+", " ", t).strip().lower()


_THERMAL_KEYWORDS_RE = re.compile(
    r"re\s*2020|re2020|bbio|cep\b|performance\s+[ée]nerg[ée]tique"
    r"|r[ée]glementation\s+thermique|bilan\s+thermique|[ée]tude\s+thermique"
    r"|consommation\s+[ée]nerg[ée]tique|d[ée]perdition",
    re.IGNORECASE,
)
_BILAN_THERMIQUE_TYPE_RE = re.compile(
    r"fiche.technique|bilan.thermique|etude.thermique", re.IGNORECASE
)
_BILAN_THERMIQUE_FILENAME_RE = re.compile(r"bilan|thermique|re2020|bbio", re.IGNORECASE)


def _filter_bilan_thermique(
    search_results: list[SearchResult], question: str
) -> list[SearchResult]:
    """Remove bilan thermique chunks when the question is not about thermal performance."""
    if _THERMAL_KEYWORDS_RE.search(question):
        return search_results

    filtered: list[SearchResult] = []
    for sr in search_results:
        is_bilan = bool(
            (sr.type and _BILAN_THERMIQUE_TYPE_RE.search(sr.type))
            or (sr.filename and _BILAN_THERMIQUE_FILENAME_RE.search(sr.filename))
        )
        if is_bilan:
            continue
        filtered.append(sr)
    return filtered


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

    main_queries = [search_query]
    if search_query != question:
        main_queries.append(question)
    main_queries.extend(related_queries)

    forced_queries = get_forced_related(search_query)

    main_limit = max(search_limit, len(main_queries) * 5)
    search_results = await search_service.search_merged(
        tenant_id=tenant_id,
        project_id=project_id,
        queries=main_queries,
        filters=SearchFilters(),
        limit=main_limit,
    )

    if forced_queries:
        forced_results = await search_service.search_merged(
            tenant_id=tenant_id,
            project_id=project_id,
            queries=forced_queries,
            filters=SearchFilters(),
            limit=max(search_limit, len(forced_queries) * 5),
            score_threshold=0.30,
        )
        main_texts = {sr.text[:200] for sr in search_results}
        for fr in forced_results:
            if fr.text[:200] not in main_texts:
                fr.score = max(fr.score, FORCED_SCORE_FLOOR)
                search_results.append(fr)
                main_texts.add(fr.text[:200])

    search_results = await expand_heading_chunks(tenant_id, project_id, search_results)
    search_results = await enrich_with_dpgf_quantities(
        tenant_id, project_id, search_query, question, search_results
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
    seen_texts: set[str] = set()
    valid_chunks: list[SearchResult] = []

    for sr in search_results:
        if sr.score < score_threshold and sr.type != "DPGF":
            continue
        text_key = sr.text[:200]
        if text_key in seen_texts:
            continue
        seen_texts.add(text_key)
        valid_chunks.append(sr)

    lot_groups: dict[str, list[SearchResult]] = {}
    for sr in valid_chunks:
        lot_key = sr.lot or "unknown"
        lot_groups.setdefault(lot_key, []).append(sr)

    for chunks in lot_groups.values():
        chunks.sort(key=lambda s: (s.filename or "", s.position))

    context_parts: list[str] = []
    total_chars = 0
    context_full = False
    multiple_lots = len(lot_groups) > 1
    included_chunks: list[SearchResult] = []

    for lot_key in sorted(lot_groups.keys()):
        if context_full:
            break
        if multiple_lots:
            separator = f"\n=== {lot_key} ===\n"
            if total_chars + len(separator) > context_max:
                break
            context_parts.append(separator)
            total_chars += len(separator)

        for sr in lot_groups[lot_key]:
            chunk_text = f"[{sr.filename}, p.{sr.page}]\n{sr.text}"
            if total_chars + len(chunk_text) > context_max:
                context_full = True
                break
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)
            included_chunks.append(sr)

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
    recent_messages: list[dict[str, str]],
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

    has_table = bool(structured == "table" and context_block)
    has_schema = bool(schema_flag == "schema" and context_block)
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
        mistral_messages.append({"role": msg["role"], "content": msg["content"]})

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


# ── Graph state ──────────────────────────────────────────────────


class ChatState(TypedDict, total=False):
    question: str
    history_for_rewrite: list[dict[str, str]]
    recent_messages: list[dict[str, str]]
    search_query: str | None
    related_queries: list[str]
    scope: str
    structured: str
    schema_flag: str
    search_limit: int
    context_max: int
    score_threshold: float
    max_sources: int
    search_results: list[SearchResult]
    context_block: str
    sources: list[Source]
    mistral_messages: list[dict[str, str]]
    rewrite_usage: UsageInfo | None
    generation_usage: UsageInfo | None
    full_response: str
    table: StructuredTable | None
    schema_result: StructuredSchema | None
    error: str | None


def _build_graph(*, db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> object:
    """Compiles a fresh graph, bound by closure to this one request's db/ids."""

    @traceable(name="rewrite_node")
    async def rewrite_node(state: ChatState) -> dict[str, object]:
        rewrite_usage: list[UsageInfo] = []
        history = [SimpleNamespace(**m) for m in state["history_for_rewrite"]]
        search_query, related_queries, _llm_scope, structured, schema_flag = await rewrite_query(
            state["question"], history, usage_sink=rewrite_usage
        )

        scope = classify_scope(state["question"])
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

        if schema_flag == "none" and (
            FORCED_SCHEMA_RE.search(state["question"])
            or (search_query and FORCED_SCHEMA_RE.search(search_query))
        ):
            schema_flag = "schema"

        return {
            "search_query": search_query,
            "related_queries": related_queries,
            "scope": scope,
            "structured": structured,
            "schema_flag": schema_flag,
            "search_limit": search_limit,
            "context_max": context_max,
            "score_threshold": score_threshold,
            "max_sources": max_sources,
            "rewrite_usage": rewrite_usage[0] if rewrite_usage else None,
        }

    @traceable(name="search_node")
    async def search_node(state: ChatState) -> dict[str, object]:
        try:
            search_results = await _run_search(
                tenant_id=tenant_id,
                project_id=project_id,
                search_query=state["search_query"],
                question=state["question"],
                related_queries=state["related_queries"],
                scope=state["scope"],
                search_limit=state["search_limit"],
            )
        except Exception:
            logger.exception("Search failed")
            return {"error": SEARCH_ERROR_MESSAGE}
        return {"search_results": search_results}

    @traceable(name="enrich_node")
    async def enrich_node(state: ChatState) -> dict[str, object]:
        db_context = ""
        if state["scope"] == "broad" and state["search_query"] is not None:
            db_context = await build_db_context(db, tenant_id, project_id)

        filtered = _filter_bilan_thermique(state["search_results"], state["question"])
        context_block, sources = _build_context_and_sources(
            filtered,
            score_threshold=state["score_threshold"],
            context_max=state["context_max"],
            max_sources=state["max_sources"],
        )
        if db_context:
            context_block = (
                f"{db_context}\n\n---\n\n{context_block}" if context_block else db_context
            )

        mistral_messages = _build_mistral_messages(
            context_block=context_block,
            question=state["question"],
            recent_messages=state["recent_messages"],
            scope=state["scope"],
            structured=state["structured"],
            schema_flag=state["schema_flag"],
            sources=sources,
        )
        if not context_block:
            sources = []

        return {
            "context_block": context_block,
            "sources": sources,
            "mistral_messages": mistral_messages,
        }

    @traceable(name="generate_node")
    async def generate_node(state: ChatState) -> dict[str, object]:
        writer = get_stream_writer()
        full_response = ""
        generation_usage: UsageInfo | None = None

        await mistral_large_limiter.wait()
        stream = await mistral_client.chat.stream_async(
            model="mistral-large-latest",
            messages=state["mistral_messages"],
            temperature=0.1,
        )
        async for event in stream:
            token = event.data.choices[0].delta.content
            if token:
                full_response += token
                writer({"text": token})
            if event.data.usage is not None:
                generation_usage = event.data.usage

        return {"full_response": full_response, "generation_usage": generation_usage}

    @traceable(name="extract_table_node")
    async def extract_table_node(state: ChatState) -> dict[str, object]:
        table = await extract_table(state["context_block"], state["question"])
        return {"table": table}

    @traceable(name="extract_schema_node")
    async def extract_schema_node(state: ChatState) -> dict[str, object]:
        schema = await extract_schema(state["context_block"], state["question"])
        if schema and schema.schema_type == "semelle_filante":
            missing = {"fond_fouille", "gros_beton", "bon_sol"} - set(schema.params)
            if missing or "fond_fouille" in schema.params:
                schema = await enrich_schema_with_search(
                    schema, tenant_id=tenant_id, project_id=project_id
                )
        return {"schema_result": schema}

    async def error_node(state: ChatState) -> dict[str, object]:
        writer = get_stream_writer()
        writer({"error": state["error"]})
        return {}

    async def join_node(state: ChatState) -> dict[str, object]:
        writer = get_stream_writer()

        table = state.get("table")
        if table:
            writer({"structured": table.model_dump()})

        schema = state.get("schema_result")
        if schema:
            writer({"schema": schema.model_dump()})

        sources = state.get("sources") or []
        if sources:
            writer({"sources": [s.model_dump(mode="json") for s in sources]})

        writer(
            {
                "__final__": {
                    "full_response": state.get("full_response", ""),
                    "sources": sources,
                    "table": table,
                    "schema": schema,
                    "rewrite_usage": state.get("rewrite_usage"),
                    "generation_usage": state.get("generation_usage"),
                }
            }
        )
        return {}

    def _route_after_search(state: ChatState) -> str:
        return "error_node" if state.get("error") else "enrich_node"

    def _route_after_enrich(state: ChatState) -> list[str]:
        targets = ["generate_node"]
        if state["structured"] == "table" and state["context_block"]:
            targets.append("extract_table_node")
        if state["schema_flag"] == "schema" and state["context_block"]:
            targets.append("extract_schema_node")
        return targets

    builder = StateGraph(ChatState)
    builder.add_node("rewrite_node", rewrite_node)
    builder.add_node("search_node", search_node)
    builder.add_node("enrich_node", enrich_node)
    builder.add_node("generate_node", generate_node)
    builder.add_node("extract_table_node", extract_table_node)
    builder.add_node("extract_schema_node", extract_schema_node)
    builder.add_node("error_node", error_node)
    builder.add_node("join_node", join_node)

    builder.add_edge(START, "rewrite_node")
    builder.add_edge("rewrite_node", "search_node")
    builder.add_conditional_edges("search_node", _route_after_search, ["error_node", "enrich_node"])
    builder.add_conditional_edges(
        "enrich_node",
        _route_after_enrich,
        ["generate_node", "extract_table_node", "extract_schema_node"],
    )
    builder.add_edge("generate_node", "join_node")
    builder.add_edge("extract_table_node", "join_node")
    builder.add_edge("extract_schema_node", "join_node")
    builder.add_edge("error_node", END)
    builder.add_edge("join_node", END)

    return builder.compile(checkpointer=InMemorySaver())


async def chat_stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    conversation_id: uuid.UUID | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a RAG chat response as SSE events — LangGraph-orchestrated (J1)."""
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
    recent_rows = list(reversed(list(result.scalars().all())))
    recent_messages = [{"role": m.role, "content": m.content} for m in recent_rows]
    history_for_rewrite = recent_messages[:-1]

    graph = _build_graph(db=db, tenant_id=tenant_id, project_id=project_id)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    initial_state: ChatState = {
        "question": question,
        "history_for_rewrite": history_for_rewrite,
        "recent_messages": recent_messages,
    }

    final_payload: dict[str, object] | None = None
    error_message: str | None = None

    async for chunk in graph.astream(initial_state, config, stream_mode="custom"):
        if "__final__" in chunk:
            final_payload = chunk["__final__"]
            continue
        if "error" in chunk:
            error_message = str(chunk["error"])
        yield f"data: {json.dumps(chunk)}\n\n"

    if error_message is not None:
        yield "data: [DONE]\n\n"
        return

    assert final_payload is not None
    sources: list[Source] = final_payload["sources"]  # type: ignore[assignment]
    table: StructuredTable | None = final_payload["table"]  # type: ignore[assignment]
    schema: StructuredSchema | None = final_payload["schema"]  # type: ignore[assignment]

    sources_json = json.dumps([s.model_dump(mode="json") for s in sources])
    structured_json_str = table.model_dump_json() if table else None
    schema_json_str = schema.model_dump_json() if schema else None
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=final_payload["full_response"],
        sources_json=sources_json,
        structured_json=structured_json_str,
        schema_json=schema_json_str,
    )
    db.add(assistant_msg)
    await db.commit()

    usage_event = _usage_event(final_payload["rewrite_usage"], final_payload["generation_usage"])  # type: ignore[arg-type]
    yield f"data: {json.dumps({'usage': usage_event})}\n\n"
    yield "data: [DONE]\n\n"
