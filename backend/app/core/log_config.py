"""Logging setup for the per-question JSON record read by CloudWatch Logs Insights."""

import logging
import sys
from typing import TextIO

QUESTION_LOGGER = "app.chat_question"


class _QuestionLogHandler(logging.StreamHandler[TextIO]):
    """Marker subclass so a second configuration call can find the handler it added."""


def configure_question_logger(stream: TextIO = sys.stdout) -> None:
    """Print each per-question record as one bare JSON line on `stream`.

    The logger does not propagate, so the root handler never prints a prefixed copy that
    Logs Insights could not parse. Idempotent: a second call adds no handler."""
    logger = logging.getLogger(QUESTION_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(isinstance(handler, _QuestionLogHandler) for handler in logger.handlers):
        return
    handler = _QuestionLogHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
