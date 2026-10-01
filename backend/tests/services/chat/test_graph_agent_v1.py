"""The v1 chat graph's "start over" loop on a broad question: judge, reformulate, search once more.

End to end through `chat_stream`, at the same edge as `test_graph.py`: the Mistral
singleton's `complete_async` / `stream_async` / `embeddings.create_async` are patched in
place and Qdrant is `FakeQdrant`. The Mistral double routes `complete_async` by system
prompt (rewrite, judge, reformulation) and keeps the list of prompts it was sent.

Reachability is built on purpose, so a retry case can only pass if the second search ran:
- passage A answers the question (dense score 0.9, content type `description`);
- passage B shares tokens only with the reformulated query, none with the broad question,
  scores 0.1 on the dense branch and has content type `quantity`, which the per-lot scroll
  of the first (broad) search skips.

Where the only trace of a rule is "was this call made at all", the prompt log is read, the
same exception `test_graph.py` takes. The embedded texts are read because the query sent to
the second search is only visible there.
"""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from mistralai.models import UsageInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mistral import mistral_client, mistral_fast_limiter, mistral_large_limiter
from app.models.tenant import Tenant
from app.services.chat.graph import _usage_event
from app.services.chat.prompts import REWRITE_PROMPT
from app.services.chat.sufficiency import JUDGE_PROMPT, REFORMULATE_PROMPT
from app.services.sparse import query_sparse_vector
from tests.fakes import FakePoint, FakeQdrant, FakeQueryResponse
from tests.services.chat.test_graph import (
    _chunk_point,
    _kind,
    _patched_qdrant,
    _project_and_user,
    _rewrite_response,
    _stream,
)

BROAD_QUESTION = "Listez les lots du projet ?"
NARROW_QUESTION = "Quel isolant sous la dalle du garage ?"
REFORMULATED = "panneaux XPS lambda 0,034 resistance thermique"
STREAM_TOKENS = ("Le garage ", "reçoit un isolant.")

A_TEXT = (
    "Le garage reçoit une dalle béton armé de douze centimètres avec isolant polystyrène "
    "expansé posé sous la chape flottante, conformément au DTU 13.3 et aux prescriptions "
    "du fabricant de l'ouvrage."
)
A_MARK = "dalle béton armé de douze centimètres"
B_TEXT = (
    "Panneaux XPS lambda 0,034 resistance thermique 2,9 m2.K/W epaisseur 100 mm, pose "
    "collee en plaque sur support plan, joints decales, fourniture et mise en oeuvre "
    "incluses selon prescriptions techniques fabricant."
)
B_MARK = "Panneaux XPS lambda 0,034"
A_FILE = "CCTP_gros_oeuvre.pdf"
B_FILE = "CCTP_isolation_dalle.pdf"


def _reply(content: str, usage: UsageInfo | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage
    )


def _judge_reply(verdict: str) -> SimpleNamespace:
    return _reply(json.dumps({"verdict": verdict, "manque": "les caractéristiques de l'isolant"}))


def _reformulation_reply(query: str) -> SimpleNamespace:
    return _reply(json.dumps({"query": query}))


INSUFFICIENT = _judge_reply("insuffisant")
SUFFICIENT = _judge_reply("suffisant")


