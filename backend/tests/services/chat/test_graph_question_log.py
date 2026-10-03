"""chat_stream logging (J3): no corpus or model text at any log level, and a failing
per-question record never breaks the stream.

Reuses `test_graph.py`'s doubles. Sentinels prefixed `ZXQ` mark every piece of free text
the run handles (context chunks, table rows and title, schema reply, enriched values),
so a single substring check covers all of them.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from tests.services.chat.test_graph import (
    _chunk_point,
    _kind,
    _patched_mistral,
    _patched_qdrant,
    _project_and_user,
    _rewrite_response,
    _schema_response,
    _stream,
    _table_response,
)
from tests.fakes import FakeQdrant

SENTINEL = "ZXQ"
CONTEXT_TEXT = (
    "Les semelles filantes ZXQCONTEXT sont coulées en béton armé C25/30, "
    "fond de fouille ZXQFOUILLE à -1,20 m, largeur cinquante centimètres."
)


def _leaks(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        f"{record.name}: {record.getMessage()[:120]}"
        for record in caplog.records
        if SENTINEL in record.getMessage() or SENTINEL in str(record.args)
    ]


async def test_table_question_logs_no_context_nor_table_text_at_any_level(
    db: AsyncSession, tenant_a: Tenant, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")
    project, user = await _project_and_user(db, tenant_a)
    question = "Quel type de béton pour les semelles ?"
    fake = FakeQdrant(
        [_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=CONTEXT_TEXT)]
    )
    rewrite = _rewrite_response(query=question, structured="table", schema="none")
    rows = [
        {
            "element": "Semelle ZXQROW",
            "description": "Béton armé ZXQDESC",
            "quantite": "25 ml",
            "localisation": "Fondations ZXQLOC",
        },
        {
            "element": "Semelle ZXQROW",
            "description": "doublon",
            "quantite": "",
            "localisation": "",
        },
        {
            "element": "Longrine ZXQNOQTY",
            "description": "sans quantité",
            "quantite": "",
            "localisation": "",
        },
    ]
    table_response = _table_response(title="Semelles ZXQTITLE", rows=rows)

    with (
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=rewrite, table_response=table_response),
    ):
        events = await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question
        )

    assert any(_kind(e) == "structured" for e in events)
    assert caplog.records
    assert _leaks(caplog) == []


async def test_schema_question_logs_no_context_nor_schema_text_at_any_level(
    db: AsyncSession, tenant_a: Tenant, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")
    project, user = await _project_and_user(db, tenant_a)
    question = "Quelle est la composition du fond de fouille sous les semelles ?"
    fond_id = str(uuid.uuid4())
    main_point = _chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=CONTEXT_TEXT)
    fond_point = _chunk_point(
        tenant_id=tenant_a.id,
        project_id=project.id,
        text=(
            "Gros béton de propreté épaisseur 10 cm sous les semelles filantes ZXQGROS. "
            "Bon sol : argile ZXQSOL compacte."
        ),
        point_id=fond_id,
        filename="CCTP_terrassement.pdf",
    )
    fake = FakeQdrant([main_point, fond_point], score_rounds=[{fond_id: 0.05}])
    rewrite = _rewrite_response(query=question, structured="none", schema="schema")
    schema_response = _schema_response(
        schema_type="semelle_filante",
        title="Semelle ZXQSCHEMA",
        params={"B": "50 cm", "H": "20 cm", "fond_fouille": "non précisé ZXQPARAM"},
    )

    with (
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=rewrite, schema_response=schema_response),
    ):
        events = await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question
        )

    assert any(_kind(e) == "schema" for e in events)
    assert caplog.records
    assert _leaks(caplog) == []


async def test_a_failing_question_record_never_breaks_the_stream_and_logs_a_constant_message(
    db: AsyncSession,
    tenant_a: Tenant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raising_builder(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("record build failed")

    monkeypatch.setattr("app.services.chat.graph.build_question_record", _raising_builder)
    caplog.set_level(logging.DEBUG, logger="app")
    project, user = await _project_and_user(db, tenant_a)
    question = "Quel type de béton pour les semelles ?"
    fake = FakeQdrant(
        [_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=CONTEXT_TEXT)]
    )

    with (
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=_rewrite_response(query=question)),
    ):
        events = await _stream(
            db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question=question
        )

    assert _kind(events[-1]) == "DONE"
    failures = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in failures] == ["Question log record failed"]
    assert failures[0].args == ()


@pytest.fixture
def timing_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")


async def _timed_question(
    db: AsyncSession,
    tenant: Tenant,
    *,
    question: str = "Quel type de béton pour les semelles ?",
    structured: str = "none",
    schema: str = "none",
    tokens: tuple[str, ...] = ("Une réponse.",),
    search_error: bool = False,
    broad: bool = False,
) -> dict[str, object]:
    from tests.services.chat.question_log_capture import parsed, question_records
    from tests.services.chat.test_graph import _raising_qdrant
    from tests.services.chat.test_graph_agent_v1 import _patched_mistral as agent_mistral

    project, user = await _project_and_user(db, tenant)
    fake = (
        _raising_qdrant("Search unavailable")
        if search_error
        else FakeQdrant([_chunk_point(tenant_id=tenant.id, project_id=project.id, text=CONTEXT_TEXT)])
    )
    rewrite = _rewrite_response(query=question, structured=structured, schema=schema)
    mistral = (
        agent_mistral(rewrite_response=rewrite)
        if broad
        else _patched_mistral(rewrite_response=rewrite, stream_tokens=tokens)
    )
    with question_records() as records, _patched_qdrant(fake), mistral:
        await _stream(
            db, tenant_id=tenant.id, project_id=project.id, user_id=user.id, question=question
        )
    lines = parsed(records)
    assert len(lines) == 1
    return lines[0]


def _assert_durations(record: dict[str, object], keys: tuple[str, ...]) -> None:
    for key in keys:
        value = record[key]
        assert isinstance(value, int) and value >= 0


async def test_narrow_question_record_carries_the_narrow_steps(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a)
    _assert_durations(record, (
        "rewrite_ms", "rewrite_wait_ms", "search_ms", "enrich_ms", "generate_ms",
        "generate_wait_ms", "generate_first_token_ms", "generate_stream_ms",
    ))
    assert "judge_ms" not in record
    assert "retry_search_ms" not in record


async def test_a_real_limiter_wait_reaches_the_emitted_line(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core import mistral

    now = time.monotonic()
    monkeypatch.setattr(mistral, "time", SimpleNamespace(monotonic=lambda: now))
    monkeypatch.setattr(mistral.mistral_large_limiter, "_min_interval", 4.0)
    monkeypatch.setattr(mistral.mistral_large_limiter, "_next_slot", now + 3.0)
    monkeypatch.setattr(mistral, "asyncio", SimpleNamespace(sleep=AsyncMock()))
    record = await _timed_question(db, tenant_a)
    assert record["rewrite_wait_ms"] >= 2900


async def test_first_token_ignores_an_empty_role_chunk(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.core.mistral import mistral_client
    from app.services.chat import graph

    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant([_chunk_point(tenant_id=tenant_a.id, project_id=project.id, text=CONTEXT_TEXT)])
    now = {"value": 1.0}
    monkeypatch.setattr(graph, "time", SimpleNamespace(perf_counter=lambda: now["value"]))

    async def stream_async(**kwargs: object) -> object:
        async def chunks() -> AsyncGenerator[SimpleNamespace, None]:
            for instant, token in ((1.1, ""), (2.5, "token")):
                now["value"] = instant
                yield SimpleNamespace(data=SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=token))], usage=None
                ))
            now["value"] = 3.0
        return chunks()

    from tests.services.chat.question_log_capture import parsed, question_records

    with (
        question_records() as records,
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=_rewrite_response(query="Quel béton ?")),
        patch.object(mistral_client.chat, "stream_async", side_effect=stream_async),
    ):
        await _stream(db, tenant_id=tenant_a.id, project_id=project.id, user_id=user.id, question="Quel béton ?")
    record = parsed(records)[0]
    assert record["generate_first_token_ms"] == 1500
    assert record["generate_stream_ms"] == 500


async def test_broad_retried_question_record_carries_judge_and_retry_steps(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a, question="Listez les lots du projet ?", broad=True)
    _assert_durations(record, (
        "judge_ms", "judge_wait_ms", "retry_search_ms", "enrich_ms", "enrich_retry_ms",
    ))
    assert record["retried"] is True


async def test_table_question_record_carries_parallel_generation_and_extraction(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a, structured="table")
    _assert_durations(record, ("generate_ms", "extract_table_ms", "extract_table_wait_ms"))


async def test_schema_question_record_carries_extract_schema(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a, schema="schema")
    _assert_durations(record, ("extract_schema_ms", "extract_schema_wait_ms"))


async def test_search_error_record_still_carries_the_steps_that_ran(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a, search_error=True)
    _assert_durations(record, ("rewrite_ms", "search_ms"))
    assert "generate_ms" not in record
    assert record["outcome"] == "search_error"


async def test_step_timings_add_no_text_to_the_record(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    import json

    record = await _timed_question(db, tenant_a, question="Quel béton ZXQQUESTION ?", tokens=("ZXQANSWER",))
    assert "generate_ms" in record
    assert "ZXQ" not in json.dumps(record)


async def test_no_token_records_no_generation_submeasures(
    db: AsyncSession, tenant_a: Tenant, timing_v1: None
) -> None:
    record = await _timed_question(db, tenant_a, tokens=("",))
    assert "generate_ms" in record
    assert "generate_first_token_ms" not in record
    assert "generate_stream_ms" not in record
