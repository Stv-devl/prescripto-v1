"""Tests for extract_schema: model and limiter routing, usage sink, failure handling."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from mistralai.client.models import UsageInfo

from app.core.config import settings
from app.schemas.chat import StructuredSchema
from app.services.chat.schema_extraction import extract_schema

MODULE = "app.services.chat.schema_extraction"
SCHEMA_JSON = json.dumps(
    {
        "schema_type": "toiture_terrasse",
        "title": "Toiture terrasse",
        "params": {"type_toiture": "étanchéité bitumineuse"},
    }
)
EXPECTED = StructuredSchema(
    schema_type="toiture_terrasse",
    title="Toiture terrasse",
    params={"type_toiture": "étanchéité bitumineuse"},
)
USAGE = UsageInfo(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)


@dataclass
class Doubles:
    complete: AsyncMock
    fast_wait: AsyncMock
    large_wait: AsyncMock

    @property
    def model_sent(self) -> str:
        return self.complete.await_args.kwargs["model"]


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=USAGE
    )


@contextmanager
def _patched(
    *, content: str = SCHEMA_JSON, error: Exception | None = None
) -> Iterator[Doubles]:
    complete = AsyncMock(side_effect=error) if error else AsyncMock(return_value=_response(content))
    fast_wait = AsyncMock()
    large_wait = AsyncMock()
    client = SimpleNamespace(chat=SimpleNamespace(complete_async=complete))
    with (
        patch(f"{MODULE}.mistral_client", client, create=True),
        patch(f"{MODULE}.mistral_fast_limiter.wait", fast_wait, create=True)
        if hasattr(__import__(MODULE, fromlist=["x"]), "mistral_fast_limiter")
        else patch(
            f"{MODULE}.mistral_fast_limiter", SimpleNamespace(wait=fast_wait), create=True
        ),
        patch(f"{MODULE}.mistral_large_limiter.wait", large_wait),
    ):
        yield Doubles(complete=complete, fast_wait=fast_wait, large_wait=large_wait)


@pytest.fixture
def v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "retrieval_mode", "v1")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")


@pytest.fixture
def baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "retrieval_mode", "baseline")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")


async def test_v1_schema_extraction_stays_on_mistral_large(v1: None) -> None:
    with _patched() as doubles:
        await extract_schema("contexte", "question")

    assert doubles.model_sent == "mistral-large-latest"


async def test_v1_schema_extraction_waits_on_the_large_limiter_not_the_fast_one(v1: None) -> None:
    with _patched() as doubles:
        await extract_schema("contexte", "question")

    assert (doubles.fast_wait.await_count, doubles.large_wait.await_count) == (0, 1)


async def test_baseline_schema_extraction_stays_on_mistral_large(baseline: None) -> None:
    with _patched() as doubles:
        await extract_schema("contexte", "question")

    assert doubles.model_sent == "mistral-large-latest"
    assert (doubles.fast_wait.await_count, doubles.large_wait.await_count) == (0, 1)


async def test_schema_extraction_appends_its_usage_to_the_sink(baseline: None) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _patched():
        result = await extract_schema("contexte", "question", usage_sink=sink)

    assert sink == [("mistral-large-latest", USAGE)]
    assert result == EXPECTED


async def test_v1_schema_extraction_records_mistral_large_in_the_sink(v1: None) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _patched():
        await extract_schema("contexte", "question", usage_sink=sink)

    assert sink == [("mistral-large-latest", USAGE)]


async def test_a_large_fast_model_keeps_the_large_limiter_for_schema(
    v1: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-large-latest")
    with _patched() as doubles:
        await extract_schema("contexte", "question")

    assert (doubles.fast_wait.await_count, doubles.large_wait.await_count) == (0, 1)


async def test_schema_extraction_without_sink_still_returns_the_schema(baseline: None) -> None:
    with _patched():
        result = await extract_schema("contexte", "question")

    assert result == EXPECTED


async def test_invalid_json_returns_none_without_raising_for_schema(baseline: None) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _patched(content="this is not json"):
        result = await extract_schema("contexte", "question", usage_sink=sink)

    assert result is None
    assert sink == [("mistral-large-latest", USAGE)]


async def test_mistral_error_returns_none_without_raising_for_schema(baseline: None) -> None:
    sink: list[tuple[str, UsageInfo]] = []
    with _patched(error=RuntimeError("boom")):
        result = await extract_schema("contexte", "question", usage_sink=sink)

    assert result is None
    assert sink == []