@contextmanager
def _patched_mistral(
    *,
    rewrite_response: SimpleNamespace,
    judge_response: SimpleNamespace | Exception = INSUFFICIENT,
    reformulation_response: SimpleNamespace | Exception | None = None,
    generation_usage: UsageInfo | None = None,
    calls: list[str] | None = None,
    embedded: list[list[str]] | None = None,
) -> Iterator[AsyncMock]:
    """Patches the Mistral edges in place. `calls` records the system prompt kind per call,
    `embedded` the batch of texts of each embedding call."""
    call_log = calls if calls is not None else []
    embed_log = embedded if embedded is not None else []
    reformulation = (
        reformulation_response
        if reformulation_response is not None
        else _reformulation_reply(REFORMULATED)
    )

    async def _complete_async(
        *, model: str, messages: list[dict[str, str]], **kwargs: object
    ) -> SimpleNamespace:
        system = messages[0]["content"]
        if system == REWRITE_PROMPT:
            call_log.append("rewrite")
            return rewrite_response
        if system == JUDGE_PROMPT:
            call_log.append("judge")
            if isinstance(judge_response, Exception):
                raise judge_response
            return judge_response
        if system == REFORMULATE_PROMPT:
            call_log.append("reformulate")
            if isinstance(reformulation, Exception):
                raise reformulation
            return reformulation
        raise AssertionError(f"unexpected system prompt sent to complete_async: {system[:80]!r}")

    def _stream_async(*, model: str, messages: list[dict[str, str]], **kwargs: object) -> object:
        async def _gen() -> object:
            last = len(STREAM_TOKENS) - 1
            for i, token in enumerate(STREAM_TOKENS):
                yield SimpleNamespace(
                    data=SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=token))],
                        usage=generation_usage if i == last else None,
                    )
                )

        return _gen()

    async def _create_async(*, model: str, inputs: list[str], **kwargs: object) -> SimpleNamespace:
        embed_log.append(list(inputs))
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0, 0.0]) for _ in inputs])

    with (
        patch.object(mistral_client.chat, "complete_async", side_effect=_complete_async),
        patch.object(mistral_client.chat, "stream_async", side_effect=_stream_async) as stream_mock,
        patch.object(mistral_client.embeddings, "create_async", side_effect=_create_async),
    ):
        yield stream_mock


class _FailsOnReformulatedQuery(FakeQdrant):
    """A FakeQdrant whose hybrid query raises when its sparse branch carries the
    reformulated query's tokens, as a Qdrant outage during the second search."""

    async def query_points(self, **kwargs: object) -> FakeQueryResponse:  # type: ignore[override]
        reformulated = query_sparse_vector(REFORMULATED)
        assert reformulated is not None
        for branch in kwargs.get("prefetch") or []:  # type: ignore[attr-defined]
            if branch.using == "sparse" and list(branch.query.indices) == list(reformulated.indices):
                raise RuntimeError("Qdrant unreachable on the second search")
        return await super().query_points(**kwargs)  # type: ignore[arg-type]


def _points(
    tenant_id: uuid.UUID, project_id: uuid.UUID, *, b_content_type: str = "quantity"
) -> list[FakePoint]:
    return [
        _chunk_point(
            tenant_id=tenant_id,
            project_id=project_id,
            text=A_TEXT,
            filename=A_FILE,
            page=4,
            position=1,
            score=0.9,
        ),
        _chunk_point(
            tenant_id=tenant_id,
            project_id=project_id,
            text=B_TEXT,
            filename=B_FILE,
            page=9,
            position=2,
            score=0.1,
            content_type=b_content_type,
        ),
    ]


def _prompt(stream_mock: AsyncMock) -> str:
    return "\n".join(m["content"] for m in stream_mock.call_args.kwargs["messages"])


def _source_files(events: list[dict[str, object] | str]) -> list[str]:
    for event in events:
        if isinstance(event, dict) and "sources" in event:
            return [str(s["filename"]) for s in event["sources"]]  # type: ignore[union-attr]
    return []


def _usage_of(events: list[dict[str, object] | str]) -> dict[str, dict[str, float]]:
    usage_events = [e for e in events if isinstance(e, dict) and "usage" in e]
    assert len(usage_events) == 1
    return usage_events[0]["usage"]  # type: ignore[return-value]


# ── Core behaviour ────────────────────────────────────────────────


async def test_v1_broad_insufficient_judgment_triggers_one_second_search_and_generation_reads_both_passages(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), calls=calls
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge", "reformulate"]
    prompt = _prompt(stream_mock)
    assert A_MARK in prompt
    assert B_MARK in prompt


async def test_v1_narrow_question_sends_neither_judge_nor_reformulation(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=NARROW_QUESTION),
        judge_response=INSUFFICIENT,
        calls=calls,
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=NARROW_QUESTION,
        )

    assert calls == ["rewrite"]
    assert B_MARK not in _prompt(stream_mock)


