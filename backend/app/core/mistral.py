"""Mistral AI client singleton, its pricing, and its per-second rate limit.

Both numbers are sourced and dated in docs/research-cache/settled.md — not
re-checked automatically, re-verify there before trusting either.
"""

import asyncio
import time

from mistralai.client import Mistral
from mistralai.client.chat import Chat
from mistralai.client.models import ChatCompletionResponse, CompletionEvent
from mistralai.client.utils.eventstreaming import EventStreamAsync

from app.core import timing
from app.core.config import settings

MODEL_PINS: dict[str, str] = {"mistral-large-latest": "mistral-large-2512"}


def pinned_model(model: str) -> str:
    """The exact model version sent to the API for `model`.

    `mistral-large-latest` now resolves to mistral-large-4, a reasoning model whose replies
    carry `ThinkChunk` lists; the prompts, quota and parsing were tuned for mistral-large-2512
    (docs/work/mistral-large-4-alias/debug.md)."""
    return MODEL_PINS.get(model, model)


class _PinnedChat:
    """The SDK's `chat`, with the model name pinned before each request."""

    def __init__(self, chat: Chat) -> None:
        self._chat = chat

    async def complete_async(self, *, model: str, **kwargs: object) -> ChatCompletionResponse:
        return await self._chat.complete_async(model=pinned_model(model), **kwargs)  # type: ignore[arg-type]

    async def stream_async(
        self, *, model: str, **kwargs: object
    ) -> EventStreamAsync[CompletionEvent]:
        return await self._chat.stream_async(model=pinned_model(model), **kwargs)  # type: ignore[arg-type]

    def __getattr__(self, name: str) -> object:
        return getattr(self._chat, name)


class _PinnedMistral:
    """The SDK client; `chat` pins model names, every other attribute is the SDK's own."""

    def __init__(self, client: Mistral) -> None:
        self._client = client
        self.chat = _PinnedChat(client.chat)

    def __getattr__(self, name: str) -> object:
        return getattr(self._client, name)


mistral_client = _PinnedMistral(Mistral(api_key=settings.mistral_api_key))

MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS = {"input": 0.5, "output": 1.5}


class _RateLimiter:
    """Serializes calls to stay under a fixed requests-per-second budget."""

    def __init__(self, requests_per_second: float) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def wait(self) -> float:
        async with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_slot - now)
            self._next_slot = max(now, self._next_slot) + self._min_interval
        if delay:
            await asyncio.sleep(delay)
        step = timing.current_step()
        if step is not None:
            timing.record(f"{step}_wait", int(delay * 1000))
        return delay


mistral_large_limiter = _RateLimiter(requests_per_second=0.25)
mistral_fast_limiter = _RateLimiter(requests_per_second=settings.v1_fast_rps)
