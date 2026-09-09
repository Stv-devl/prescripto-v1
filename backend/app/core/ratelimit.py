"""Fixed-window rate limiting, in the memory of one process.

Deliberately not Redis: there is a single uvicorn process today, so an in-memory
count is exact and free. The day there is more than one instance this becomes
per-instance and the effective limit is multiplied by their number — that is a
decision for the AWS migration, not a defect of this module.

Nothing here knows about HTTP. That is what lets the whole thing be tested
without building a request, and it keeps `services/`-style layering intact.
"""

import math
import threading
import time
from collections.abc import Callable
from typing import NamedTuple


def _purge_interval_seconds(window_seconds: float) -> float:
    """How often expired keys are swept, capped at one minute.

    Reset buckets run on an hour; sweeping only once an hour would let a
    client rotating addresses pile up keys for that whole hour (measured at
    192 bytes each, so 1M keys is 192MB). A new key is always allowed, so
    nothing else slows their creation down.
    """
    return min(window_seconds, 60.0)


class Verdict(NamedTuple):
    """The answer to one attempt. `retry_after_seconds` is 0 when allowed."""

    allowed: bool
    retry_after_seconds: int


class _Window(NamedTuple):
    started_at: float
    count: int


class FixedWindowCounter:
    """Counts attempts per key over a fixed window.

    The clock is injected so expiry can be tested without waiting for real
    seconds, and `hit` takes a lock because FastAPI runs a synchronous
    dependency in its thread pool: `count + 1` would otherwise be a
    read-modify-write that two concurrent requests can both win.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._now = now
        self._windows: dict[str, _Window] = {}
        self._last_purge = now()
        self._purge_interval = _purge_interval_seconds(window_seconds)
        self._lock = threading.Lock()

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    @property
    def tracked_keys(self) -> int:
        """How many keys the structure still holds.

        Public on purpose: without it the purge could only be asserted as a
        black box, where the case would pass whether or not anything is ever
        forgotten, or against a private attribute.
        """
        with self._lock:
            return len(self._windows)

    def hit(self, key: str) -> Verdict:
        with self._lock:
            now = self._now()
            self._forget_expired(now)

            window = self._windows.get(key)
            if window is None or now - window.started_at >= self._window_seconds:
                window = _Window(started_at=now, count=0)

            if window.count >= self._limit:
                self._windows[key] = window
                remaining = self._window_seconds - (now - window.started_at)
                return Verdict(allowed=False, retry_after_seconds=max(1, math.ceil(remaining)))

            self._windows[key] = window._replace(count=window.count + 1)
            return Verdict(allowed=True, retry_after_seconds=0)

    def _forget_expired(self, now: float) -> None:
        """Drop keys whose window has passed, and only those.

        Never evicts a key that is still inside its window, whatever the memory
        pressure: an evicted key starts counting from zero again, so a cap that
        evicted live keys would let ordinary traffic wipe the count of exactly
        the client the limit exists to slow down.

        Swept at most once per window rather than on every call, so the cost
        stays bounded on a hot path.
        """
        if now - self._last_purge < self._purge_interval:
            return
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if now - window.started_at < self._window_seconds
        }
        self._last_purge = now


_counters: dict[str, FixedWindowCounter] = {}
_registry_lock = threading.Lock()


def counter_for(bucket: str, limit: int, window_seconds: float) -> FixedWindowCounter:
    """The process-wide counter for one bucket, created on first use.

    Raises when a bucket is asked for twice with different numbers: silently
    keeping the first would let a route declare a limit it never gets, and the
    mismatch would only show as traffic nobody metered the way they meant to.
    """
    with _registry_lock:
        counter = _counters.get(bucket)
        if counter is None:
            counter = FixedWindowCounter(limit, window_seconds)
            _counters[bucket] = counter
        elif (counter.limit, counter.window_seconds) != (limit, window_seconds):
            raise ValueError(
                f"rate-limit bucket {bucket!r} already exists as "
                f"{counter.limit}/{counter.window_seconds}s, asked for "
                f"{limit}/{window_seconds}s"
            )
        return counter


def reset_all() -> None:
    """Forget every counter. The test suite calls this between cases.

    Without it, a case that deliberately saturates a bucket leaks its count into
    whatever runs next, in an order nothing guarantees.
    """
    with _registry_lock:
        _counters.clear()
