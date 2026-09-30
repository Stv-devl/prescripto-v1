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
