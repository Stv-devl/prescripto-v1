"""Model and limiter routing, and usage reporting, of `extract_table`.

Mistral and both rate limiters are doubles; nothing touches the network. The
limiter passage counts are the only observable trace of which limiter gated
the call.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from mistralai.client.models import UsageInfo

from app.core.config import settings
from app.core.mistral import mistral_client, mistral_fast_limiter, mistral_large_limiter
from app.schemas.chat import StructuredTable
from app.services.chat.table_extraction import extract_table

CONTEXT = "Semelle filante en béton armé, 10 ml, RDC."
QUESTION = "Fais-moi un tableau des semelles"
ROWS = [{"element": "Semelle", "description": "Béton armé", "quantite": "10 ml", "localisation": "RDC"}]
COLUMNS = ["Élément", "Description", "Quantité", "Localisation"]
USAGE = UsageInfo.model_validate({"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200})


@dataclass
class Trace:
    models: list[str] = field(default_factory=list)
    large_waits: int = 0
    fast_waits: int = 0


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=USAGE)


def _table_json() -> str:
    return json.dumps({"title": "Semelles", "columns": COLUMNS, "rows": ROWS})


@contextmanager
def _doubles(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str,
    fast_model: str = "mistral-small-latest",
    content: str | None = None,
    error: Exception | None = None,
) -> Iterator[Trace]:
    monkeypatch.setattr(settings, "retrieval_mode", mode)
    monkeypatch.setattr(settings, "v1_fast_model", fast_model)
    trace = Trace()

    async def _complete_async(*, model: str, **kwargs: object) -> SimpleNamespace:
        trace.models.append(model)
        if error is not None:
            raise error
        return _response(content if content is not None else _table_json())

    async def _large_wait() -> None:
        trace.large_waits += 1

    async def _fast_wait() -> None:
        trace.fast_waits += 1

    with (
        patch.object(mistral_client.chat, "complete_async", new=_complete_async),
        patch.object(mistral_large_limiter, "wait", new=AsyncMock(side_effect=_large_wait)),
        patch.object(mistral_fast_limiter, "wait", new=AsyncMock(side_effect=_fast_wait)),
    ):
        yield trace


async def test_v1_table_extraction_stays_on_mistral_large(monkeypatch: pytest.MonkeyPatch) -> None:
    with _doubles(monkeypatch, mode="v1") as trace:
        await extract_table(CONTEXT, QUESTION, usage_sink=[])

    assert trace.models == ["mistral-large-latest"]


async def test_v1_table_extraction_waits_on_the_large_limiter_not_the_fast_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _doubles(monkeypatch, mode="v1") as trace:
        await extract_table(CONTEXT, QUESTION, usage_sink=[])

    assert (trace.fast_waits, trace.large_waits) == (0, 1)


async def test_baseline_table_extraction_stays_on_mistral_large(monkeypatch: pytest.MonkeyPatch) -> None:
    with _doubles(monkeypatch, mode="baseline") as trace:
        await extract_table(CONTEXT, QUESTION, usage_sink=[])

    assert trace.models == ["mistral-large-latest"]
    assert (trace.large_waits, trace.fast_waits) == (1, 0)


async def test_table_extraction_appends_its_usage_to_the_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _doubles(monkeypatch, mode="baseline"):
        table = await extract_table(CONTEXT, QUESTION, usage_sink=sink)

    assert sink == [("mistral-large-latest", USAGE)]
    assert table == StructuredTable(title="Semelles", columns=COLUMNS, rows=ROWS)


async def test_v1_table_extraction_records_mistral_large_in_the_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _doubles(monkeypatch, mode="v1"):
        await extract_table(CONTEXT, QUESTION, usage_sink=sink)

    assert sink == [("mistral-large-latest", USAGE)]


async def test_a_large_fast_model_keeps_the_large_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    with _doubles(monkeypatch, mode="v1", fast_model="mistral-large-latest") as trace:
        await extract_table(CONTEXT, QUESTION, usage_sink=[])

    assert (trace.large_waits, trace.fast_waits) == (1, 0)


async def test_table_extraction_without_sink_still_returns_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    with _doubles(monkeypatch, mode="baseline"):
        table = await extract_table(CONTEXT, QUESTION)

    assert table == StructuredTable(title="Semelles", columns=COLUMNS, rows=ROWS)


async def test_invalid_json_returns_none_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _doubles(monkeypatch, mode="v1", content="not json at all"):
        table = await extract_table(CONTEXT, QUESTION, usage_sink=sink)

    assert table is None
    assert sink == [("mistral-large-latest", USAGE)]


async def test_mistral_error_returns_none_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _doubles(monkeypatch, mode="v1", error=RuntimeError("boom")):
        table = await extract_table(CONTEXT, QUESTION, usage_sink=sink)

    assert table is None
    assert sink == []


async def test_b28_table_on_openai_is_parsed_and_usage_names_the_openai_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openai.types import CompletionUsage
    from openai.types.completion_usage import PromptTokensDetails

    openai_calls: list[dict[str, object]] = []
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=_table_json(), tool_calls=None))],
        usage=CompletionUsage(
            prompt_tokens=321,
            completion_tokens=17,
            total_tokens=338,
            prompt_tokens_details=PromptTokensDetails(cached_tokens=64),
        ),
    )

    async def create(**kwargs: object) -> SimpleNamespace:
        openai_calls.append(kwargs)
        return reply

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    sink: list[tuple[str, UsageInfo]] = []
    with _doubles(monkeypatch, mode="v1") as trace:
        monkeypatch.setattr(settings, "openai_api_key", "sk-test")
        monkeypatch.setattr(settings, "chat_provider", "openai")
        monkeypatch.setattr(settings, "openai_chat_model", "gpt-test-chat")
        monkeypatch.setattr(settings, "openai_fast_model", "gpt-test-fast")
        monkeypatch.setattr(settings, "openai_reasoning_effort", None)
        monkeypatch.setattr("app.services.chat.llm.get_openai_client", lambda: fake_openai)
        table = await extract_table(CONTEXT, QUESTION, usage_sink=sink)

    assert table == StructuredTable(title="Semelles", columns=COLUMNS, rows=ROWS)
    assert len(openai_calls) == 1
    assert openai_calls[0]["model"] == "gpt-test-chat"
    assert openai_calls[0]["response_format"] == {"type": "json_object"}
    assert trace.models == []
    assert (trace.large_waits, trace.fast_waits) == (0, 0)
    assert len(sink) == 1
    assert sink[0][0] == "gpt-test-chat"
    assert sink[0][1].prompt_tokens == 321
    assert sink[0][1].completion_tokens == 17
