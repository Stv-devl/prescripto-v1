"""Request-local timings shared by child tasks, with task-local step names."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

_entries: ContextVar[list[tuple[str, int]] | None] = ContextVar("timing_entries", default=None)
_step: ContextVar[str | None] = ContextVar("timing_step", default=None)


def collect() -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    _entries.set(entries)
    return entries


def record(name: str, ms: int) -> None:
    entries = _entries.get()
    if entries is not None:
        entries.append((name, ms))


def current_step() -> str | None:
    return _step.get()


@contextmanager
def step(name: str) -> Iterator[None]:
    token = _step.set(name)
    started = perf_counter()
    try:
        yield
    finally:
        record(name, int((perf_counter() - started) * 1000))
        _step.reset(token)
