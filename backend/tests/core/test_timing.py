"""Collector isolation and durations, independent of wall-clock timing."""

import asyncio
from contextvars import Context

import pytest

from app.core import timing


def test_step_records_its_duration_in_ms(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([1.0, 1.25])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))
    entries = timing.collect()
    with timing.step("rewrite"):
        pass
    assert entries == [("rewrite", 250)]


def test_step_records_even_when_the_block_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([1.0, 1.5])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))
    entries = timing.collect()
    with pytest.raises(ValueError, match="failure"), timing.step("search"):
        raise ValueError("failure")
    assert entries == [("search", 500)]
    assert timing.current_step() is None


def test_record_without_collector_is_a_no_op() -> None:
    entries = timing.collect()
    assert Context().run(timing.record, "search", 123) is None
    assert entries == []


def test_step_sets_and_restores_the_current_step() -> None:
    assert timing.current_step() is None
    with timing.step("rewrite"):
        with timing.step("judge"):
            assert timing.current_step() == "judge"
        assert timing.current_step() == "rewrite"
    assert timing.current_step() is None


async def test_parallel_tasks_share_the_collector_but_not_the_current_step() -> None:
    entries = timing.collect()
    ready = asyncio.Event()
    seen: list[str | None] = []

    async def branch(name: str) -> None:
        with timing.step(name):
            if name == "generate":
                await ready.wait()
            else:
                ready.set()
                await asyncio.sleep(0)
            seen.append(timing.current_step())

    await asyncio.gather(branch("generate"), branch("extract_table"))
    assert set(seen) == {"generate", "extract_table"}
    assert {name for name, _ in entries} == {"generate", "extract_table"}
    assert all(isinstance(ms, int) and ms >= 0 for _, ms in entries)
    assert timing.current_step() is None


def test_collect_starts_a_separate_question() -> None:
    first = timing.collect()
    timing.record("search", 10)
    second = timing.collect()
    timing.record("search", 20)
    assert first == [("search", 10)]
    assert second == [("search", 20)]
