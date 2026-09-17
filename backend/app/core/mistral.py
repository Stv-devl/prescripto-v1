"""Mistral AI client singleton, its pricing, and its per-second rate limit.

Both numbers are sourced and dated in docs/research-cache/settled.md — not
re-checked automatically, re-verify there before trusting either.
"""

import asyncio
import time

from mistralai import Mistral

from app.core.config import settings

mistral_client = Mistral(api_key=settings.mistral_api_key)

MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS = {"input": 0.5, "output": 1.5}


class _RateLimiter:
    """Serializes calls to stay under a fixed requests-per-second budget."""

    def __init__(self, requests_per_second: float) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_slot - now)
            self._next_slot = max(now, self._next_slot) + self._min_interval
        if delay:
            await asyncio.sleep(delay)


mistral_large_limiter = _RateLimiter(requests_per_second=0.25)
