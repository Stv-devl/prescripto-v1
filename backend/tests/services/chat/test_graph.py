"""The LangGraph chat orchestrator — proves the graph reproduces `stream.py`'s
observable contract (SSE sequence, persistence, isolation) with the same
`chat_stream()` signature, not that any particular node exists.

Boundary mocked, nothing below it: `mistral_client.chat.{complete_async,stream_async}`
and `mistral_client.embeddings.create_async` are patched once, in place, on the
shared singleton (`app/core/mistral.py`) — every module that imported that same
object (`query_rewrite.py`, `table_extraction.py`, `schema_extraction.py`, the
future `graph.py`) sees the patch, because they all hold a reference to the one
`Mistral` instance, not a copy. `rewrite_query`, `extract_table`, `extract_schema`
and `enrich_schema_with_search` therefore run for real: only the network edge is
a double. Same idea for Qdrant, following `test_chunk_enrichment.py`'s own
pattern — `FakeQdrant` patched onto every module that imports `qdrant_client`
(`app/services/search.py`, `chunk_enrichment.py`, `context_enrichment.py`).

Where a business rule's only externally visible trace is "was this LLM call
made at all" (an empty context must not launch table/schema extraction; the
shared rate limiter must gate every real Mistral call), the call log kept by
`_patched_mistral` is inspected — the same exception `05-testing.md` grants
`test_chunk_enrichment.py` for a Qdrant filter: no other observable trace
exists, because a call that is launched but degrades to nothing produces the
same SSE stream as a call never made at all.
"""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from mistralai.models import UsageInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mistral import mistral_client, mistral_large_limiter
from app.models.document import Document
from app.models.message import Message
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.user import User
from app.services import project as project_service
from app.services.chat.prompts import REWRITE_PROMPT, SCHEMA_EXTRACTION_PROMPT, TABLE_EXTRACTION_PROMPT
from tests.fakes import FakePoint, FakeQdrant

QUESTION = "Quel est le type de béton utilisé pour les fondations ?"
MAIN_CHUNK_TEXT = (
    "Les semelles filantes de ce chantier sont coulées en béton armé C25/30, "
    "avec une largeur de cinquante centimètres et une hauteur de vingt centimètres."
)
STREAM_TOKENS = ("Les fondations ", "sont en béton armé C25/30.")
SEARCH_ERROR_MESSAGE = (
    "Le service de recherche est temporairement indisponible. "
    "Veuillez réessayer dans quelques instants."
)


# ── Setup helpers ─────────────────────────────────────────────────


async def _project_and_user(db: AsyncSession, tenant: Tenant) -> tuple[Project, User]:
    project = await project_service.create_project(db, tenant.id, name="Chantier", phase="PRO")
    user = User(
        tenant_id=tenant.id,
        email=f"eco-{uuid.uuid4()}@cabinet.fr",
        hashed_password="not-a-real-hash",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return project, user


def _chunk_point(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    text: str,
    point_id: str | None = None,
    document_id: uuid.UUID | None = None,
    filename: str = "CCTP_fondations.pdf",
    page: int = 12,
    position: int = 5,
    lot: str = "01 - Gros oeuvre",
    phase: str = "PRO",
    type_: str = "CCTP",
    content_type: str = "description",
    score: float = 0.9,
) -> FakePoint:
    return FakePoint(
        id=point_id or str(uuid.uuid4()),
        score=score,
        payload={
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "document_id": str(document_id or uuid.uuid4()),
            "text": text,
            "page": page,
            "position": position,
            "filename": filename,
            "lot": lot,
            "phase": phase,
            "type": type_,
            "content_type": content_type,
        },
    )


@contextmanager
def _patched_qdrant(fake: object) -> Iterator[object]:
    """Patches the Qdrant double onto every module that imports the singleton.

    Mirrors `test_chunk_enrichment.py`: `graph.py` reaches Qdrant only through
    `search.py`/`chunk_enrichment.py`/`context_enrichment.py`, never directly.
    """
    with (
        patch("app.services.search.qdrant_client", fake),
        patch("app.services.chat.chunk_enrichment.qdrant_client", fake),
        patch("app.services.chat.context_enrichment.qdrant_client", fake),
    ):
        yield fake


def _raising_qdrant(message: str) -> MagicMock:
    """A Qdrant double whose first `.search()` call raises, for the search-failure case."""
    double = MagicMock()
    double.search = AsyncMock(side_effect=RuntimeError(message))
    return double


def _rewrite_response(
    *,
    query: str,
    related: list[str] | None = None,
    structured: str = "none",
    schema: str = "none",
) -> SimpleNamespace:
    content = json.dumps(
        {"query": query, "related": related or [], "structured": structured, "schema": schema}
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None
    )


def _table_response(
    *, title: str, rows: list[dict[str, str]], columns: list[str] | None = None
) -> SimpleNamespace:
    content = json.dumps(
        {
            "title": title,
            "columns": columns or ["Élément", "Description", "Quantité", "Localisation"],
            "rows": rows,
        }
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None
    )


def _schema_response(*, schema_type: str, title: str, params: dict[str, str]) -> SimpleNamespace:
    content = json.dumps({"schema_type": schema_type, "title": title, "params": params})
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None
    )


