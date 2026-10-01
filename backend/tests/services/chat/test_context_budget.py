"""Tests for the score-ordered, budget-exact selection of chat context passages."""

import uuid

from app.schemas.search import SearchResult
from app.services.chat.context_budget import (
    document_order,
    render_context_parts,
    select_by_score,
)


def _chunk(
    text: str,
    *,
    score: float = 0.5,
    lot: str = "01",
    filename: str = "f",
    page: int = 1,
    position: int = 0,
) -> SearchResult:
    return SearchResult(
        text=text,
        page=page,
        position=position,
        filename=filename,
        document_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        project_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        score=score,
        lot=lot,
        phase="PRO",
        type="CCTP",
    )


def _texts(passages: list[SearchResult]) -> list[str]:
    return [p.text for p in passages]


def test_keeps_the_best_scored_passage_even_when_it_ends_the_document() -> None:
    passages = [
        _chunk("AAAA", score=0.3, page=1, position=0),
        _chunk("BBBB", score=0.5, page=2, position=1),
        _chunk("CCCC", score=0.9, page=3, position=2),
    ]
    budget = len("[f, p.2]\nBBBB") + len("\n---\n") + len("[f, p.3]\nCCCC")
    out = select_by_score(passages, context_max=budget, multiple_lots=False)
    assert _texts(out) == ["BBBB", "CCCC"]


def test_returns_the_retained_passages_in_document_order() -> None:
    passages = [
        _chunk("EEEE", score=0.9, page=5, position=5),
        _chunk("BBBB", score=0.8, page=1, position=1),
    ]
    out = select_by_score(passages, context_max=1000, multiple_lots=False)
    assert _texts(out) == ["BBBB", "EEEE"]


def test_stops_at_the_first_passage_by_score_that_does_not_fit() -> None:
    passages = [
        _chunk("AA", score=0.9, page=1, position=0),
        _chunk("B" * 50, score=0.8, page=2, position=1),
        _chunk("CC", score=0.7, page=3, position=2),
    ]
    out = select_by_score(passages, context_max=40, multiple_lots=False)
    assert _texts(out) == ["AA"]


def test_keeps_every_passage_when_their_full_rendering_fits() -> None:
    passages = [
        _chunk("CCCC", score=0.2, page=3, position=2),
        _chunk("AAAA", score=0.9, page=1, position=0),
        _chunk("BBBB", score=0.5, page=2, position=1),
    ]
    out = select_by_score(passages, context_max=1000, multiple_lots=False)
    assert _texts(out) == ["AAAA", "BBBB", "CCCC"]


def test_budget_counts_each_header() -> None:
    passages = [_chunk("AAAA", page=1)]
    exact = len("[f, p.1]\nAAAA")
    fits = select_by_score(passages, context_max=exact, multiple_lots=False)
    too_small = select_by_score(passages, context_max=exact - 1, multiple_lots=False)
    assert _texts(fits) == ["AAAA"]
    assert too_small == []


def test_budget_counts_the_join_between_passages() -> None:
    passages = [
        _chunk("AAAA", score=0.9, page=1, position=0),
        _chunk("BBBB", score=0.5, page=2, position=1),
    ]
    without_join = len("[f, p.1]\nAAAA") + len("[f, p.2]\nBBBB")
    short = select_by_score(passages, context_max=without_join, multiple_lots=False)
    enough = select_by_score(passages, context_max=without_join + 5, multiple_lots=False)
    assert _texts(short) == ["AAAA"]
    assert _texts(enough) == ["AAAA", "BBBB"]


def test_budget_counts_the_separator_and_its_join_when_a_new_lot_enters() -> None:
    passages = [
        _chunk("AAAA", score=0.9, lot="01", page=1, position=0),
        _chunk("BBBB", score=0.5, lot="04", page=2, position=0),
    ]
    first_only = len("\n=== 01 ===\n") + 5 + len("[f, p.1]\nAAAA")
    both = first_only + 5 + len("\n=== 04 ===\n") + 5 + len("[f, p.2]\nBBBB")
    short = select_by_score(passages, context_max=both - 1, multiple_lots=True)
    enough = select_by_score(passages, context_max=both, multiple_lots=True)
    assert _texts(short) == ["AAAA"]
    assert _texts(enough) == ["AAAA", "BBBB"]