async def test_v1_broad_second_search_uses_the_reformulated_query_not_the_first_one(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    embedded: list[list[str]] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), embedded=embedded
    ):
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert embedded[0] == [BROAD_QUESTION]
    assert embedded[-1] == [REFORMULATED]


async def test_v1_broad_sufficient_judgment_goes_to_generation_without_reformulation_or_second_search(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        judge_response=SUFFICIENT,
        calls=calls,
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge"]
    prompt = _prompt(stream_mock)
    assert A_MARK in prompt
    assert B_MARK not in prompt


async def test_v1_broad_sources_follow_the_merged_passages(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION)
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert B_FILE in _source_files(events)


# ── Business rules ────────────────────────────────────────────────


async def test_baseline_broad_question_sends_neither_judge_nor_reformulation_and_keeps_the_three_key_usage(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), calls=calls
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite"]
    assert set(_usage_of(events)) == {"rewrite", "generation", "total"}


async def test_v1_broad_judge_is_called_once_even_when_it_would_always_answer_insufficient(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        judge_response=INSUFFICIENT,
        calls=calls,
    ):
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls.count("judge") == 1
    assert calls.count("reformulate") == 1


async def test_v1_broad_retry_search_never_brings_another_tenants_passage(
    db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    own = _chunk_point(
        tenant_id=tenant_a.id,
        project_id=project.id,
        text=B_TEXT,
        filename="CCTP_tenant_a_only.pdf",
        page=9,
        position=2,
        score=0.1,
        content_type="quantity",
    )
    foreign = _chunk_point(
        tenant_id=tenant_b.id,
        project_id=project.id,
        text=B_TEXT.replace("Panneaux XPS lambda 0,034", "SECRET_TENANT_B_XPS lambda 0,034"),
        filename="CCTP_tenant_b_secret.pdf",
        page=3,
        position=7,
        score=0.1,
        content_type="quantity",
    )
    answer = _chunk_point(
        tenant_id=tenant_a.id,
        project_id=project.id,
        text=A_TEXT,
        filename=A_FILE,
        page=4,
        position=1,
        score=0.9,
    )
    fake = FakeQdrant([answer, own, foreign])

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION)
    ) as stream_mock:
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    prompt = _prompt(stream_mock)
    assert B_MARK in prompt
    assert "SECRET_TENANT_B_XPS" not in prompt
    assert "CCTP_tenant_a_only.pdf" in _source_files(events)
    assert "CCTP_tenant_b_secret.pdf" not in _source_files(events)


async def test_v1_broad_usage_counts_judge_and_reformulation_in_agent_and_total(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    rewrite = _rewrite_response(query=BROAD_QUESTION)
    rewrite.usage = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)
    judge = _judge_reply("insuffisant")
    judge.usage = UsageInfo(
        prompt_tokens=2_000_000, completion_tokens=1_000_000, total_tokens=3_000_000
    )
    reformulation = _reformulation_reply(REFORMULATED)
    reformulation.usage = UsageInfo(
        prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000
    )
    generation = UsageInfo(prompt_tokens=2_000_000, completion_tokens=0, total_tokens=2_000_000)

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=rewrite,
        judge_response=judge,
        reformulation_response=reformulation,
        generation_usage=generation,
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    usage = _usage_of(events)
    assert usage["agent"] == {
        "input_tokens": 3_000_000,
        "output_tokens": 2_000_000,
        "cost_usd": pytest.approx(1.65),
    }
    assert usage["total"] == {
        "input_tokens": 6_000_000,
        "output_tokens": 2_000_000,
        "cost_usd": pytest.approx(3.15),
    }


async def test_usage_event_with_an_agent_list_adds_the_agent_leg_and_sums_it_into_total() -> None:
    rewrite = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)
    generation = UsageInfo(prompt_tokens=2_000_000, completion_tokens=0, total_tokens=2_000_000)
    judge = UsageInfo(prompt_tokens=2_000_000, completion_tokens=1_000_000, total_tokens=3_000_000)
    reformulation = UsageInfo(
        prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000
    )

    event = _usage_event(rewrite, generation, agent=[judge, reformulation])

    assert event == {
        "rewrite": {"input_tokens": 1_000_000, "output_tokens": 0, "cost_usd": 0.5},
        "generation": {"input_tokens": 2_000_000, "output_tokens": 0, "cost_usd": 1.0},
        "agent": {"input_tokens": 3_000_000, "output_tokens": 2_000_000, "cost_usd": 4.5},
        "total": {"input_tokens": 6_000_000, "output_tokens": 2_000_000, "cost_usd": 6.0},
    }


