"""Tests for the chat context deduplication of article copies."""

import uuid

from app.schemas.search import SearchResult
from app.services.chat.context_dedup import (
    MergedPassage,
    article_dedup_key,
    merge_article_copies,
    passage_header,
    render_merged_context,
)

BODY = (
    "Réglementation thermique\n"
    "Le bâtiment doit respecter la RT 2012 pour l'ensemble des locaux chauffés du lot."
)
A1 = "1.1.3.9. " + BODY
A4 = "4.1.3.11. " + BODY
X = (
    "2.3.1.1. Enduit monocouche\n"
    "Enduit monocouche gratté de teinte claire sur l'ensemble des façades de la maison."
)
SHARED_SENTENCE = "Le bâtiment doit respecter la RT 2012"


def _chunk(
    text: str,
    *,
    page: int = 1,
    lot: str = "01",
    score: float = 0.5,
    position: int = 0,
) -> SearchResult:
    return SearchResult(
        text=text,
        page=page,
        position=position,
        filename="CCTP.pdf",
        document_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        project_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        score=score,
        lot=lot,
        phase="PRO",
        type="CCTP",
    )


def _merged(passages: list[SearchResult]) -> MergedPassage:
    merged = merge_article_copies(passages)
    assert len(merged) == 1
    return merged[0]


def _render_input() -> list[SearchResult]:
    return [
        _chunk(A1, lot="01", page=5, score=0.3),
        _chunk(A4, lot="04", page=46, score=0.9),
        _chunk(X, lot="04", page=50, score=0.5),
    ]


def test_two_passages_differing_only_by_their_leading_article_number_are_merged_into_one() -> None:
    out = merge_article_copies(
        [
            _chunk(A1, lot="01", page=5, score=0.5),
            _chunk(A4, lot="04", page=46, score=0.5),
        ]
    )
    assert len(out) == 1
    assert len(out[0].copies) == 2


def test_the_kept_copy_is_the_one_with_the_highest_score() -> None:
    out = merge_article_copies(
        [_chunk(A1, score=0.4), _chunk(A4, score=0.9)]
    )
    assert len(out) == 1
    assert out[0].kept.text == A4


def test_the_merged_header_names_file_and_page_of_every_copy_kept_copy_first() -> None:
    merged = _merged(
        [
            _chunk(A1, page=3, lot="01", score=0.5),
            _chunk(A4, page=27, lot="02", score=0.9),
            _chunk("5.5.5.5. " + BODY, page=36, lot="03", score=0.3),
        ]
    )
    assert passage_header(merged) == (
        "[CCTP.pdf, p.27 ; aussi : CCTP.pdf, p.3 ; CCTP.pdf, p.36]"
    )


def test_a_passage_without_copies_keeps_the_current_header_byte_for_byte() -> None:
    merged = _merged([_chunk(X, page=3, lot="01")])
    assert passage_header(merged) == "[CCTP.pdf, p.3]"


def test_rendered_context_contains_the_shared_text_once() -> None:
    out = render_merged_context(_render_input(), multiple_lots=True)
    assert out is not None
    assert out.count(SHARED_SENTENCE) == 1
    assert "Enduit monocouche gratté" in out


def test_key_strips_a_leading_article_number_without_final_dot() -> None:
    assert article_dedup_key("4.1.3.11 Texte") == "texte"
    assert article_dedup_key("1.2 Texte") == "texte"


def test_key_normalises_whitespace_and_case() -> None:
    assert article_dedup_key("1.1. Le  Bâtiment\n doit") == "le bâtiment doit"


def test_two_passages_without_article_number_but_identical_after_normalisation_are_merged() -> None:
    out = merge_article_copies(
        [
            _chunk("Texte  commun\nsuite du passage"),
            _chunk("texte commun suite du passage"),
        ]
    )
    assert len(out) == 1
    assert len(out[0].copies) == 2


def test_a_number_inside_the_text_is_not_stripped() -> None:
    out = merge_article_copies(
        [
            _chunk("Conforme au DTU 20.1. Sujétions"),
            _chunk("Conforme au DTU 26.1. Sujétions"),
        ]
    )
    assert len(out) == 2


def test_a_single_level_number_is_not_treated_as_an_article_number() -> None:
    out = merge_article_copies(
        [_chunk("1. Généralités"), _chunk("2. Généralités")]
    )
    assert len(out) == 2


