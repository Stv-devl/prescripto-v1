"""Model routing of the short chat calls (query rewrite, sufficiency judge, retry
reformulation): which model each one calls, and at what price its usage is counted
(j3-routage-mistral-small). Generation always stays on mistral-large."""

from app.core.mistral import MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS

LARGE_MODEL = "mistral-large-latest"

Price = dict[str, float]

LARGE_PRICE: Price = MISTRAL_LARGE_PRICE_USD_PER_1M_TOKENS
_SMALL_PRICE: Price = {"input": 0.15, "output": 0.6}

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