def test_no_separator_for_a_lot_with_no_retained_passage() -> None:
    passages = [
        _chunk("AAAA", score=0.9, lot="01", page=1, position=0),
        _chunk("CCCC", score=0.8, lot="01", page=2, position=1),
        _chunk("B" * 50, score=0.5, lot="04", page=3, position=0),
    ]
    budget = (
        len("\n=== 01 ===\n")
        + 5
        + len("[f, p.1]\nAAAA")
        + 5
        + len("[f, p.2]\nCCCC")
    )
    out = select_by_score(passages, context_max=budget, multiple_lots=True)
    rendered = "\n---\n".join(render_context_parts(out, multiple_lots=True))
    assert _texts(out) == ["AAAA", "CCCC"]
    assert "=== 04 ===" not in rendered
    assert len(rendered) == budget


def test_budget_counts_the_merged_rendering_when_it_is_longer() -> None:
    passages = [
        _chunk("a", score=0.9, page=1, position=0),
        _chunk("A", score=0.5, page=2, position=1),
    ]
    plain_len = len("[f, p.1]\na\n---\n[f, p.2]\nA")
    merged_len = len("[f, p.1 ; aussi : f, p.2]\na")
    assert plain_len == 25
    assert merged_len == 27
    plain_fit = select_by_score(passages, context_max=25, multiple_lots=False)
    both_fit = select_by_score(passages, context_max=27, multiple_lots=False)
    assert _texts(plain_fit) == ["a"]
    assert _texts(both_fit) == ["a", "A"]


def test_score_ties_keep_the_earlier_passage_in_input_order() -> None:
    passages = [
        _chunk("XXXX", score=0.7, page=1, position=5),
        _chunk("YYYY", score=0.7, page=2, position=1),
    ]
    out = select_by_score(
        passages, context_max=len("[f, p.1]\nXXXX"), multiple_lots=False
    )
    assert _texts(out) == ["XXXX"]


def test_render_context_parts_reproduces_the_historical_layout() -> None:
    passages = [
        _chunk("A", lot="01", page=1, position=0),
        _chunk("B", lot="04", page=2, position=0),
        _chunk("C", lot="04", page=3, position=1),
    ]
    parts = render_context_parts(passages, multiple_lots=True)
    assert parts == [
        "\n=== 01 ===\n",
        "[f, p.1]\nA",
        "\n=== 04 ===\n",
        "[f, p.2]\nB",
        "[f, p.3]\nC",
    ]
    assert "\n---\n".join(parts) == (
        "\n=== 01 ===\n"
        "\n---\n"
        "[f, p.1]\nA"
        "\n---\n"
        "\n=== 04 ===\n"
        "\n---\n"
        "[f, p.2]\nB"
        "\n---\n"
        "[f, p.3]\nC"
    )


def test_render_context_parts_without_multiple_lots_has_no_separator() -> None:
    passages = [
        _chunk("A", lot="01", page=1, position=0),
        _chunk("B", lot="04", page=2, position=0),
        _chunk("C", lot="04", page=3, position=1),
    ]
    parts = render_context_parts(passages, multiple_lots=False)
    assert parts == ["[f, p.1]\nA", "[f, p.2]\nB", "[f, p.3]\nC"]


def test_document_order_sorts_by_lot_then_filename_then_position() -> None:
    no_lot = SearchResult.model_construct(
        text="t2",
        page=1,
        position=0,
        filename="z.pdf",
        document_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        project_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        score=0.5,
        lot=None,
        phase="PRO",
        type="CCTP",
    )
    passages = [
        _chunk("t1", lot="04", filename="a.pdf", position=0),
        no_lot,
        _chunk("t3", lot="01", filename="b.pdf", position=1),
        _chunk("t4", lot="01", filename="a.pdf", position=2),
        _chunk("t5", lot="01", filename="b.pdf", position=0),
    ]
    out = document_order(passages)
    assert _texts(out) == ["t4", "t5", "t3", "t1", "t2"]


def test_empty_input_retains_nothing() -> None:
    assert select_by_score([], context_max=100, multiple_lots=False) == []


def test_a_best_passage_larger_than_the_budget_retains_nothing() -> None:
    passages = [
        _chunk("A" * 50, score=0.9, page=1, position=0),
        _chunk("BB", score=0.5, page=2, position=1),
    ]
    out = select_by_score(passages, context_max=20, multiple_lots=False)
    assert out == []


def test_passages_sharing_lot_file_and_position_keep_their_input_order() -> None:
    passages = [
        _chunk("FIRST-ARRIVAL", score=0.5, page=1, position=3),
        _chunk("SECOND-ARRIVAL", score=0.9, page=2, position=3),
    ]
    out = select_by_score(passages, context_max=1000, multiple_lots=False)
    assert _texts(out) == ["FIRST-ARRIVAL", "SECOND-ARRIVAL"]
