"""Tests for the per-question JSON logger setup."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from app.core.log_config import QUESTION_LOGGER, configure_question_logger


@pytest.fixture
def question_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger(QUESTION_LOGGER)
    saved_handlers = list(logger.handlers)
    saved_propagate = logger.propagate
    saved_level = logger.level
    logger.handlers = []
    yield logger
    logger.handlers = saved_handlers
    logger.propagate = saved_propagate
    logger.setLevel(saved_level)


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_configured_logger_writes_one_bare_json_line(question_logger: logging.Logger) -> None:
    stream = io.StringIO()
    configure_question_logger(stream=stream)

    question_logger.info(json.dumps({"event": "chat_question", "cost_usd": 0.0033}))

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"event": "chat_question", "cost_usd": 0.0033}


def test_configured_logger_does_not_propagate_to_root(question_logger: logging.Logger) -> None:
    root_collector = _Collector()
    logging.getLogger().addHandler(root_collector)
    try:
        configure_question_logger(stream=io.StringIO())
        question_logger.info('{"event": "chat_question"}')
    finally:
        logging.getLogger().removeHandler(root_collector)

    assert root_collector.records == []


def test_info_record_is_written_even_when_app_logger_is_at_warning(
    question_logger: logging.Logger,
) -> None:
    app_logger = logging.getLogger("app")
    saved_app_level = app_logger.level
    app_logger.setLevel(logging.WARNING)
    stream = io.StringIO()
    try:
        configure_question_logger(stream=stream)
        question_logger.info('{"event": "chat_question"}')
    finally:
        app_logger.setLevel(saved_app_level)

    assert stream.getvalue() == '{"event": "chat_question"}\n'


def test_configuring_twice_adds_no_second_handler(question_logger: logging.Logger) -> None:
    stream = io.StringIO()
    configure_question_logger(stream=stream)
    configure_question_logger(stream=stream)

    question_logger.info('{"event": "chat_question"}')

    assert stream.getvalue().count("chat_question") == 1