_DEFAULT_TABLE_RESPONSE = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(content='{"skip": true}'))], usage=None
)
_DEFAULT_SCHEMA_RESPONSE = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(content='{"schema_type": "none"}'))],
    usage=None,
)


@contextmanager
def _patched_mistral(
    *,
    rewrite_response: SimpleNamespace,
    table_response: SimpleNamespace | None = None,
    schema_response: SimpleNamespace | None = None,
    stream_tokens: tuple[str, ...] = STREAM_TOKENS,
    generation_usage: UsageInfo | None = None,
    complete_calls: list[str] | None = None,
) -> Iterator[AsyncMock]:
    """Patches the three Mistral edges in place on the shared singleton.

    `complete_calls`, when given, records which system prompt each
    `complete_async` call carried ("rewrite"/"table"/"schema") — the only trace
    of whether a node was launched at all when it degrades to nothing.
    """
    log = complete_calls if complete_calls is not None else []

    async def _complete_async(*, model: str, messages: list[dict[str, str]], **kwargs: object):
        system = messages[0]["content"]
        if system == REWRITE_PROMPT:
            log.append("rewrite")
            return rewrite_response
        if system == TABLE_EXTRACTION_PROMPT:
            log.append("table")
            return table_response if table_response is not None else _DEFAULT_TABLE_RESPONSE
        if system == SCHEMA_EXTRACTION_PROMPT:
            log.append("schema")
            return schema_response if schema_response is not None else _DEFAULT_SCHEMA_RESPONSE
        raise AssertionError(f"unexpected system prompt sent to complete_async: {system[:80]!r}")

    def _stream_async(*, model: str, messages: list[dict[str, str]], **kwargs: object):
        async def _gen() -> object:
            n = len(stream_tokens)
            for i, token in enumerate(stream_tokens):
                yield SimpleNamespace(
                    data=SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=token))],
                        usage=generation_usage if i == n - 1 else None,
                    )
                )

        return _gen()

    async def _create_async(*, model: str, inputs: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0, 0.0]) for _ in inputs])

    with (
        patch.object(mistral_client.chat, "complete_async", side_effect=_complete_async),
        patch.object(mistral_client.chat, "stream_async", side_effect=_stream_async) as stream_mock,
        patch.object(mistral_client.embeddings, "create_async", side_effect=_create_async),
    ):
        yield stream_mock


def _parse_events(lines: list[str]) -> list[dict[str, object] | str]:
    events: list[dict[str, object] | str] = []
    for line in lines:
        assert line.startswith("data: ") and line.endswith("\n\n"), f"malformed SSE line: {line!r}"
        payload = line[len("data: ") : -2]
        events.append("DONE" if payload == "[DONE]" else json.loads(payload))
    return events


def _kind(event: dict[str, object] | str) -> str:
    if event == "DONE":
        return "DONE"
    assert isinstance(event, dict) and len(event) == 1, f"not a single-key SSE event: {event!r}"
    return next(iter(event))


async def _stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str = QUESTION,
) -> list[dict[str, object] | str]:
    from app.services.chat.graph import chat_stream

    lines = [
        line
        async for line in chat_stream(
            db,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            question=question,
        )
    ]
    return _parse_events(lines)


