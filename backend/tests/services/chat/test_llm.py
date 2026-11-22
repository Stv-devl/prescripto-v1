import inspect
from collections.abc import AsyncIterator, Iterable
from types import SimpleNamespace

import pytest
from mistralai.client.models import UsageInfo
from openai.types import CompletionUsage
from openai.types.completion_usage import PromptTokensDetails

from app.core.config import settings

LARGE = "mistral-large-latest"
SMALL = "mistral-small-latest"
MESSAGES = [{"role": "user", "content": "Bonjour"}]
TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {"name": "search", "parameters": {"type": "object", "properties": {}}},
    }
]


class FakeLimiter:
    def __init__(self) -> None:
        self.waits = 0

    async def wait(self) -> float:
        self.waits += 1
        return 0.0


class FakeMistral:
    """Stands in for the Mistral client: `.chat.complete_async` / `.chat.stream_async`."""

    def __init__(
        self,
        *,
        content: str | None = "mistral-text",
        tool_calls: list[SimpleNamespace] | None = None,
        usage: object = None,
        events: Iterable[SimpleNamespace] = (),
    ) -> None:
        self.complete_kwargs: list[dict[str, object]] = []
        self.stream_kwargs: list[dict[str, object]] = []
        self._content = content
        self._tool_calls = tool_calls
        self._usage = usage if usage is not None else SimpleNamespace()
        self._events = list(events)
        self.chat = SimpleNamespace(complete_async=self._complete, stream_async=self._stream)

    async def _complete(self, **kwargs: object) -> SimpleNamespace:
        self.complete_kwargs.append(kwargs)
        fields: dict[str, object] = {"content": self._content}
        if self._tool_calls is not None:
            fields["tool_calls"] = self._tool_calls
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(**fields))], usage=self._usage
        )

    async def _stream(self, **kwargs: object) -> AsyncIterator[SimpleNamespace]:
        self.stream_kwargs.append(kwargs)
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[SimpleNamespace]:
        for event in self._events:
            yield event


class FakeOpenAI:
    """Stands in for AsyncOpenAI: `.chat.completions.create(**kwargs)`."""

    def __init__(
        self,
        *,
        content: str | None = "openai-text",
        tool_calls: list[SimpleNamespace] | None = None,
        usage: CompletionUsage | None = None,
        chunks: Iterable[SimpleNamespace] = (),
        error: Exception | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._content = content
        self._tool_calls = tool_calls
        self._usage = usage
        self._chunks = list(chunks)
        self._error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: object) -> SimpleNamespace | AsyncIterator[SimpleNamespace]:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if kwargs.get("stream"):
            return self._iterate()
        message = SimpleNamespace(content=self._content, tool_calls=self._tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=self._usage)

    async def _iterate(self) -> AsyncIterator[SimpleNamespace]:
        for chunk in self._chunks:
            yield chunk


def openai_usage(prompt: int, cached: int | None, completion: int = 5) -> CompletionUsage:
    details = None if cached is None else PromptTokensDetails(cached_tokens=cached)
    return CompletionUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        prompt_tokens_details=details,
    )


def tool_call(name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="call_1", type="function", function=SimpleNamespace(name=name, arguments=arguments)
    )


def mistral_event(content: str | None, usage: object = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content)
    return SimpleNamespace(data=SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage))


def openai_chunk(content: str, usage: CompletionUsage | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


async def collect(opened: object) -> list[object]:
    """Drains what `open_stream` gives back, awaited or not."""
    stream = await opened if inspect.isawaitable(opened) else opened
    return [piece async for piece in stream]  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "chat_provider", "mistral")
    monkeypatch.setattr(settings, "openai_chat_model", "gpt-test-chat")
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-test-fast")
    monkeypatch.setattr(settings, "openai_reasoning_effort", None)


def install_openai(monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI) -> None:
    monkeypatch.setattr("app.services.chat.llm.get_openai_client", lambda: fake)


