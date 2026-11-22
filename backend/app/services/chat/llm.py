"""One entry point for the chat's LLM calls: provider, model and rate limiter, chosen per call.

`settings.chat_provider` is read at call time. On Mistral the request is exactly the one the chat
sent before this module existed — the caller passes its own `mistral_client` and the Mistral
limiter it picked, so the frozen tests that patch those names on each service module still
intercept. On OpenAI the requested Mistral model is mapped by `effective_model`, the OpenAI
limiter replaces the Mistral one, and the usage is converted to a Mistral `UsageInfo` whose
`prompt_tokens_details.cached_tokens` extra is what `cached_tokens_of` reads. Errors propagate
unchanged: every caller keeps its own fallback (docs/work/openai-chat/plan.md, § Contracts).
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from mistralai.client.models import UsageInfo
from openai.types import CompletionUsage

from app.core.config import settings
from app.core.openai import get_openai_client, openai_limiter
from app.services.chat.model_routing import effective_model


class Limiter(Protocol):
    async def wait(self) -> float: ...


class ToolFunction(Protocol):
    name: str
    arguments: str | dict[str, object]


class ToolCallLike(Protocol):
    function: ToolFunction


class _MistralChat(Protocol):
    async def complete_async(self, **kwargs: object) -> object: ...

    async def stream_async(self, **kwargs: object) -> object: ...


class MistralChat(Protocol):
    chat: _MistralChat


@dataclass(frozen=True)
class ChatReply:
    text: str | None
    usage: UsageInfo | None
    model: str
    tool_calls: Sequence[ToolCallLike] = field(default_factory=list)


@dataclass(frozen=True)
class StreamPiece:
    text: str | None
    usage: UsageInfo | None


def _openai_model(model: str) -> str:
    return effective_model(
        "openai",
        model,
        chat_model=settings.openai_chat_model,
        fast_model=settings.openai_fast_model,
    )


def _to_usage(usage: CompletionUsage | None) -> UsageInfo | None:
    if usage is None:
        return None
    details = usage.prompt_tokens_details
    cached = details.cached_tokens if details is not None and details.cached_tokens else 0
    return UsageInfo(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        prompt_tokens_details={"cached_tokens": cached},
    )


def _text_of(content: object) -> str | None:
    return content if isinstance(content, str) else None


async def wait_turn(mistral_limiter: Limiter) -> None:
    """Wait for a request slot: the given Mistral limiter, or the OpenAI one on openai."""
    if settings.chat_provider == "openai":
        await openai_limiter.wait()
    else:
        await mistral_limiter.wait()


async def complete(
    mistral: MistralChat,
    mistral_limiter: Limiter,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None = None,
    json_mode: bool = False,
    cache_key: str | None = None,
    tools: list[dict[str, object]] | None = None,
) -> ChatReply:
    """One non-streamed chat call on the configured provider, after its rate-limit slot."""
    await wait_turn(mistral_limiter)
    if settings.chat_provider == "openai":
        return await _complete_openai(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            cache_key=cache_key,
            tools=tools,
        )
    kwargs: dict[str, object] = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if cache_key:
        kwargs["prompt_cache_key"] = cache_key
    if tools is not None:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "any"
        kwargs["parallel_tool_calls"] = True
    response = await mistral.chat.complete_async(**kwargs)
    message = response.choices[0].message  # type: ignore[attr-defined]
    return ChatReply(
        text=_text_of(message.content),
        usage=response.usage,  # type: ignore[attr-defined]
        model=model,
        tool_calls=getattr(message, "tool_calls", None) or [],
    )


async def _complete_openai(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
    json_mode: bool,
    cache_key: str | None,
    tools: list[dict[str, object]] | None,
) -> ChatReply:
    called = _openai_model(model)
    kwargs: dict[str, object] = {"model": called, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_completion_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if cache_key:
        kwargs["prompt_cache_key"] = cache_key
    if tools is not None:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "required"
        kwargs["parallel_tool_calls"] = True
    if settings.openai_reasoning_effort is not None:
        kwargs["reasoning_effort"] = settings.openai_reasoning_effort
    response = await get_openai_client().chat.completions.create(**kwargs)  # type: ignore[call-overload]
    message = response.choices[0].message
    return ChatReply(
        text=_text_of(message.content),
        usage=_to_usage(response.usage),
        model=called,
        tool_calls=message.tool_calls or [],
    )


async def open_stream(
    mistral: MistralChat,
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    cache_key: str | None = None,
) -> AsyncIterator[StreamPiece]:
    """The streamed generation on the configured provider, as text pieces then the final usage.

    No rate-limit wait here: the caller runs `wait_turn` first, so the time to first token is
    measured from the request, not from the queue."""
    if settings.chat_provider == "openai":
        kwargs: dict[str, object] = {
            "model": _openai_model(model),
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if cache_key:
            kwargs["prompt_cache_key"] = cache_key
        if settings.openai_reasoning_effort is not None:
            kwargs["reasoning_effort"] = settings.openai_reasoning_effort
        chunks = await get_openai_client().chat.completions.create(**kwargs)  # type: ignore[call-overload]
        async for chunk in chunks:
            text = chunk.choices[0].delta.content if chunk.choices else None
            yield StreamPiece(text=_text_of(text), usage=_to_usage(chunk.usage))
        return
    mistral_kwargs: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if cache_key:
        mistral_kwargs["prompt_cache_key"] = cache_key
    events = await mistral.chat.stream_async(**mistral_kwargs)
    async for event in events:  # type: ignore[attr-defined]
        token = event.data.choices[0].delta.content
        yield StreamPiece(text=_text_of(token), usage=event.data.usage)
