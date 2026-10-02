"""Model routing of the short chat calls (query rewrite, sufficiency judge, retry
reformulation): which model each one calls, and at what price its usage is counted
(j3-routage-mistral-small). Generation always stays on mistral-large.

Also the v1 prompt-cache keys of the four chat calls and the pricing of cached input
tokens (j3-prompt-caching)."""

from typing import Literal

from mistralai.client.models import UsageInfo

from app.core.mistral import MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS

LARGE_MODEL = "mistral-large-latest"

Price = dict[str, float]

LARGE_PRICE: Price = MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS
_SMALL_PRICE: Price = {"input": 0.15, "output": 0.6}

CACHED_INPUT_PRICE_RATIO = 0.1

PromptName = Literal["generation", "rewrite", "judge", "reformulate"]

PROMPT_CACHE_KEYS: dict[PromptName, str] = {
    "generation": "prescripto-v1-generation",
    "rewrite": "prescripto-v1-rewrite",
    "judge": "prescripto-v1-judge",
    "reformulate": "prescripto-v1-reformulate",
}

MODEL_PRICES: dict[str, Price] = {
    LARGE_MODEL: LARGE_PRICE,
    "mistral-small-latest": _SMALL_PRICE,
    "mistral-small-2603": _SMALL_PRICE,
}


def short_call_model(mode: str, fast_model: str) -> str:
    """The model configured for a short call (`V1_FAST_MODEL` for the judge and the
    reformulation, `V1_REWRITE_MODEL` for the rewrite) under v1; mistral-large otherwise."""
    return fast_model if mode == "v1" else LARGE_MODEL


def price_for(model: str) -> Price:
    """USD per million tokens of `model`; an unknown model is priced as mistral-large."""
    return MODEL_PRICES.get(model, LARGE_PRICE)


def is_large(model: str) -> bool:
    """Whether `model` is a mistral-large version, i.e. shares its rate limiter."""
    return model.startswith("mistral-large")


def prompt_cache_key(mode: str, prompt: PromptName) -> str | None:
    """The fixed cache key of `prompt` under v1; None under any other mode (no key is sent).

    Shared by every tenant on purpose: a cache hit needs a token-identical prefix, and the
    system prompt that opens every call carries no client data. A tenant who sends the exact
    same following text (question, context) as another one extends that shared prefix: the
    hit reveals nothing it did not already send, but it is observable (j3-prompt-caching
    review)."""
    return PROMPT_CACHE_KEYS[prompt] if mode == "v1" else None


def cached_tokens_of(usage: UsageInfo | None) -> int:
    """`prompt_tokens_details.cached_tokens` from the SDK's untyped extras, clamped to
    [0, prompt_tokens]; 0 when absent, null or not an integer."""
    if usage is None:
        return 0
    details = (usage.model_extra or {}).get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    if not isinstance(cached, int) or isinstance(cached, bool):
        return 0
    return max(0, min(cached, usage.prompt_tokens or 0))


def input_cost_usd(prompt_tokens: int, cached_tokens: int, price: Price) -> float:
    """USD input cost: uncached tokens at the full input price, cached ones at
    CACHED_INPUT_PRICE_RATIO of it. `prompt_tokens` includes the cached ones."""
    uncached = prompt_tokens - cached_tokens
    cached_price = price["input"] * CACHED_INPUT_PRICE_RATIO
    return (uncached * price["input"] + cached_tokens * cached_price) / 1_000_000