async def _happy_path(db: AsyncSession, tenant: Tenant) -> tuple[list[dict[str, object] | str], Project]:
    project, user = await _project_and_user(db, tenant)
    fake = FakeQdrant([_chunk_point(tenant_id=tenant.id, project_id=project.id, text=MAIN_CHUNK_TEXT)])
    rewrite = _rewrite_response(query=QUESTION)
    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite):
        events = await _stream(db, tenant_id=tenant.id, project_id=project.id, user_id=user.id)
    return events, project


# ── Core behaviour ────────────────────────────────────────────────


async def test_happy_path_emits_exact_event_sequence(db: AsyncSession, tenant_a: Tenant) -> None:
    events, _ = await _happy_path(db, tenant_a)

    assert [_kind(e) for e in events] == [
        "conversation_id",
        "text",
        "text",
        "sources",
        "usage",
        "DONE",
    ]


async def test_happy_path_accumulated_text_equals_concatenated_stream_tokens(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    events, _ = await _happy_path(db, tenant_a)

    text_events = [e["text"] for e in events if _kind(e) == "text"]
    assert "".join(text_events) == "".join(STREAM_TOKENS)


async def test_happy_path_commits_assistant_message_with_content_and_sources(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    events, _ = await _happy_path(db, tenant_a)
    conv_id = uuid.UUID(str(events[0]["conversation_id"]))

    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
    )
    assistant_msg = result.scalar_one()

    assert assistant_msg.content == "".join(STREAM_TOKENS)
    sources = json.loads(assistant_msg.sources_json)
    assert len(sources) == 1
    assert sources[0]["filename"] == "CCTP_fondations.pdf"


async def test_usage_leg_of_none_is_all_zeros() -> None:
    from app.services.chat.graph import _usage_leg

    assert _usage_leg(None) == {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


async def test_usage_leg_of_one_million_input_half_million_output_costs_1_25_usd() -> None:
    from app.services.chat.graph import _usage_leg

    usage = UsageInfo(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)

    assert _usage_leg(usage) == {"input_tokens": 1_000_000, "output_tokens": 500_000, "cost_usd": 1.25}


async def test_usage_leg_with_missing_prompt_tokens_counts_zero_input() -> None:
    from app.services.chat.graph import _usage_leg

    usage = UsageInfo(prompt_tokens=None, completion_tokens=2_000_000, total_tokens=2_000_000)

    assert _usage_leg(usage) == {"input_tokens": 0, "output_tokens": 2_000_000, "cost_usd": 3.0}


async def test_usage_event_of_two_nones_zeroes_rewrite_generation_and_total() -> None:
    from app.services.chat.graph import _usage_event

    zero = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    assert _usage_event(None, None) == {"rewrite": zero, "generation": zero, "total": zero}


async def test_usage_event_with_only_generation_leaves_rewrite_zero_and_total_equal_generation() -> (
    None
):
    from app.services.chat.graph import _usage_event

    generation = UsageInfo(prompt_tokens=200_000, completion_tokens=100_000, total_tokens=300_000)
    event = _usage_event(None, generation)

    assert event["rewrite"] == {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    assert event["generation"] == {"input_tokens": 200_000, "output_tokens": 100_000, "cost_usd": 0.25}
    assert event["total"] == event["generation"]


async def test_usage_event_with_both_legs_sums_into_total() -> None:
    from app.services.chat.graph import _usage_event

    rewrite = UsageInfo(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)
    generation = UsageInfo(prompt_tokens=200_000, completion_tokens=100_000, total_tokens=300_000)

    event = _usage_event(rewrite, generation)

    assert event["total"] == {"input_tokens": 1_200_000, "output_tokens": 600_000, "cost_usd": 1.5}


# ── Business rules ────────────────────────────────────────────────


async def test_search_failure_emits_three_event_error_sequence_without_persisting_assistant_message(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    rewrite = _rewrite_response(query=QUESTION)

    with _patched_qdrant(_raising_qdrant("Qdrant unreachable")), _patched_mistral(rewrite_response=rewrite):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    assert [_kind(e) for e in events] == ["conversation_id", "error", "DONE"]
    assert events[1]["error"] == SEARCH_ERROR_MESSAGE

    conv_id = uuid.UUID(str(events[0]["conversation_id"]))
    result = await db.execute(select(Message).where(Message.conversation_id == conv_id))
    roles = {m.role for m in result.scalars().all()}
    assert roles == {"user"}


async def test_build_db_context_only_runs_for_broad_scope_and_precedes_chunk_context(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    db.add(Document(project_id=project.id, filename="DPGF_carrelage.xlsx", type="DPGF", lot="07 - Revêtements"))
    await db.commit()

    broad_text = "Le lot Gros œuvre comprend les fondations et l'ossature béton du bâtiment principal."
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=broad_text)])

    # Specific scope: the DB-lot marker must never reach the generation prompt.
    specific_question = "Quel est le type de béton des fondations ?"
    rewrite_specific = _rewrite_response(query=specific_question)
    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite_specific) as stream_mock:
        await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=specific_question
        )
    specific_messages = stream_mock.call_args.kwargs["messages"]
    specific_prompt = "\n".join(m["content"] for m in specific_messages)
    assert "07 - Revêtements" not in specific_prompt

    # Broad scope: the DB-lot marker precedes the chunk text in the same prompt.
    broad_question = "Quels sont les documents du projet ?"
    rewrite_broad = _rewrite_response(query=broad_question)
    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite_broad) as stream_mock:
        await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=broad_question
        )
    broad_messages = stream_mock.call_args.kwargs["messages"]
    broad_prompt = "\n".join(m["content"] for m in broad_messages)
    assert "07 - Revêtements" in broad_prompt
    assert broad_prompt.index("07 - Revêtements") < broad_prompt.index("Gros œuvre comprend les fondations")