async def test_v1_broad_each_mistral_call_waits_on_its_models_rate_limiter(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))

    with (
        patch.object(mistral_large_limiter, "wait", new_callable=AsyncMock) as large_wait,
        patch.object(mistral_fast_limiter, "wait", new_callable=AsyncMock) as fast_wait,
        _patched_qdrant(fake),
        _patched_mistral(rewrite_response=_rewrite_response(query=BROAD_QUESTION)),
    ):
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert large_wait.await_count == 2
    assert fast_wait.await_count == 2


async def test_v1_broad_generation_keeps_the_broad_prompt_after_the_retry(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION)
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    system_prompt = stream_mock.call_args.kwargs["messages"][0]["content"]
    assert B_MARK in _prompt(stream_mock)
    assert "QUESTION GÉNÉRALE" in system_prompt


async def test_v1_off_topic_broad_question_sends_no_judge(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_reply("HORS_SUJET"), calls=calls
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite"]
    assert _kind(events[-1]) == "DONE"


# ── Edge cases ────────────────────────────────────────────────────


async def test_v1_broad_judge_exception_serves_the_question_as_today_without_retry_or_error_event(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        judge_response=RuntimeError("Mistral judge unavailable"),
        calls=calls,
    ) as stream_mock:
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge"]
    assert "error" not in [_kind(e) for e in events]
    prompt = _prompt(stream_mock)
    assert A_MARK in prompt
    assert B_MARK not in prompt


async def test_v1_broad_unreadable_judge_reply_serves_the_question_without_retry(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        judge_response=_reply("je ne sais pas, voici du texte libre"),
        calls=calls,
    ) as stream_mock:
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge"]
    assert "error" not in [_kind(e) for e in events]
    assert B_MARK not in _prompt(stream_mock)


async def test_v1_broad_reformulation_equal_to_the_first_query_makes_no_second_search(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []
    embedded: list[list[str]] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        reformulation_response=_reformulation_reply("  LISTEZ les lots du projet ?  "),
        calls=calls,
        embedded=embedded,
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge", "reformulate"]
    assert all(REFORMULATED not in batch for batch in embedded)
    assert B_MARK not in _prompt(stream_mock)


async def test_v1_broad_second_search_failure_serves_the_first_passages_without_error_event(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = _FailsOnReformulatedQuery(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), calls=calls
    ) as stream_mock:
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert calls == ["rewrite", "judge", "reformulate"]
    kinds = [_kind(e) for e in events]
    assert "error" not in kinds
    assert "text" in kinds
    prompt = _prompt(stream_mock)
    assert A_MARK in prompt
    assert B_MARK not in prompt


async def test_v1_broad_empty_first_context_triggers_the_retry_without_a_judge_call(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    only_b = [_points(tenant_a.id, project.id)[1]]
    fake = FakeQdrant(only_b)
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), calls=calls
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert "judge" not in calls
    assert "reformulate" in calls
    assert B_MARK in _prompt(stream_mock)


async def test_v1_narrow_question_whose_llm_rewrite_says_broad_sends_no_judge(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []
    llm_says_broad = _reply(
        json.dumps(
            {
                "query": NARROW_QUESTION,
                "related": [],
                "scope": "broad",
                "structured": "none",
                "schema": "none",
            }
        )
    )

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=llm_says_broad, judge_response=INSUFFICIENT, calls=calls
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=NARROW_QUESTION,
        )

    assert calls == ["rewrite"]
    assert B_MARK not in _prompt(stream_mock)


# ── Jambe B — model routing ───────────────────────────────────────


async def test_v1_rewrite_calls_the_rewrite_model_and_judge_and_reformulation_the_fast_model(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    calls: list[str] = []

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION),
        judge_response=INSUFFICIENT,
        calls=calls,
    ):
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )
        models = [
            call.kwargs["model"] for call in mistral_client.chat.complete_async.call_args_list
        ]

    assert calls == ["rewrite", "judge", "reformulate"]
    assert models == ["mistral-large-latest", "mistral-small-latest", "mistral-small-latest"]


