"""Tests for _parse_rewrite_response with related queries.

Imported straight from `app.services.chat.query_rewrite`, not from the `chat`
package: the mirror says this file covers that module, and importing through the
re-export would leave nothing in the file naming what it exercises.
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.chat.query_rewrite import (
    _parse_rewrite_response,
    has_normative_reference,
    rewrite_query,
)


class TestParseRewriteResponse:
    def test_full_json_with_related(self) -> None:
        raw = '{"query": "semelles filantes béton", "related": ["fond de fouille terrassement", "gros béton propreté"], "scope": "specific", "structured": "table", "schema": "schema"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "semelles filantes béton"
        assert related == ["fond de fouille terrassement", "gros béton propreté"]
        assert scope == "specific"
        assert structured == "table"
        assert schema == "schema"

    def test_json_without_related(self) -> None:
        raw = '{"query": "isolation murs", "scope": "specific", "structured": "none", "schema": "none"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "isolation murs"
        assert related == []
        assert scope == "specific"

    def test_json_with_empty_related(self) -> None:
        raw = '{"query": "lots du projet", "related": [], "scope": "broad", "structured": "none", "schema": "none"}'
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == "lots du projet"
        assert related == []
        assert scope == "broad"

    def test_related_max_2(self) -> None:
        raw = '{"query": "test", "related": ["a", "b", "c", "d"], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert len(related) == 2

    def test_related_strips_whitespace(self) -> None:
        raw = '{"query": "test", "related": ["  foo  ", "  bar  "], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == ["foo", "bar"]

    def test_related_filters_empty_strings(self) -> None:
        raw = '{"query": "test", "related": ["valid", "", "  "], "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == ["valid"]

    def test_related_non_list_ignored(self) -> None:
        raw = '{"query": "test", "related": "not a list", "scope": "specific", "structured": "none", "schema": "none"}'
        _, related, _, _, _ = _parse_rewrite_response(raw)
        assert related == []

    def test_fallback_raw_string(self) -> None:
        raw = "not valid json at all"
        query, related, scope, structured, schema = _parse_rewrite_response(raw)
        assert query == raw
        assert related == []
        assert scope == "specific"
        assert structured == "none"
        assert schema == "none"

    def test_markdown_code_fences_stripped(self) -> None:
        raw = '```json\n{"query": "test query", "related": ["rel1"], "scope": "specific", "structured": "none", "schema": "none"}\n```'
        query, related, scope, _, _ = _parse_rewrite_response(raw)
        assert query == "test query"
        assert related == ["rel1"]

    def test_invalid_scope_defaults_specific(self) -> None:
        raw = '{"query": "test", "scope": "invalid", "structured": "none", "schema": "none"}'
        _, _, scope, _, _ = _parse_rewrite_response(raw)
        assert scope == "specific"

    def test_invalid_structured_defaults_none(self) -> None:
        raw = '{"query": "test", "scope": "specific", "structured": "invalid", "schema": "none"}'
        _, _, _, structured, _ = _parse_rewrite_response(raw)
        assert structured == "none"


class TestHasNormativeReference:
    """Whole-token detection of normative references in a user question."""

    def test_dtu_reference_detected(self) -> None:
        question = "Quel DTU définit la qualité d'exécution des maçonneries ?"
        assert has_normative_reference(question) is True

    def test_nf_c_15_100_detected(self) -> None:
        assert has_normative_reference("Que dit la NF C 15-100 sur les prises ?") is True

    def test_en_followed_by_number_detected(self) -> None:
        question = "Ces ardoises sont-elles conformes selon l'EN 12326 ?"
        assert has_normative_reference(question) is True

    def test_norme_word_detected(self) -> None:
        assert has_normative_reference("Quelle est la norme applicable ?") is True

    def test_eurocode_detected(self) -> None:
        assert has_normative_reference("Que dit l'Eurocode 2 sur le béton armé ?") is True

    def test_reglementation_detected(self) -> None:
        assert has_normative_reference("Que dit la réglementation thermique ?") is True

    def test_re2020_attached_detected(self) -> None:
        assert has_normative_reference("Le projet respecte-t-il la RE2020 ?") is True

    def test_re_2020_spaced_detected(self) -> None:
        assert has_normative_reference("Le projet respecte-t-il la RE 2020 ?") is True

    def test_rt2012_attached_detected(self) -> None:
        assert has_normative_reference("Le projet respecte-t-il la RT2012 ?") is True

    def test_rt_2012_spaced_detected(self) -> None:
        assert has_normative_reference("Le projet respecte-t-il la RT 2012 ?") is True

    def test_nf_alone_detected(self) -> None:
        assert has_normative_reference("Cette exigence vient-elle d'une NF ?") is True

    def test_eurocodes_plural_detected(self) -> None:
        assert has_normative_reference("Que disent les Eurocodes sur les charges ?") is True

    def test_plain_building_question_not_detected(self) -> None:
        assert has_normative_reference("Combien de fenêtres en façade ?") is False

    def test_french_word_en_never_triggers(self) -> None:
        assert has_normative_reference("Peux-tu m'expliquer le mot en français ?") is False

    def test_off_topic_question_not_detected(self) -> None:
        assert has_normative_reference("Quelle est la capitale de la France ?") is False

    def test_empty_question_not_detected(self) -> None:
        assert has_normative_reference("") is False

    def test_en_alone_without_number_not_detected(self) -> None:
        assert has_normative_reference("Le lot est en cours") is False

    def test_dtu_inside_longer_word_not_detected(self) -> None:
        assert has_normative_reference("Le dtuxyz est absent") is False

    def test_nf_inside_longer_word_not_detected(self) -> None:
        assert has_normative_reference("Le nfc du lot est cité") is False

    def test_re_without_2020_not_detected(self) -> None:
        assert has_normative_reference("Le projet est en RE avec 2021") is False

    def test_case_insensitive(self) -> None:
        assert has_normative_reference("QUEL DTU S'APPLIQUE ?") is True

    def test_accent_insensitive(self) -> None:
        assert has_normative_reference("Quelle REGLEMENTATION s'applique ?") is True
        assert has_normative_reference("Quelle réglementation s'applique ?") is True

    def test_hyphenated_reference_detected(self) -> None:
        assert has_normative_reference("Que dit le DTU-20.1 ?") is True

    def test_nf_en_combined_detected(self) -> None:
        assert has_normative_reference("Selon la NF EN 13501-1, quel classement ?") is True

    def test_plural_normes_detected(self) -> None:
        assert has_normative_reference("Quelles normes s'appliquent ?") is True


NORMATIVE_QUESTION = "Quel DTU définit la qualité d'exécution des maçonneries ?"
PLAIN_QUESTION = "Combien de fenêtres en façade ?"
OFF_TOPIC_QUESTION = "Quelle est la capitale de la France ?"
NORMAL_JSON = (
    '{"query": "DTU 20.1 qualité maçonneries", "related": ["exécution maçonnerie"], '
    '"scope": "specific", "structured": "none", "schema": "none"}'
)


def _fake_mistral(content: str) -> SimpleNamespace:
    reponse = SimpleNamespace(
        usage=SimpleNamespace(),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )
    return SimpleNamespace(chat=SimpleNamespace(complete_async=AsyncMock(return_value=reponse)))


def _failing_mistral() -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(complete_async=AsyncMock(side_effect=RuntimeError("boom")))
    )


def _has_error_record(caplog: pytest.LogCaptureFixture) -> bool:
    return any(r.levelno >= logging.ERROR for r in caplog.records)


def _has_guard_record(caplog: pytest.LogCaptureFixture) -> bool:
    return any(r.levelno == logging.INFO and "Rewrite guard" in r.getMessage() for r in caplog.records)


class TestRewriteQueryGuard:
    """The v1-only guard that keeps normative questions out of HORS_SUJET."""

    async def test_v1_off_topic_on_normative_question_returns_raw_question(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral("HORS_SUJET"))
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "Quel DTU définit la qualité d'exécution des maçonneries ?",
            [],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)
        assert _has_guard_record(caplog)

    async def test_v1_guard_logs_event_in_english_without_question_text(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral("HORS_SUJET"))
        await rewrite_query(NORMATIVE_QUESTION, [])
        assert not _has_error_record(caplog)
        assert _has_guard_record(caplog)
        messages = [r.getMessage() for r in caplog.records]
        assert not any("maçonneries" in message for message in messages)

    async def test_v1_off_topic_reply_with_extra_text_still_guarded(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr(
            "app.services.chat.query_rewrite.mistral_client",
            _fake_mistral("HORS_SUJET — pas de rapport"),
        )
        result = await rewrite_query("Quelle norme NF est citée pour l'électricité ?", [])
        assert result == (
            "Quelle norme NF est citée pour l'électricité ?",
            [],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)
        assert _has_guard_record(caplog)

    async def test_baseline_off_topic_on_normative_question_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "baseline")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral("HORS_SUJET"))
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (None, [], "specific", "none", "none")
        assert not _has_error_record(caplog)
        assert not _has_guard_record(caplog)

    async def test_v1_off_topic_without_normative_reference_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral("HORS_SUJET"))
        result = await rewrite_query(OFF_TOPIC_QUESTION, [])
        assert result == (None, [], "specific", "none", "none")
        assert not _has_error_record(caplog)
        assert not _has_guard_record(caplog)

    async def test_v1_normal_reply_on_normative_question_untouched(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral(NORMAL_JSON))
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "DTU 20.1 qualité maçonneries",
            ["exécution maçonnerie"],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)
        assert not _has_guard_record(caplog)

    async def test_v1_normal_reply_on_plain_question_untouched(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral(NORMAL_JSON))
        result = await rewrite_query(PLAIN_QUESTION, [])
        assert result == (
            "DTU 20.1 qualité maçonneries",
            ["exécution maçonnerie"],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)
        assert not _has_guard_record(caplog)

    async def test_baseline_normal_reply_untouched(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr(settings, "retrieval_mode", "baseline")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral(NORMAL_JSON))
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "DTU 20.1 qualité maçonneries",
            ["exécution maçonnerie"],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)
        assert not _has_guard_record(caplog)

    async def test_guard_reads_mode_at_call_time(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="app.services.chat.query_rewrite")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral("HORS_SUJET"))
        monkeypatch.setattr(settings, "retrieval_mode", "baseline")
        first = await rewrite_query(NORMATIVE_QUESTION, [])
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        second = await rewrite_query(NORMATIVE_QUESTION, [])
        assert first == (None, [], "specific", "none", "none")
        assert second == (
            "Quel DTU définit la qualité d'exécution des maçonneries ?",
            [],
            "specific",
            "none",
            "none",
        )
        assert not _has_error_record(caplog)

    async def test_v1_model_exception_falls_back_to_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _failing_mistral())
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "Quel DTU définit la qualité d'exécution des maçonneries ?",
            [],
            "specific",
            "none",
            "none",
        )

    async def test_baseline_model_exception_falls_back_to_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "retrieval_mode", "baseline")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _failing_mistral())
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "Quel DTU définit la qualité d'exécution des maçonneries ?",
            [],
            "specific",
            "none",
            "none",
        )

    async def test_v1_empty_model_reply_falls_back_to_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "retrieval_mode", "v1")
        monkeypatch.setattr("app.services.chat.query_rewrite.mistral_client", _fake_mistral(""))
        result = await rewrite_query(NORMATIVE_QUESTION, [])
        assert result == (
            "Quel DTU définit la qualité d'exécution des maçonneries ?",
            [],
            "specific",
            "none",
            "none",
        )