async def test_broad_scope_resets_structured_and_schema_unless_forced_schema_keyword_matches(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    question = "Quels sont les lots concernant le dallage du projet ?"
    chunk_text = "Le dallage sur terre-plein comprend une dalle en béton armé de quinze centimètres."
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=chunk_text)])
    # The LLM rewrite asked for a table too, and it must be reset by the broad scope.
    rewrite = _rewrite_response(query=question, structured="table", schema="none")
    schema_response = _schema_response(
        schema_type="dallage_terre_plein", title="Dallage", params={"epaisseur_totale": "54 cm"}
    )

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, schema_response=schema_response):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question)

    kinds = [_kind(e) for e in events]
    assert "structured" not in kinds
    assert "schema" in kinds
    schema_event = next(e for e in events if _kind(e) == "schema")
    assert schema_event["schema"] == {
        "schema_type": "dallage_terre_plein",
        "title": "Dallage",
        "params": {"epaisseur_totale": "54 cm"},
    }


async def test_bilan_thermique_chunks_are_dropped_unless_question_matches_thermal_keywords(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    bilan_text = (
        "Fiche technique du bilan thermique RE2020 : Bbio et Cep du bâtiment principal, "
        "avec le détail des déperditions par paroi."
    )
    points = [
        _chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT),
        _chunk_point(
            tenant_id=tenant_a.id,
            project_id=project.id,
            text=bilan_text,
            filename="Bilan_thermique_RE2020.pdf",
            type_="etude_thermique",
        ),
    ]

    # Non-thermal question: the bilan thermique chunk must be filtered out.
    non_thermal_question = "Quel est le type de béton des fondations ?"
    fake_1 = FakeQdrant(list(points))
    rewrite_1 = _rewrite_response(query=non_thermal_question)
    with _patched_qdrant(fake_1), _patched_mistral(rewrite_response=rewrite_1) as stream_mock:
        await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=non_thermal_question
        )
    prompt_1 = "\n".join(m["content"] for m in stream_mock.call_args.kwargs["messages"])
    assert "Bbio" not in prompt_1

    # Thermal question: the bilan thermique chunk is kept.
    thermal_question = "Quelle est la performance énergétique (RE2020) du bâtiment ?"
    fake_2 = FakeQdrant(list(points))
    rewrite_2 = _rewrite_response(query=thermal_question)
    with _patched_qdrant(fake_2), _patched_mistral(rewrite_response=rewrite_2) as stream_mock:
        await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=thermal_question
        )
    prompt_2 = "\n".join(m["content"] for m in stream_mock.call_args.kwargs["messages"])
    assert "Bbio" in prompt_2


