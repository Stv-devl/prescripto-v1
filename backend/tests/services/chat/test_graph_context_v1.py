"""Context cutoff of the chat graph under RETRIEVAL_MODE=v1 (fused RRF scores)."""

import uuid

import pytest

from app.schemas.search import SearchResult
from app.services.chat.graph import _build_context_and_sources

DOCUMENT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _chunk(
    text: str,
    *,
    score: float,
    type_: str = "CCTP",
    filename: str = "cctp-gros-oeuvre.pdf",
    page: int = 3,
    position: int = 0,
) -> SearchResult:
    return SearchResult(
        text=text,
        page=page,
        position=position,
        filename=filename,
        document_id=DOCUMENT_ID,
        project_id=PROJECT_ID,
        score=score,
        lot="02 - Gros oeuvre",
        phase="PRO",
        type=type_,
    )


def test_v1_keeps_a_chunk_scored_0_2_when_the_requested_threshold_is_0_40(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    results = [
        _chunk(
            "Beton de fondation C25/30 conforme au DTU 21, epaisseur minimale 30 cm, coulage par temps sec.",
            score=0.2,
            filename="fused.pdf",
            page=7,
        )
    ]

    context, sources = _build_context_and_sources(
        results, score_threshold=0.40, context_max=10_000, max_sources=10
    )

    assert "Beton de fondation C25/30 conforme au DTU 21, epaisseur minimale 30 cm, coulage par temps sec." in context
    assert [(s.filename, s.page) for s in sources] == [("fused.pdf", 7)]


def test_baseline_drops_the_chunk_scored_0_2_under_a_threshold_of_0_40(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
    results = [
        _chunk(
            "Beton de fondation C25/30 conforme au DTU 21, epaisseur minimale 30 cm, coulage par temps sec.",
            score=0.2,
            filename="fused.pdf",
            page=7,
        )
    ]

    context, sources = _build_context_and_sources(
        results, score_threshold=0.40, context_max=10_000, max_sources=10
    )

    assert "Beton de fondation C25/30 conforme au DTU 21, epaisseur minimale 30 cm, coulage par temps sec." not in context
    assert sources == []


@pytest.mark.parametrize("mode", ["v1", "baseline"])
def test_dpgf_chunk_under_the_threshold_is_kept_in_both_modes(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", mode)
    results = [
        _chunk(
            "Poste 2.1 fondations superficielles, 45 m3 a 180 euros, fourniture et mise en oeuvre comprises.",
            score=0.2,
            type_="DPGF",
            filename="dpgf.pdf",
            page=2,
        )
    ]

    context, sources = _build_context_and_sources(
        results, score_threshold=0.40, context_max=10_000, max_sources=10
    )

    assert "Poste 2.1 fondations superficielles, 45 m3 a 180 euros, fourniture et mise en oeuvre comprises." in context
    assert [(s.filename, s.page) for s in sources] == [("dpgf.pdf", 2)]


def test_v1_deduplicates_chunks_sharing_their_first_200_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    shared_prefix = "Les ouvrages de maconnerie sont realises selon le DTU 20.1. " * 4
    assert len(shared_prefix) > 200
    results = [
        _chunk(shared_prefix + "TAIL-ALPHA", score=0.05, position=0),
        _chunk(shared_prefix + "TAIL-BETA", score=0.04, position=1),
    ]

    context, _ = _build_context_and_sources(
        results, score_threshold=0.40, context_max=10_000, max_sources=10
    )

    assert "TAIL-ALPHA" in context
    assert "TAIL-BETA" not in context


def test_v1_context_max_bound_still_applies_and_drops_what_does_not_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    first = "FIRST-CHUNK " + "a" * 288
    second = "SECOND-CHUNK " + "b" * 287
    assert len(first) == 300 and len(second) == 300
    results = [
        _chunk(first, score=0.05, position=0),
        _chunk(second, score=0.04, position=1),
    ]

    context, _ = _build_context_and_sources(
        results, score_threshold=0.40, context_max=500, max_sources=10
    )

    assert "FIRST-CHUNK" in context
    assert "SECOND-CHUNK" not in context
    assert len(context) <= 500


HEAD = "HEAD-PASSAGE " + "a" * 87
MIDDLE = "MIDDLE-PASSAGE " + "b" * 85
END = "END-PASSAGE " + "c" * 88
PART_LENGTH = len("[cctp.pdf, p.1]\n") + 100


def _passage(text: str, *, score: float, page: int, position: int, lot: str = "02") -> SearchResult:
    return SearchResult(
        text=text,
        page=page,
        position=position,
        filename="cctp.pdf",
        document_id=DOCUMENT_ID,
        project_id=PROJECT_ID,
        score=score,
        lot=lot,
        phase="PRO",
        type="CCTP",
    )


def _head_middle_end() -> list[SearchResult]:
    return [
        _passage(HEAD, score=0.45, page=1, position=0),
        _passage(MIDDLE, score=0.6, page=2, position=1),
        _passage(END, score=0.9, page=3, position=2),
    ]


def test_v1_cut_keeps_the_best_scored_passage_at_the_end_of_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    assert len(HEAD) == len(MIDDLE) == len(END) == 100 and PART_LENGTH == 116

    context, _ = _build_context_and_sources(
        _head_middle_end(), score_threshold=0.40, context_max=237, max_sources=10
    )

    assert context == "[cctp.pdf, p.2]\n" + MIDDLE + "\n---\n" + "[cctp.pdf, p.3]\n" + END


def test_v1_sources_follow_the_retained_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")

    _, sources = _build_context_and_sources(
        _head_middle_end(), score_threshold=0.40, context_max=237, max_sources=10
    )

    assert [(s.filename, s.page) for s in sources] == [("cctp.pdf", 2), ("cctp.pdf", 3)]


def test_v1_rendered_context_never_exceeds_context_max_counting_the_joins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")

    context, _ = _build_context_and_sources(
        _head_middle_end(), score_threshold=0.40, context_max=348, max_sources=10
    )

    assert len(context) <= 348
    assert "HEAD-PASSAGE" not in context
    assert "END-PASSAGE" in context


def test_v1_rendered_context_with_merged_copies_stays_within_context_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    body = (
        "Réglementation thermique\n"
        "Le bâtiment doit respecter la RT 2012 pour l'ensemble des locaux chauffés du lot."
    )
    results = [
        _passage("1.1.3.9. " + body, score=0.9, page=5, position=0, lot="01"),
        _passage("4.1.3.11. " + body, score=0.6, page=46, position=0, lot="04"),
        _passage(END, score=0.7, page=50, position=1, lot="04"),
    ]

    context, _ = _build_context_and_sources(
        results, score_threshold=0.40, context_max=300, max_sources=10
    )

    assert len(context) <= 300
    assert "Le bâtiment doit respecter la RT 2012" in context


def test_baseline_cut_still_fills_in_document_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")

    context, sources = _build_context_and_sources(
        _head_middle_end(), score_threshold=0.40, context_max=237, max_sources=10
    )

    assert context == "[cctp.pdf, p.1]\n" + HEAD + "\n---\n" + "[cctp.pdf, p.2]\n" + MIDDLE
    assert [(s.filename, s.page) for s in sources] == [("cctp.pdf", 1), ("cctp.pdf", 2)]


def test_v1_context_is_unchanged_when_everything_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")

    context, sources = _build_context_and_sources(
        _head_middle_end(), score_threshold=0.40, context_max=20000, max_sources=10
    )

    assert context == (
        "[cctp.pdf, p.1]\n"
        + HEAD
        + "\n---\n"
        + "[cctp.pdf, p.2]\n"
        + MIDDLE
        + "\n---\n"
        + "[cctp.pdf, p.3]\n"
        + END
    )
    assert [(s.filename, s.page) for s in sources] == [
        ("cctp.pdf", 1),
        ("cctp.pdf", 2),
        ("cctp.pdf", 3),
    ]


def test_v1_keeps_the_lot_separator_when_a_single_lot_survives_the_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
    results = [
        _passage(END, score=0.9, page=3, position=2, lot="01"),
        _passage(HEAD, score=0.45, page=1, position=0, lot="04"),
    ]

    context, _ = _build_context_and_sources(
        results, score_threshold=0.40, context_max=200, max_sources=10
    )

    assert context == "\n=== 01 ===\n" + "\n---\n" + "[cctp.pdf, p.3]\n" + END
