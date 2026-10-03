"""chat_stream logging (J3): no corpus or model text at any log level, and a failing
per-question record never breaks the stream.

Reuses `test_graph.py`'s doubles. Sentinels prefixed `ZXQ` mark every piece of free text
the run handles (context chunks, table rows and title, schema reply, enriched values),
so a single substring check covers all of them.
"""

import logging
import uuid

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