async def test_table_event_is_emitted_from_extract_table_result_when_structured_table_and_context(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    question = "Quel type de béton pour les semelles ?"
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT)])
    rewrite = _rewrite_response(query=question, structured="table", schema="none")
    rows = [
        {
            "element": "Semelle filante",
            "description": "Béton armé C25/30",
            "quantite": "25 ml",
            "localisation": "Fondations",
        },
        {
            "element": "Béton de propreté",
            "description": "Sous semelles",
            "quantite": "5 m3",
            "localisation": "Fondations",
        },
    ]
    table_response = _table_response(title="Semelles", rows=rows)

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, table_response=table_response):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question)

    structured_event = next(e for e in events if _kind(e) == "structured")
    assert structured_event["structured"] == {
        "title": "Semelles",
        "columns": ["Élément", "Description", "Quantité", "Localisation"],
        "rows": rows,
    }


async def test_schema_event_reflects_enrichment_when_semelle_filante_and_fond_fouille_present(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    """`fond_fouille` present (with `gros_beton`/`bon_sol` missing) must trigger
    `enrich_schema_with_search`'s own targeted Qdrant search, run for real.

    The "fond de fouille" chunk is scored below threshold for the very first
    Qdrant `.search()` call of the run (the main context search) and at its
    normal score for every later call, so it never contaminates the main
    context (which would let `extract_schema`'s own context-regex enrichment
    fill the fields first) yet is found by the enrichment's own search.

    `fond_fouille` itself does not survive into the final params: verified
    directly against `schema_extraction._strip_non_precise` (unchanged by
    this port, and run *inside* `extract_schema` before it ever returns) —
    its `_NON_PRECISE_RE` treats a leading minus sign as the "non précisé"
    placeholder pattern (`|—|-)\\b`), so a negative altimetric cote like
    "-1,33 m / TN" is stripped as if it were absent. Pre-existing defect, out
    of J1's scope (`.claude/.tdd-unfrozen`, 2026-09-18). The enrichment still
    triggers here — not via `"fond_fouille" in schema.params` (already false,
    stripped), but via the sibling `missing` branch: with `fond_fouille` gone
    too, all three of `{fond_fouille, gros_beton, bon_sol}` are missing.
    """
    project, user = await _project_and_user(db, tenant_a)
    question = "Quelle est la composition du fond de fouille sous les semelles ?"
    fond_id = str(uuid.uuid4())
    main_point = _chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT)
    fond_point = _chunk_point(
        tenant_id=tenant_a.id,
        project_id=project.id,
        text=(
            "Gros béton de propreté épaisseur 10 cm sous les semelles filantes. "
            "Bon sol : argile compacte."
        ),
        point_id=fond_id,
        filename="CCTP_terrassement.pdf",
    )
    fake = FakeQdrant([main_point, fond_point], score_rounds=[{fond_id: 0.05}])
    rewrite = _rewrite_response(query=question, structured="none", schema="schema")
    schema_response = _schema_response(
        schema_type="semelle_filante",
        title="Semelle filante",
        params={"B": "50 cm", "H": "20 cm", "fond_fouille": "-1,33 m / TN"},
    )

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, schema_response=schema_response):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question)

    schema_event = next(e for e in events if _kind(e) == "schema")
    assert schema_event["schema"] == {
        "schema_type": "semelle_filante",
        "title": "Semelle filante",
        "params": {
            "B": "50 cm",
            "H": "20 cm",
            "gros_beton": "10 cm",
            "bon_sol": "argile compacte",
        },
    }


async def test_empty_search_results_emit_no_sources_and_skip_extraction_tasks_but_still_generate(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant([])  # no chunk anywhere in the store
    rewrite = _rewrite_response(query=QUESTION, structured="table", schema="schema")
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, complete_calls=calls):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    kinds = [_kind(e) for e in events]
    assert "sources" not in kinds
    assert "structured" not in kinds
    assert "schema" not in kinds
    assert "text" in kinds
    assert kinds[-1] == "DONE"
    # The only trace that the extraction tasks were never launched at all
    # (not launched-then-degraded-to-nothing): they never called Mistral.
    assert "table" not in calls
    assert "schema" not in calls

    conv_id = uuid.UUID(str(events[0]["conversation_id"]))
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
    )
    assert json.loads(result.scalar_one().sources_json) == []


