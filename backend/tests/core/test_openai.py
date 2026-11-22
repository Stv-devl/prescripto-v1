import pytest
from openai import AsyncOpenAI

from app.core import openai as openai_module
from app.core.config import settings
from app.core.mistral import RateLimiter


@pytest.fixture(autouse=True)
def _fresh_client_cache() -> object:
    openai_module.get_openai_client.cache_clear()
    yield
    openai_module.get_openai_client.cache_clear()


def test_importing_the_module_builds_no_client_and_needs_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    assert openai_module.get_openai_client.cache_info().currsize == 0


def test_without_a_key_the_client_cannot_be_built(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        openai_module.get_openai_client()


def test_the_client_is_built_once_with_the_settings_key_and_no_hidden_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-never-called")

    first = openai_module.get_openai_client()
    second = openai_module.get_openai_client()

    assert first is second
    assert isinstance(first, AsyncOpenAI)
    assert first.api_key == "sk-test-never-called"
    assert first.max_retries == 0


def test_the_openai_limiter_is_a_rate_limiter() -> None:
    assert isinstance(openai_module.openai_limiter, RateLimiter)