def test_a_leading_decimal_quantity_is_not_treated_as_an_article_number() -> None:
    out = merge_article_copies(
        [
            _chunk("12.5 m² de carrelage grès cérame"),
            _chunk("15.0 m² de carrelage grès cérame"),
        ]
    )
    assert len(out) == 2


def test_passages_differing_by_a_quantity_are_not_merged() -> None:
    out = merge_article_copies(
        [
            _chunk("1.1. Chape de 12 m² en sous-sol"),
            _chunk("2.1. Chape de 15 m² en sous-sol"),
        ]
    )
    assert len(out) == 2


def test_passages_with_the_same_start_but_a_different_end_are_not_merged() -> None:
    out = merge_article_copies(
        [_chunk(A1), _chunk(A4 + "\n\n2.2.1.4. Poteau en bois")]
    )
    assert len(out) == 2


def test_merged_passage_takes_the_position_of_its_kept_copy_and_others_keep_their_order() -> None:
    out = merge_article_copies(
        [
            _chunk("Alpha"),
            _chunk(A1, score=0.3),
            _chunk("Beta"),
            _chunk(A4, score=0.9),
            _chunk("Gamma"),
        ]
    )
    assert [m.kept.text for m in out] == ["Alpha", "Beta", A4, "Gamma"]


def test_score_tie_keeps_the_first_copy_in_input_order() -> None:
    out = merge_article_copies(
        [_chunk(A1, score=0.5), _chunk(A4, score=0.5)]
    )
    assert len(out) == 1
    assert out[0].kept.text == A1


def test_a_copy_with_an_empty_lot_is_listed_without_lot() -> None:
    merged = _merged(
        [
            _chunk(A1, page=5, lot="01", score=0.9),
            _chunk(A4, page=46, lot="", score=0.5),
        ]
    )
    assert passage_header(merged) == "[CCTP.pdf, p.5 ; aussi : CCTP.pdf, p.46]"


def test_the_lot_is_never_part_of_the_merged_header() -> None:
    merged = _merged(
        [
            _chunk(A1, page=5, lot="01 - Gros oeuvre", score=0.9),
            _chunk(A4, page=46, lot="09 - Plomberie", score=0.5),
        ]
    )
    assert passage_header(merged) == "[CCTP.pdf, p.5 ; aussi : CCTP.pdf, p.46]"


def test_two_copies_on_the_same_page_in_different_lots_are_one_location() -> None:
    merged = _merged(
        [
            _chunk(A1, page=5, lot="01"),
            _chunk(A4, page=5, lot="04"),
        ]
    )
    assert passage_header(merged) == "[CCTP.pdf, p.5]"


def test_an_identical_location_is_listed_once() -> None:
    merged = _merged(
        [
            _chunk(A1, page=5, lot="01"),
            _chunk(A4, page=5, lot="01"),
        ]
    )
    assert passage_header(merged) == "[CCTP.pdf, p.5]"


def test_render_emits_a_lot_separator_only_for_lots_that_keep_a_passage() -> None:
    out = render_merged_context(_render_input(), multiple_lots=True)
    assert out is not None
    assert "\n=== 04 ===\n" in out
    assert "\n=== 01 ===\n" not in out


def test_render_without_multiple_lots_emits_no_separator() -> None:
    out = render_merged_context(_render_input(), multiple_lots=False)
    assert out is not None
    assert "===" not in out


def test_render_returns_none_when_no_key_is_shared() -> None:
    assert render_merged_context([_chunk(A1), _chunk(X)], multiple_lots=True) is None


def test_render_of_an_empty_input_returns_none() -> None:
    assert render_merged_context([], multiple_lots=True) is None


def test_a_leading_two_digit_decimal_quantity_is_not_partly_stripped() -> None:
    out = merge_article_copies(
        [
            _chunk("1.25 m² de carrelage grès cérame"),
            _chunk("1.35 m² de carrelage grès cérame"),
        ]
    )
    assert len(out) == 2


def test_a_leading_multi_level_quantity_keeps_its_key() -> None:
    assert article_dedup_key("1.2.3 ml de plinthe") == "1.2.3 ml de plinthe"


def test_the_unit_guard_ignores_case() -> None:
    out = merge_article_copies(
        [_chunk("12.5 M2 de carrelage"), _chunk("15.0 M2 de carrelage")]
    )
    assert len(out) == 2


def test_an_article_number_followed_by_an_elided_article_is_stripped() -> None:
    assert article_dedup_key("1.1.1. l'ouvrage comprend") == "l'ouvrage comprend"
