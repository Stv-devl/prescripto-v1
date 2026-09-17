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
