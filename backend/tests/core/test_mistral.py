"""Unit tests for _RateLimiter (backend/app/core/mistral.py).

Both the clock and asyncio.sleep are patched: nothing here waits on real time,
same discipline as test_ratelimit.py's injected clock.
"""

from unittest.mock import AsyncMock

import pytest

from app.core import mistral as mistral_module
from app.core.mistral import _RateLimiter


class TestFirstCall:
    async def test_the_first_call_does_not_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mistral_module.time, "monotonic", lambda: 1000.0)
        sleep = AsyncMock()
        monkeypatch.setattr(mistral_module.asyncio, "sleep", sleep)
        limiter = _RateLimiter(requests_per_second=0.25)

        await limiter.wait()

        sleep.assert_not_called()


class TestSerialization:
    async def test_a_second_call_at_the_same_instant_waits_the_full_interval(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mistral_module.time, "monotonic", lambda: 1000.0)
        sleep = AsyncMock()
        monkeypatch.setattr(mistral_module.asyncio, "sleep", sleep)
        limiter = _RateLimiter(requests_per_second=0.25)

        await limiter.wait()
        await limiter.wait()

        sleep.assert_called_once_with(4.0)

    async def test_a_call_after_the_interval_has_already_elapsed_does_not_sleep(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr(mistral_module.time, "monotonic", lambda: clock["now"])
        sleep = AsyncMock()
        monkeypatch.setattr(mistral_module.asyncio, "sleep", sleep)
        limiter = _RateLimiter(requests_per_second=0.25)

        await limiter.wait()
        clock["now"] += 10.0
        await limiter.wait()

        sleep.assert_not_called()

    async def test_three_calls_at_the_same_instant_space_out_by_the_interval_each(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mistral_module.time, "monotonic", lambda: 1000.0)
        sleep = AsyncMock()
        monkeypatch.setattr(mistral_module.asyncio, "sleep", sleep)
        limiter = _RateLimiter(requests_per_second=0.25)

        await limiter.wait()
        await limiter.wait()
        await limiter.wait()

        assert [call.args[0] for call in sleep.await_args_list] == [4.0, 8.0]


@pytest.fixture
def timing_limiter(monkeypatch: pytest.MonkeyPatch) -> _RateLimiter:
    from types import SimpleNamespace

    limiter = _RateLimiter(requests_per_second=0.25)
    monkeypatch.setattr(mistral_module, "time", SimpleNamespace(monotonic=lambda: 1000.0))
    monkeypatch.setattr(mistral_module, "asyncio", SimpleNamespace(sleep=AsyncMock()))
    return limiter


async def test_wait_returns_the_seconds_it_waited(timing_limiter: _RateLimiter) -> None:
    await timing_limiter.wait()
    assert await timing_limiter.wait() == 4.0


async def test_wait_returns_zero_when_no_wait_is_needed(timing_limiter: _RateLimiter) -> None:
    assert await timing_limiter.wait() == 0.0


async def test_wait_records_the_wait_under_the_current_step(timing_limiter: _RateLimiter) -> None:
    from app.core import timing

    entries = timing.collect()
    await timing_limiter.wait()
    with timing.step("generate"):
        await timing_limiter.wait()
    assert ("generate_wait", 4000) in entries


async def test_wait_records_nothing_outside_a_step(timing_limiter: _RateLimiter) -> None:
    from app.core import timing

    entries = timing.collect()
    await timing_limiter.wait()
    await timing_limiter.wait()
    assert entries == []


async def test_wait_records_zero_under_a_step(timing_limiter: _RateLimiter) -> None:
    from app.core import timing

    entries = timing.collect()
    with timing.step("rewrite"):
        await timing_limiter.wait()
    assert ("rewrite_wait", 0) in entries


@pytest.fixture
def api_requests(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Replaces the SDK's async HTTP client with a mock transport.

    Returns the list of JSON bodies the SDK actually sends. The transport answers
    a chat completion as JSON, or as an SSE stream when the body asks for one.
    """
    import json

    import httpx

    from app.core.mistral import mistral_client

    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append(body)
        if body.get("stream"):
            chunk = {
                "id": "cmpl-1",
                "model": "mistral-large-2512",
                "choices": [
                    {"index": 0, "delta": {"content": "Reponse streamee"}, "finish_reason": None}
                ],
            }
            sse = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=sse.encode()
            )
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "object": "chat.completion",
                "model": "mistral-large-2512",
                "created": 1700000000,
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Reponse simulee de l'API"},
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(mistral_client.sdk_configuration, "async_client", client)
    return sent


async def test_d1_a_large_latest_completion_is_sent_to_the_api_as_mistral_large_2512(
    api_requests: list[dict[str, object]],
) -> None:
    from app.core.mistral import mistral_client

    await mistral_client.chat.complete_async(
        model="mistral-large-latest", messages=[{"role": "user", "content": "x"}]
    )

    assert [body["model"] for body in api_requests] == ["mistral-large-2512"]


async def test_d2_a_large_latest_stream_is_sent_to_the_api_as_mistral_large_2512(
    api_requests: list[dict[str, object]],
) -> None:
    from app.core.mistral import mistral_client

    stream = await mistral_client.chat.stream_async(
        model="mistral-large-latest", messages=[{"role": "user", "content": "x"}]
    )
    async for _event in stream:
        pass

    assert [body["model"] for body in api_requests] == ["mistral-large-2512"]


async def test_d3_an_unpinned_model_is_sent_unchanged(
    api_requests: list[dict[str, object]],
) -> None:
    from app.core.mistral import mistral_client

    await mistral_client.chat.complete_async(
        model="mistral-small-latest", messages=[{"role": "user", "content": "x"}]
    )

    assert [body["model"] for body in api_requests] == ["mistral-small-latest"]


async def test_d4_the_completion_returned_to_the_caller_is_the_api_response(
    api_requests: list[dict[str, object]],
) -> None:
    from app.core.mistral import mistral_client

    response = await mistral_client.chat.complete_async(
        model="mistral-large-latest", messages=[{"role": "user", "content": "x"}]
    )

    assert response.choices[0].message.content == "Reponse simulee de l'API"