async def test_changing_v1_fast_model_changes_the_model_called(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "ministral-8b-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), judge_response=INSUFFICIENT
    ):
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )
        models = [
            call.kwargs["model"] for call in mistral_client.chat.complete_async.call_args_list
        ]

    assert models == ["mistral-large-latest", "ministral-8b-latest", "ministral-8b-latest"]


async def test_v1_generation_still_calls_mistral_large(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=_rewrite_response(query=BROAD_QUESTION), judge_response=INSUFFICIENT
    ) as stream_mock:
        await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )
        generation_model = stream_mock.call_args.kwargs["model"]

    assert generation_model == "mistral-large-latest"


async def test_v1_rewrite_leg_is_priced_at_the_rewrite_models_price(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-large-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    rewrite = _rewrite_response(query=BROAD_QUESTION)
    rewrite.usage = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=rewrite, judge_response=SUFFICIENT
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert _usage_of(events)["rewrite"] == {
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "cost_usd": pytest.approx(0.5),
    }


async def test_usage_event_with_a_short_call_price_prices_rewrite_and_agent_at_it_and_generation_at_large() -> (
    None
):
    rewrite = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)
    generation = UsageInfo(prompt_tokens=2_000_000, completion_tokens=0, total_tokens=2_000_000)
    judge = UsageInfo(prompt_tokens=2_000_000, completion_tokens=1_000_000, total_tokens=3_000_000)
    reformulation = UsageInfo(
        prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000
    )

    event = _usage_event(
        rewrite,
        generation,
        agent=[judge, reformulation],
        short_call_price={"input": 0.15, "output": 0.6},
    )

    assert event["rewrite"] == {
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "cost_usd": pytest.approx(0.15),
    }
    assert event["generation"] == {
        "input_tokens": 2_000_000,
        "output_tokens": 0,
        "cost_usd": pytest.approx(1.0),
    }
    assert event["agent"] == {
        "input_tokens": 3_000_000,
        "output_tokens": 2_000_000,
        "cost_usd": pytest.approx(1.65),
    }
    assert event["total"] == {
        "input_tokens": 6_000_000,
        "output_tokens": 2_000_000,
        "cost_usd": pytest.approx(2.8),
    }


async def test_baseline_broad_question_prices_every_leg_at_the_large_price(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    rewrite = _rewrite_response(query=BROAD_QUESTION)
    rewrite.usage = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)
    generation = UsageInfo(prompt_tokens=2_000_000, completion_tokens=0, total_tokens=2_000_000)

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=rewrite, generation_usage=generation
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    usage = _usage_of(events)
    assert usage["rewrite"]["cost_usd"] == pytest.approx(0.5)
    assert usage["total"]["cost_usd"] == pytest.approx(1.5)


async def test_v1_rewrite_leg_follows_a_non_large_rewrite_models_price(
    db: AsyncSession, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    monkeypatch.setattr("app.core.config.settings.v1_fast_model", "mistral-small-latest")
    monkeypatch.setattr("app.core.config.settings.v1_rewrite_model", "mistral-small-latest")
    project, user = await _project_and_user(db, tenant_a)
    fake = FakeQdrant(_points(tenant_a.id, project.id))
    rewrite = _rewrite_response(query=BROAD_QUESTION)
    rewrite.usage = UsageInfo(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)

    with _patched_qdrant(fake), _patched_mistral(
        rewrite_response=rewrite, judge_response=SUFFICIENT
    ):
        events = await _stream(
            db,
            tenant_id=tenant_a.id,
            project_id=project.id,
            user_id=user.id,
            question=BROAD_QUESTION,
        )

    assert _usage_of(events)["rewrite"]["cost_usd"] == pytest.approx(0.15)
