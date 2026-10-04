"""Order in which one chat question passes the shared Mistral rate limiters.

The only observable trace of the choice "generation reserves the large limiter
before the extractions" is the order of the `wait()` passages, recorded here by
step name, so the call log is the assertion (same exception as `test_graph.py`).
"""

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import timing
from app.core.mistral import mistral_fast_limiter, mistral_large_limiter
from app.models.tenant import Tenant
from tests.fakes import FakeQdrant
from tests.services.chat.test_graph import (
    _chunk_point,
    _patched_mistral,
    _patched_qdrant,
    _project_and_user,
    _rewrite_response,
    _schema_response,
    _stream,
    _table_response,
)

NARROW_QUESTION = "Quel type de béton pour les semelles ?"
TABLE_TITLE = "Béton des semelles filantes"
CONTEXT_TEXT = (
    "Les semelles filantes sont coulées en béton armé C25/30, "
    "largeur cinquante centimètres, hauteur vingt centimètres."
)


@dataclass
class _Passages:
    large: list[str | None]
    fast: list[str | None]


@contextmanager
def _recorded_limiters() -> Iterator[_Passages]:
    passages = _Passages(large=[], fast=[])

    async def _large() -> None:
        passages.large.append(timing.current_step())

    async def _fast() -> None:
        passages.fast.append(timing.current_step())

    with (
        patch.object(mistral_large_limiter, "wait", new_callable=AsyncMock, side_effect=_large),
        patch.object(mistral_fast_limiter, "wait", new_callable=AsyncMock, side_effect=_fast),
    ):
        yield passages


def _pin_settings(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", mode)
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")


def _fake_qdrant(tenant_id: uuid.UUID, project_id: uuid.UUID) -> FakeQdrant:
    return FakeQdrant([_chunk_point(tenant_id=tenant_id, project_id=project_id, text=CONTEXT_TEXT)])


def _table() -> object:
    return _table_response(
        title=TABLE_TITLE,
        rows=[
            {
                "element": "Semelle filante",
                "description": "Béton armé C25/30",
                "quantite": "25 ml",
                "localisation": "Fondations",
            }
        ],
    )


def _schema() -> object:
    return _schema_response(
        schema_type="dallage_terre_plein", title="Dallage", params={"epaisseur_totale": "54 cm"}
    )


async def _passages_for(
    db: AsyncSession,
    tenant: Tenant,
    *,
    structured: str,
    schema: str,
) -> _Passages:
    project, user = await _project_and_user(db, tenant)
    with (
        _recorded_limiters() as passages,
        _patched_qdrant(_fake_qdrant(tenant.id, project.id)),
        _patched_mistral(
            rewrite_response=_rewrite_response(
                query=NARROW_QUESTION, structured=structured, schema=schema
            ),
            table_response=_table(),
            schema_response=_schema(),
        ),
    ):
        await _stream(
            db,
            tenant_id=tenant.id,
            project_id=project.id,
            user_id=user.id,
            question=NARROW_QUESTION,
        )
    return passages


# ── Core behaviour ────────────────────────────────────────────────


async def test_v1_table_and_schema_question_reserves_the_generation_before_both_extractions(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "v1")

    passages = await _passages_for(db, tenant_a, structured="table", schema="schema")

    large = passages.large
    assert len(large) == 4, f"large limiter passages: {large}"
    assert large[:2] == ["rewrite", "generate"], f"large limiter passages: {large}"
    assert set(large[2:]) == {"extract_table", "extract_schema"}, f"large limiter passages: {large}"


async def test_v1_table_question_reserves_the_generation_before_the_table_extraction(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "v1")

    passages = await _passages_for(db, tenant_a, structured="table", schema="none")

    assert passages.large == ["rewrite", "generate", "extract_table"], (
        f"large limiter passages: {passages.large}"
    )


# ── Business rules ────────────────────────────────────────────────


async def test_v1_question_without_extraction_keeps_rewrite_then_generation(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "v1")

    passages = await _passages_for(db, tenant_a, structured="none", schema="none")

    assert passages.large == ["rewrite", "generate"], f"large limiter passages: {passages.large}"


async def test_v1_table_question_still_emits_the_table_after_the_answer_text(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "v1")
    project, user = await _project_and_user(db, tenant_a)

    with (
        _recorded_limiters(),
        _patched_qdrant(_fake_qdrant(tenant_a.id, project.id)),
        _patched_mistral(
            rewrite_response=_rewrite_response(query=NARROW_QUESTION, structured="table"),
            table_response=_table(),
        ),
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=NARROW_QUESTION,
        )

    kinds = [next(iter(e)) if isinstance(e, dict) else e for e in events]
    assert "structured" in kinds, f"event kinds: {kinds}"
    last_text = max(i for i, k in enumerate(kinds) if k == "text")
    structured_index = kinds.index("structured")
    assert structured_index > last_text, f"event kinds: {kinds}"
    structured_event = events[structured_index]
    assert isinstance(structured_event, dict)
    assert TABLE_TITLE in str(structured_event["structured"])


async def test_baseline_table_and_schema_question_keeps_todays_large_limiter_order(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "baseline")

    passages = await _passages_for(db, tenant_a, structured="table", schema="schema")

    assert passages.large == ["rewrite", "extract_schema", "extract_table", "generate"], (
        f"large limiter passages: {passages.large}"
    )
    assert passages.fast == []


# ── Edge cases ────────────────────────────────────────────────────


async def test_v1_generation_failing_before_the_limiter_does_not_leave_the_extractions_waiting(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pin_settings(monkeypatch, "v1")

    def _boom(*args: object, **kwargs: object) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.chat.graph.prompt_cache_key", _boom)
    project, user = await _project_and_user(db, tenant_a)

    with (
        _recorded_limiters(),
        _patched_qdrant(_fake_qdrant(tenant_a.id, project.id)),
        _patched_mistral(
            rewrite_response=_rewrite_response(
                query=NARROW_QUESTION, structured="table", schema="schema"
            ),
            table_response=_table(),
            schema_response=_schema(),
        ),
        pytest.raises(RuntimeError),
    ):
        await asyncio.wait_for(
            _stream(
                db,
                tenant_id=tenant_a.id,
                project_id=project.id,
                user_id=user.id,
                question=NARROW_QUESTION,
            ),
            timeout=5,
        )
