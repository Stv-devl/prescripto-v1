"""Test helpers for the per-question `chat_question` log record (J3)."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from app.core.log_config import QUESTION_LOGGER
from app.core.mistral import mistral_client


class _QuestionRecordCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def question_records() -> Iterator[list[logging.LogRecord]]:
    """Collect what is written on QUESTION_LOGGER through a handler attached directly to it.

    The logger is forced to INFO (a test file run alone never imports `app.main`) and its
    level and handlers are restored afterwards; `propagate` is left untouched."""
    logger = logging.getLogger(QUESTION_LOGGER)
    collector = _QuestionRecordCollector()
    previous_level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.INFO)
    try:
        yield collector.records
    finally:
        logger.removeHandler(collector)
        logger.setLevel(previous_level)


def parsed(records: list[logging.LogRecord]) -> list[dict[str, object]]:
    return [json.loads(record.getMessage()) for record in records]


def usage_event_of(events: list[dict[str, object] | str]) -> dict[str, dict[str, float]]:
    usage_events = [e for e in events if isinstance(e, dict) and "usage" in e]
    assert len(usage_events) == 1
    usage = usage_events[0]["usage"]
    assert isinstance(usage, dict)
    return usage


@contextmanager
def stream_raising_after_first_token(token: str) -> Iterator[None]:
    """Replace the generation stream by one that yields `token` once, then raises."""

    def _stream_async(*, model: str, messages: list[dict[str, str]], **kwargs: object) -> object:
        async def _gen() -> object:
            yield SimpleNamespace(
                data=SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=token))], usage=None
                )
            )
            raise RuntimeError("Mistral stream dropped")

        return _gen()

    with patch.object(mistral_client.chat, "stream_async", side_effect=_stream_async):
        yield