async def test_mistral_rate_limiter_is_awaited_once_per_mistral_call_across_rewrite_generation_table_and_schema(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT)])
    rewrite = _rewrite_response(query=QUESTION, structured="table", schema="schema")
    table_response = _table_response(
        title="Semelles",
        rows=[{"element": "Semelle", "description": "Béton armé", "quantite": "10 ml", "localisation": "RDC"}],
    )
    schema_response = _schema_response(
        schema_type="toiture_terrasse", title="Toiture", params={"type_toiture": "étanchéité bitumineuse"}
    )

    with (
        patch.object(mistral_large_limiter, "wait", new_callable=AsyncMock) as wait_mock,
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=rewrite, table_response=table_response, schema_response=schema_response),
    ):
        await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    # rewrite + generation + table + schema: one wait() per real Mistral call.
    # A node that built its own `_RateLimiter()` instead of using the shared
    # one would make this count come out lower, never right by accident.
    assert wait_mock.await_count == 4


async def test_cross_tenant_chunks_never_leak_into_context_or_sources(
    db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    own_text = (
        "Les fondations du tenant A sont réalisées en béton armé C25/30, "
        "largeur cinquante centimètres, hauteur vingt centimètres."
    )
    foreign_text = (
        "SECRET_TENANT_B_TEXT : ce contenu appartient au tenant B et ne doit jamais "
        "apparaître dans une réponse fournie au tenant A."
    )
    points = [
        _chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=own_text, filename="own.pdf"),
        # Same project_id as tenant A's project: only the tenant_id filter protects isolation.
        _chunk_point(tenant_id=tenant_b.id, project_id=project.id, text=foreign_text, filename="foreign.pdf"),
    ]
    fake = FakeQdrant(points)
    rewrite = _rewrite_response(query=QUESTION)

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite) as stream_mock:
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    prompt = "\n".join(m["content"] for m in stream_mock.call_args.kwargs["messages"])
    assert "SECRET_TENANT_B_TEXT" not in prompt
    assert "béton armé C25/30" in prompt

    sources_event = next(e for e in events if _kind(e) == "sources")
    assert [s["filename"] for s in sources_event["sources"]] == ["own.pdf"]


# ── Edge cases ────────────────────────────────────────────────────


async def test_extract_schema_exception_degrades_silently_without_schema_event(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT)])
    rewrite = _rewrite_response(query=QUESTION, structured="none", schema="schema")
    # Unparsable content makes extract_schema's own json.loads raise, caught internally.
    broken_schema_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not valid json at all"))], usage=None
    )

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, schema_response=broken_schema_response):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    kinds = [_kind(e) for e in events]
    assert "schema" not in kinds
    assert kinds[-1] == "DONE"
    assert "text" in kinds


async def test_extract_table_exception_degrades_silently_without_structured_event(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=MAIN_CHUNK_TEXT)])
    rewrite = _rewrite_response(query=QUESTION, structured="table", schema="none")
    broken_table_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not valid json at all"))], usage=None
    )

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite, table_response=broken_table_response):
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    kinds = [_kind(e) for e in events]
    assert "structured" not in kinds
    assert kinds[-1] == "DONE"
    assert "text" in kinds


async def test_sources_empty_when_all_chunks_filtered_but_context_stays_non_empty(
    db: AsyncSession, tenant_a: Tenant
) -> None:
    project, user = await _project_and_user(db, tenant_a)
    # Short enough (< 80 chars) to be dropped from sources, long enough to stay in context.
    short_text = "Béton C25/30."
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=short_text)])
    rewrite = _rewrite_response(query=QUESTION)

    with _patched_qdrant(fake), _patched_mistral(rewrite_response=rewrite) as stream_mock:
        events = await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id)

    assert "sources" not in [_kind(e) for e in events]
    prompt = "\n".join(m["content"] for m in stream_mock.call_args.kwargs["messages"])
    assert "Béton C25/30." in prompt

    conv_id = uuid.UUID(str(events[0]["conversation_id"]))
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id, Message.role == "assistant")
    )
    assert json.loads(result.scalar_one().sources_json) == []