async def test_b1_mistral_provider_returns_the_text_and_usage_of_the_given_mistral_client() -> None:
    from app.services.chat.llm import complete

    usage = UsageInfo(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    mistral = FakeMistral(content="Bonjour le monde", usage=usage)
    limiter = FakeLimiter()

    reply = await complete(
        mistral, limiter, model=LARGE, messages=MESSAGES, temperature=0.0, max_tokens=256
    )

    assert reply.text == "Bonjour le monde"
    assert reply.usage is usage
    assert reply.tool_calls == []
    assert len(mistral.complete_kwargs) == 1
    assert mistral.complete_kwargs[0]["model"] == LARGE
    assert mistral.complete_kwargs[0]["messages"] == MESSAGES
    assert mistral.complete_kwargs[0]["temperature"] == 0.0
    assert mistral.complete_kwargs[0]["max_tokens"] == 256


async def test_b2_openai_provider_answers_a_large_model_request_with_the_openai_chat_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    monkeypatch.setattr(settings, "chat_provider", "openai")
    openai = FakeOpenAI(content="Reponse", usage=openai_usage(100, 0))
    install_openai(monkeypatch, openai)
    mistral = FakeMistral()

    reply = await complete(
        mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0, max_tokens=256
    )

    assert reply.text == "Reponse"
    assert len(openai.calls) == 1
    assert openai.calls[0]["model"] == "gpt-test-chat"
    assert openai.calls[0]["max_completion_tokens"] == 256
    assert "max_tokens" not in openai.calls[0]
    assert mistral.complete_kwargs == []


async def test_b3_openai_provider_answers_a_small_model_request_with_the_openai_fast_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    monkeypatch.setattr(settings, "chat_provider", "openai")
    openai = FakeOpenAI(content="Court", usage=openai_usage(100, 0))
    install_openai(monkeypatch, openai)

    reply = await complete(
        FakeMistral(), FakeLimiter(), model=SMALL, messages=MESSAGES, temperature=0.0
    )

    assert reply.text == "Court"
    assert openai.calls[0]["model"] == "gpt-test-fast"


async def test_b4_openai_usage_becomes_a_usage_whose_cached_tokens_are_read_by_cached_tokens_of(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete
    from app.services.chat.model_routing import cached_tokens_of

    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(usage=openai_usage(1192, 1152)))

    reply = await complete(
        FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert reply.usage is not None
    assert reply.usage.prompt_tokens == 1192
    assert reply.usage.completion_tokens == 5
    assert cached_tokens_of(reply.usage) == 1152


async def test_b5_reply_model_is_the_model_actually_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    install_openai(monkeypatch, FakeOpenAI(usage=openai_usage(10, 0)))

    on_mistral = await complete(
        FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )
    monkeypatch.setattr(settings, "chat_provider", "openai")
    on_openai = await complete(
        FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert on_mistral.model == "mistral-large-latest"
    assert on_openai.model == "gpt-test-chat"


async def test_b6_json_mode_asks_both_providers_for_a_json_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    openai = FakeOpenAI(content="{}", usage=openai_usage(10, 0))
    install_openai(monkeypatch, openai)
    mistral = FakeMistral(content="{}")

    await complete(
        mistral, FakeLimiter(), model=SMALL, messages=MESSAGES, temperature=0.0, json_mode=True
    )
    monkeypatch.setattr(settings, "chat_provider", "openai")
    await complete(
        mistral, FakeLimiter(), model=SMALL, messages=MESSAGES, temperature=0.0, json_mode=True
    )

    assert mistral.complete_kwargs[0]["response_format"] == {"type": "json_object"}
    assert openai.calls[0]["response_format"] == {"type": "json_object"}


async def test_b7_openai_tool_call_requires_a_tool_and_returns_name_and_json_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    monkeypatch.setattr(settings, "chat_provider", "openai")
    openai = FakeOpenAI(
        content=None,
        tool_calls=[tool_call("search", '{"q": "isolation"}')],
        usage=openai_usage(50, 0),
    )
    install_openai(monkeypatch, openai)

    reply = await complete(
        FakeMistral(),
        FakeLimiter(),
        model=SMALL,
        messages=MESSAGES,
        temperature=0.0,
        tools=TOOLS,
    )

    assert openai.calls[0]["tools"] == TOOLS
    assert openai.calls[0]["tool_choice"] == "required"
    assert openai.calls[0]["parallel_tool_calls"] is True
    assert reply.text is None
    assert len(reply.tool_calls) == 1
    assert reply.tool_calls[0].function.name == "search"
    assert reply.tool_calls[0].function.arguments == '{"q": "isolation"}'


async def test_b8_mistral_tool_call_keeps_tool_choice_any() -> None:
    from app.services.chat.llm import complete

    mistral = FakeMistral(content=None, tool_calls=[tool_call("search", '{"q": "isolation"}')])

    reply = await complete(
        mistral,
        FakeLimiter(),
        model=SMALL,
        messages=MESSAGES,
        temperature=0.0,
        tools=TOOLS,
    )

    assert mistral.complete_kwargs[0]["tools"] == TOOLS
    assert mistral.complete_kwargs[0]["tool_choice"] == "any"
    assert mistral.complete_kwargs[0]["parallel_tool_calls"] is True
    assert reply.tool_calls[0].function.name == "search"


async def test_b9_cache_key_is_sent_as_prompt_cache_key_only_when_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    openai = FakeOpenAI(usage=openai_usage(10, 0))
    install_openai(monkeypatch, openai)
    mistral = FakeMistral()

    await complete(mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0)
    await complete(
        mistral,
        FakeLimiter(),
        model=LARGE,
        messages=MESSAGES,
        temperature=0.0,
        cache_key="prescripto-v1-rewrite",
    )
    monkeypatch.setattr(settings, "chat_provider", "openai")
    await complete(mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0)
    await complete(
        mistral,
        FakeLimiter(),
        model=LARGE,
        messages=MESSAGES,
        temperature=0.0,
        cache_key="prescripto-v1-rewrite",
    )

    assert "prompt_cache_key" not in mistral.complete_kwargs[0]
    assert mistral.complete_kwargs[1]["prompt_cache_key"] == "prescripto-v1-rewrite"
    assert "prompt_cache_key" not in openai.calls[0]
    assert openai.calls[1]["prompt_cache_key"] == "prescripto-v1-rewrite"


async def test_b10_reasoning_effort_is_sent_to_openai_when_configured_and_never_to_mistral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    openai = FakeOpenAI(usage=openai_usage(10, 0))
    install_openai(monkeypatch, openai)
    mistral = FakeMistral()

    monkeypatch.setattr(settings, "openai_reasoning_effort", "low")
    await complete(mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0)
    monkeypatch.setattr(settings, "chat_provider", "openai")
    await complete(mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0)
    monkeypatch.setattr(settings, "openai_reasoning_effort", None)
    await complete(mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0)

    assert "reasoning_effort" not in mistral.complete_kwargs[0]
    assert openai.calls[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in openai.calls[1]


async def test_b11_openai_path_waits_the_openai_limiter_and_never_the_mistral_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(usage=openai_usage(10, 0)))
    openai_limiter = FakeLimiter()
    mistral_limiter = FakeLimiter()
    monkeypatch.setattr("app.services.chat.llm.openai_limiter", openai_limiter)

    await complete(
        FakeMistral(), mistral_limiter, model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert openai_limiter.waits == 1
    assert mistral_limiter.waits == 0


async def test_b12_mistral_stream_yields_tokens_in_order_then_the_final_usage() -> None:
    from app.services.chat.llm import open_stream

    usage = UsageInfo(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    mistral = FakeMistral(
        events=[
            mistral_event("Bon"),
            mistral_event("jour"),
            mistral_event(None, usage=usage),
        ]
    )

    pieces = await collect(
        open_stream(mistral, model=LARGE, messages=MESSAGES, temperature=0.0)
    )

    assert [p.text for p in pieces if p.text is not None] == ["Bon", "jour"]
    assert [p.usage for p in pieces if p.usage is not None] == [usage]
    assert pieces[-1].usage is usage


async def test_b13_openai_stream_yields_tokens_then_the_usage_of_the_final_empty_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import open_stream
    from app.services.chat.model_routing import cached_tokens_of

    monkeypatch.setattr(settings, "chat_provider", "openai")
    openai = FakeOpenAI(
        chunks=[
            openai_chunk("Bon"),
            openai_chunk("jour"),
            SimpleNamespace(choices=[], usage=openai_usage(1000, 64, completion=7)),
        ]
    )
    install_openai(monkeypatch, openai)

    pieces = await collect(
        open_stream(FakeMistral(), model=LARGE, messages=MESSAGES, temperature=0.0)
    )

    assert openai.calls[0]["stream"] is True
    assert openai.calls[0]["stream_options"] == {"include_usage": True}
    assert openai.calls[0]["model"] == "gpt-test-chat"
    assert [p.text for p in pieces if p.text is not None] == ["Bon", "jour"]
    assert pieces[-1].usage is not None
    assert pieces[-1].usage.prompt_tokens == 1000
    assert pieces[-1].usage.completion_tokens == 7
    assert cached_tokens_of(pieces[-1].usage) == 64


async def test_b14_openai_stream_without_usage_chunk_yields_no_usage_and_does_not_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import open_stream

    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(chunks=[openai_chunk("Bon"), openai_chunk("jour")]))

    pieces = await collect(
        open_stream(FakeMistral(), model=LARGE, messages=MESSAGES, temperature=0.0)
    )

    assert [p.text for p in pieces if p.text is not None] == ["Bon", "jour"]
    assert [p.usage for p in pieces if p.usage is not None] == []


async def test_b15_openai_null_content_gives_a_none_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(content=None, usage=openai_usage(10, 0)))

    reply = await complete(
        FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert reply.text is None
    assert reply.tool_calls == []


async def test_b16_an_openai_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete

    boom = RuntimeError("429 rate limited")
    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(error=boom))

    with pytest.raises(RuntimeError) as raised:
        await complete(
            FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
        )

    assert raised.value is boom


async def test_b17_provider_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.chat.llm import complete

    openai = FakeOpenAI(content="from-openai", usage=openai_usage(10, 0))
    install_openai(monkeypatch, openai)
    mistral = FakeMistral(content="from-mistral")

    first = await complete(
        mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )
    monkeypatch.setattr(settings, "chat_provider", "openai")
    second = await complete(
        mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )
    monkeypatch.setattr(settings, "chat_provider", "mistral")
    third = await complete(
        mistral, FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert [first.text, second.text, third.text] == ["from-mistral", "from-openai", "from-mistral"]
    assert len(mistral.complete_kwargs) == 2
    assert len(openai.calls) == 1


async def test_b36_openai_usage_without_prompt_tokens_details_gives_zero_cached_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.chat.llm import complete
    from app.services.chat.model_routing import cached_tokens_of

    monkeypatch.setattr(settings, "chat_provider", "openai")
    install_openai(monkeypatch, FakeOpenAI(usage=openai_usage(300, None)))

    reply = await complete(
        FakeMistral(), FakeLimiter(), model=LARGE, messages=MESSAGES, temperature=0.0
    )

    assert reply.usage is not None
    assert reply.usage.prompt_tokens == 300
    assert cached_tokens_of(reply.usage) == 0
