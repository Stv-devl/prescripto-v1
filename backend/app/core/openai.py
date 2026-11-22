"""OpenAI client and its per-second rate limit, for the chat calls on CHAT_PROVIDER=openai.

The client is built on first use, never at import: with CHAT_PROVIDER=mistral there may be no
key at all. `max_retries=0` keeps a 429 visible to the caller's own fallback, as on the Mistral
path, instead of a hidden retry outside the limiter. Facts and model choice:
docs/research-cache/settled.md (OpenAI Chat Completions row).
"""

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.mistral import RateLimiter

openai_limiter = RateLimiter(requests_per_second=settings.openai_rps)


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """The process-wide OpenAI client, built from the settings' key on first call."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set: the OpenAI client cannot be built")
    return AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
