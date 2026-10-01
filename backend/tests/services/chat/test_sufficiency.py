"""Tests for the sufficiency judge and the one-shot reformulation (agent v1).

Imported straight from `app.services.chat.sufficiency`. Mistral is doubled at its
single edge, `mistral_client.chat.complete_async`, patched on the name the module
looks up. The Mistral rate limiter is neutralised by `tests/conftest.py`.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mistralai.models import UsageInfo

from app.schemas.search import SearchResult
from app.services.chat.sufficiency import (
    Judgment,
    condense_passages,
    judge_sufficiency,
    merge_results,
    parse_judgment,
    parse_reformulation,
    reformulate,
    should_judge,
    should_retry,
)

DOC_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _result(
    text: str,
    *,
    page: int = 1,
    position: int = 1,
    score: float = 0.5,
) -> SearchResult:
    return SearchResult(
        text=text,
        page=page,
        position=position,
        filename="cctp.pdf",
        document_id=DOC_A,
        project_id=PROJECT,
        score=score,
        lot="gros oeuvre",
        phase="DCE",
        type="CCTP",
    )


def _usage() -> UsageInfo:
    return UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _install_mistral(monkeypatch: pytest.MonkeyPatch, content: str, usage: UsageInfo) -> AsyncMock:
    response = SimpleNamespace(
        usage=usage,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )
    complete = AsyncMock(return_value=response)
    monkeypatch.setattr(
        "app.services.chat.sufficiency.mistral_client",
        SimpleNamespace(chat=SimpleNamespace(complete_async=complete)),
    )
    return complete


def _install_failing_mistral(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    complete = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        "app.services.chat.sufficiency.mistral_client",
        SimpleNamespace(chat=SimpleNamespace(complete_async=complete)),
    )
    return complete


def _user_message(complete: AsyncMock) -> str:
    messages = complete.await_args.kwargs["messages"]
    users = [m["content"] for m in messages if m["role"] == "user"]
    assert len(users) == 1
    return users[0]


# --- Core behaviour ---


def test_should_judge_is_true_in_v1_on_a_broad_question_with_a_query_before_any_retry() -> None:
    assert should_judge("v1", "broad", has_query=True, retried=False) is True


def test_parse_judgment_insuffisant_returns_insufficient_with_the_missing_text() -> None:
    raw = '{"verdict": "insuffisant", "manque": "les cotes altimétriques"}'
    assert parse_judgment(raw) == Judgment(False, "les cotes altimétriques")


def test_parse_judgment_suffisant_returns_sufficient_with_empty_missing() -> None:
    raw = '{"verdict": "suffisant", "manque": "rien"}'
    assert parse_judgment(raw) == Judgment(True, "")


def test_should_retry_is_true_on_insufficient_when_no_retry_was_done() -> None:
    assert should_retry(Judgment(False, "les cotes"), retried=False) is True


def test_merge_results_keeps_first_results_in_order_then_appends_new_second_results_in_order() -> None:
    first = [_result("un", position=1), _result("deux", position=2)]
    second = [_result("trois", position=3), _result("quatre", position=4)]
    merged = merge_results(first, second)
    assert [r.text for r in merged] == ["un", "deux", "trois", "quatre"]


def test_merge_results_drops_a_second_result_with_the_same_document_page_position_and_text_keeping_the_first_copy_and_its_score() -> (
    None
):
    first = [_result("meme texte", page=2, position=3, score=0.9)]
    second = [
        _result("meme texte", page=2, position=3, score=0.1),
        _result("autre texte", page=2, position=4, score=0.2),
    ]
    merged = merge_results(first, second)
    assert [(r.text, r.score) for r in merged] == [("meme texte", 0.9), ("autre texte", 0.2)]


async def test_judge_sufficiency_returns_the_parsed_insufficient_judgment_and_records_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = _usage()
    _install_mistral(monkeypatch, '{"verdict": "insuffisant", "manque": "les cotes"}', usage)
    sink: list[UsageInfo] = []
    judgment = await judge_sufficiency(
        "Quelle est la cote du fond de fouille ?",
        "[cctp.pdf, p.2]\nTerrassement general",
        usage_sink=sink,
    )
    assert judgment == Judgment(False, "les cotes")
    assert sink == [usage]


async def test_reformulate_returns_the_parsed_query_and_records_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = _usage()
    _install_mistral(monkeypatch, '{"query": "cote altimetrique fond de fouille"}', usage)
    sink: list[UsageInfo] = []
    query = await reformulate(
        "Quelle est la cote du fond de fouille ?",
        "les cotes",
        first_query="fond de fouille",
        usage_sink=sink,
    )
    assert query == "cote altimetrique fond de fouille"
    assert sink == [usage]


# --- Business rules ---


def test_should_judge_is_false_on_a_specific_question_in_v1() -> None:
    assert should_judge("v1", "specific", has_query=True, retried=False) is False


def test_should_judge_is_false_in_baseline_even_on_a_broad_question() -> None:
    assert should_judge("baseline", "broad", has_query=True, retried=False) is False


def test_should_judge_is_false_without_a_query_off_topic() -> None:
    assert should_judge("v1", "broad", has_query=False, retried=False) is False


def test_should_judge_is_false_once_a_retry_was_done() -> None:
    assert should_judge("v1", "broad", has_query=True, retried=True) is False


def test_should_retry_is_false_on_sufficient() -> None:
    assert should_retry(Judgment(True, ""), retried=False) is False


def test_should_retry_is_false_once_a_retry_was_done() -> None:
    assert should_retry(Judgment(False, "les cotes"), retried=True) is False


def test_condense_passages_cuts_each_passage_to_max_chars_and_keeps_the_separator() -> None:
    block = "a" * 500 + "\n---\n" + "b" * 500
    assert condense_passages(block, max_chars=300) == "a" * 300 + "\n---\n" + "b" * 300


def test_condense_passages_keeps_short_passages_whole() -> None:
    block = "[cctp.pdf, p.1]\ncourt\n---\n[cctp.pdf, p.2]\nbref"
    assert condense_passages(block, max_chars=150) == block


async def test_judge_request_carries_the_question_and_the_condensed_passages_not_the_full_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete = _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    passage = "a" * 149 + "§" + "¤" + "d" * 40
    await judge_sufficiency(
        "Quelle epaisseur de dalle ?",
        passage + "\n---\n" + "e" * 20,
        usage_sink=[],
    )
    user = _user_message(complete)
    assert "Quelle epaisseur de dalle ?" in user
    assert "§" in user
    assert "¤" not in user


async def test_judge_on_an_empty_context_is_insufficient_with_empty_missing_without_calling_mistral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete = _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    judgment = await judge_sufficiency("Quelle epaisseur ?", "", usage_sink=[])
    assert judgment == Judgment(False, "")
    assert complete.await_count == 0


async def test_reformulate_request_carries_the_question_and_the_missing_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete = _install_mistral(monkeypatch, '{"query": "isolation thermique toiture"}', _usage())
    await reformulate(
        "Quel isolant en toiture ?",
        "la resistance thermique demandee",
        first_query="isolant toiture",
        usage_sink=[],
    )
    user = _user_message(complete)
    assert "Quel isolant en toiture ?" in user
    assert "la resistance thermique demandee" in user


def test_parse_reformulation_returning_the_first_query_up_to_case_and_spaces_is_none() -> None:
    raw = '{"query": "  Semelles Filantes  "}'
    assert parse_reformulation(raw, first_query="semelles filantes") is None


def test_merge_results_collapses_duplicates_inside_the_second_search_to_their_first_occurrence() -> None:
    second = [
        _result("repete", page=1, position=5, score=0.7),
        _result("repete", page=1, position=5, score=0.3),
        _result("unique", page=1, position=6, score=0.2),
    ]
    merged = merge_results([], second)
    assert [(r.text, r.score) for r in merged] == [("repete", 0.7), ("unique", 0.2)]


def test_merge_results_keeps_two_distinct_texts_sharing_document_page_and_position() -> None:
    first = [_result("premier sous-chunk", page=3, position=7)]
    second = [_result("second sous-chunk", page=3, position=7)]
    merged = merge_results(first, second)
    assert [r.text for r in merged] == ["premier sous-chunk", "second sous-chunk"]


# --- Edge cases ---


def test_should_judge_on_an_unknown_scope_is_false() -> None:
    assert should_judge("v1", "general", has_query=True, retried=False) is False


def test_parse_judgment_reads_a_json_fenced_reply() -> None:
    raw = '```json\n{"verdict": "insuffisant", "manque": "les cotes"}\n```'
    assert parse_judgment(raw) == Judgment(False, "les cotes")


def test_parse_judgment_verdict_is_case_and_whitespace_insensitive() -> None:
    raw = '{"verdict": "  Insuffisant ", "manque": "les cotes"}'
    assert parse_judgment(raw) == Judgment(False, "les cotes")


def test_parse_judgment_invalid_json_is_sufficient() -> None:
    assert parse_judgment("ceci n'est pas du json") == Judgment(True, "")


def test_parse_judgment_none_or_blank_is_sufficient() -> None:
    assert parse_judgment(None) == Judgment(True, "")
    assert parse_judgment("   ") == Judgment(True, "")


def test_parse_judgment_unknown_verdict_is_sufficient() -> None:
    assert parse_judgment('{"verdict": "peut-être", "manque": "x"}') == Judgment(True, "")


def test_parse_judgment_non_object_or_non_string_verdict_is_sufficient() -> None:
    assert parse_judgment("[]") == Judgment(True, "")
    assert parse_judgment('{"verdict": 1}') == Judgment(True, "")


def test_parse_judgment_insufficient_without_missing_keeps_empty_missing() -> None:
    assert parse_judgment('{"verdict": "insuffisant"}') == Judgment(False, "")


def test_parse_judgment_truncates_missing_to_300_characters() -> None:
    raw = '{"verdict": "insuffisant", "manque": "' + "x" * 500 + '"}'
    assert parse_judgment(raw) == Judgment(False, "x" * 300)


async def test_judge_sufficiency_on_a_mistral_exception_is_sufficient_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_mistral(monkeypatch)
    judgment = await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert judgment == Judgment(True, "")


async def test_judge_sufficiency_on_an_unreadable_reply_is_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_mistral(monkeypatch, "je ne sais pas repondre en json", _usage())
    judgment = await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert judgment == Judgment(True, "")


def test_parse_reformulation_reads_a_json_fenced_reply() -> None:
    raw = '```json\n{"query": "cote fond de fouille"}\n```'
    assert parse_reformulation(raw, first_query="fond de fouille") == "cote fond de fouille"


def test_parse_reformulation_blank_invalid_or_missing_query_is_none() -> None:
    assert parse_reformulation(None, first_query="q") is None
    assert parse_reformulation("   ", first_query="q") is None
    assert parse_reformulation("pas du json", first_query="q") is None
    assert parse_reformulation('{"autre": "x"}', first_query="q") is None
    assert parse_reformulation('{"query": "   "}', first_query="q") is None


def test_parse_reformulation_truncates_to_25_words() -> None:
    words = [f"mot{i}" for i in range(1, 31)]
    raw = '{"query": "' + " ".join(words) + '"}'
    expected = " ".join(f"mot{i}" for i in range(1, 26))
    assert parse_reformulation(raw, first_query="autre") == expected


async def test_reformulate_on_a_mistral_exception_is_none_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_mistral(monkeypatch)
    query = await reformulate("Quelle epaisseur ?", "les cotes", first_query="epaisseur", usage_sink=[])
    assert query is None


def test_merge_results_with_an_empty_side_returns_the_other_side() -> None:
    only = [_result("seul", position=1), _result("autre", position=2)]
    assert [r.text for r in merge_results(only, [])] == ["seul", "autre"]
    assert [r.text for r in merge_results([], only)] == ["seul", "autre"]


def test_merge_results_does_not_mutate_its_inputs() -> None:
    first = [_result("un", position=1)]
    second = [_result("deux", position=2), _result("un", position=1)]
    merge_results(first, second)
    assert [r.text for r in first] == ["un"]
    assert [r.text for r in second] == ["deux", "un"]


def test_condense_passages_of_an_empty_block_is_empty() -> None:
    assert condense_passages("") == ""


async def test_reformulate_request_with_an_empty_missing_says_it_is_not_specified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete = _install_mistral(monkeypatch, '{"query": "cotes NGF maison"}', _usage())
    await reformulate("Quelles sont les cotes ?", "", first_query="cotes", usage_sink=[])
    assert "Ce qui manque : non précisé" in _user_message(complete)


async def test_judge_in_v1_calls_the_configured_fast_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "retrieval_mode", "v1")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")
    complete = _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert complete.call_args.kwargs["model"] == "mistral-small-latest"


async def test_reformulate_in_v1_calls_the_configured_fast_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "retrieval_mode", "v1")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")
    complete = _install_mistral(monkeypatch, '{"query": "epaisseur dalle"}', _usage())
    await reformulate("Quelle epaisseur ?", "les cotes", first_query="epaisseur", usage_sink=[])
    assert complete.call_args.kwargs["model"] == "mistral-small-latest"


async def test_judge_in_baseline_calls_mistral_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "retrieval_mode", "baseline")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")
    complete = _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert complete.call_args.kwargs["model"] == "mistral-large-latest"


async def test_judge_in_v1_waits_on_the_fast_limiter_not_the_large_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.core.mistral import mistral_fast_limiter, mistral_large_limiter

    monkeypatch.setattr(settings, "retrieval_mode", "v1")
    monkeypatch.setattr(settings, "v1_fast_model", "mistral-small-latest")
    fast_wait = AsyncMock()
    large_wait = AsyncMock()
    monkeypatch.setattr(mistral_fast_limiter, "wait", fast_wait)
    monkeypatch.setattr(mistral_large_limiter, "wait", large_wait)
    _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert (fast_wait.await_count, large_wait.await_count) == (1, 0)


async def test_judge_in_baseline_waits_on_the_large_limiter_not_the_fast_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.core.mistral import mistral_fast_limiter, mistral_large_limiter

    monkeypatch.setattr(settings, "retrieval_mode", "baseline")
    fast_wait = AsyncMock()
    large_wait = AsyncMock()
    monkeypatch.setattr(mistral_fast_limiter, "wait", fast_wait)
    monkeypatch.setattr(mistral_large_limiter, "wait", large_wait)
    _install_mistral(monkeypatch, '{"verdict": "suffisant"}', _usage())
    await judge_sufficiency("Quelle epaisseur ?", "[cctp.pdf, p.1]\ntexte", usage_sink=[])
    assert (fast_wait.await_count, large_wait.await_count) == (0, 1)
