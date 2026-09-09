"""The chunking service: vision-specific strategies, and article enrichment.

Two files until the TDD mirror was repaired — `test_chunking.py` and
`test_chunking_enrichment.py` — both exercising
`app/services/ingestion/chunking.py`. The mirror is one module to one test file,
so they are joined here with their cases unchanged.
"""

from app.services.ingestion.chunking import (
    _classify_content_type,
    _detect_heading_level,
    _extract_keywords,
    _update_heading_stack,
    chunk_by_articles,
    chunk_fiche_sections,
    chunk_plan_pages,
)
from app.services.ingestion.extraction import ExtractedPage


class TestChunkPlanPages:
    def test_one_chunk_per_page(self) -> None:
        pages = [
            ExtractedPage(text="Plan RDC description", page=1, source="vision page 1"),
            ExtractedPage(text="Plan R+1 description", page=2, source="vision page 2"),
            ExtractedPage(text="Plan R+2 description", page=3, source="vision page 3"),
        ]
        chunks = chunk_plan_pages(pages)
        assert len(chunks) == 3
        assert chunks[0].text == "Plan RDC description"
        assert chunks[0].page == 1
        assert chunks[1].page == 2
        assert chunks[2].page == 3

    def test_empty_pages_skipped(self) -> None:
        pages = [
            ExtractedPage(text="Valid content", page=1, source="vision page 1"),
            ExtractedPage(text="", page=2, source="vision page 2"),
            ExtractedPage(text="   ", page=3, source="vision page 3"),
        ]
        chunks = chunk_plan_pages(pages)
        assert len(chunks) == 1
        assert chunks[0].page == 1


class TestChunkFicheSections:
    def test_splits_on_headings(self) -> None:
        pages = [
            ExtractedPage(
                text=(
                    "## Identification\nProduit XYZ\nRef: ABC-123\n\n"
                    "## Spécifications\nDimensions: 100x50x20\nPoids: 5kg\n\n"
                    "## Installation\nFixer au mur avec chevilles."
                ),
                page=1,
                source="vision page 1",
            ),
        ]
        chunks = chunk_fiche_sections(pages)
        assert len(chunks) == 3
        assert "Identification" in chunks[0].text
        assert "Spécifications" in chunks[1].text
        assert "Installation" in chunks[2].text

    def test_no_headings_falls_back_to_paragraphs(self) -> None:
        pages = [
            ExtractedPage(
                text="Just plain text without any markdown headings. " * 10,
                page=1,
                source="vision page 1",
            ),
        ]
        chunks = chunk_fiche_sections(pages)
        assert len(chunks) >= 1
        # Should still produce chunks (via paragraph fallback)

    def test_empty_returns_empty(self) -> None:
        pages = [ExtractedPage(text="", page=1, source="vision page 1")]
        chunks = chunk_fiche_sections(pages)
        assert chunks == []


class TestDetectHeadingLevel:
    def test_lot_heading(self) -> None:
        result = _detect_heading_level("LOT 03 - Maçonnerie")
        assert result is not None
        level, text = result
        assert level == 0
        assert "LOT 03" in text
        assert "Maçonnerie" in text

    def test_lot_heading_lowercase(self) -> None:
        result = _detect_heading_level("Lot 5 - Charpente bois")
        assert result is not None
        level, _ = result
        assert level == 0

    def test_article_heading(self) -> None:
        result = _detect_heading_level("2.3 - Semelles filantes")
        assert result is not None
        level, text = result
        assert level == 1
        assert "Semelles filantes" in text

    def test_article_heading_with_prefix(self) -> None:
        result = _detect_heading_level("Article 2.3 - Fondations")
        assert result is not None
        level, _ = result
        assert level == 1

    def test_subarticle_heading(self) -> None:
        result = _detect_heading_level("2.3.1 - Béton de propreté")
        assert result is not None
        level, text = result
        assert level == 2
        assert "Béton de propreté" in text

    def test_not_a_heading(self) -> None:
        assert _detect_heading_level("Le béton sera coulé en place.") is None

    def test_not_a_dimension(self) -> None:
        # "2.5 m" should NOT match as a heading (no [-–:.] separator + text)
        assert _detect_heading_level("2.5 m de profondeur") is None


class TestUpdateHeadingStack:
    def test_add_lot(self) -> None:
        stack = _update_heading_stack([], 0, "LOT 03 - Maçonnerie")
        assert stack == ["LOT 03 - Maçonnerie"]

    def test_add_article_under_lot(self) -> None:
        stack = _update_heading_stack(["LOT 03 - Maçonnerie"], 1, "2.3 - Semelles")
        assert stack == ["LOT 03 - Maçonnerie", "2.3 - Semelles"]

    def test_add_subarticle(self) -> None:
        stack = _update_heading_stack(
            ["LOT 03 - Maçonnerie", "2.3 - Semelles"], 2, "2.3.1 - Béton"
        )
        assert stack == ["LOT 03 - Maçonnerie", "2.3 - Semelles", "2.3.1 - Béton"]

    def test_new_article_truncates_subarticle(self) -> None:
        stack = _update_heading_stack(
            ["LOT 03 - Maçonnerie", "2.3 - Semelles", "2.3.1 - Béton"],
            1,
            "2.4 - Longrines",
        )
        assert stack == ["LOT 03 - Maçonnerie", "2.4 - Longrines"]

    def test_new_lot_resets_stack(self) -> None:
        stack = _update_heading_stack(
            ["LOT 03 - Maçonnerie", "2.3 - Semelles"], 0, "LOT 04 - Charpente"
        )
        assert stack == ["LOT 04 - Charpente"]


class TestClassifyContentType:
    def test_heading(self) -> None:
        assert _classify_content_type("LOT 03 - Maçonnerie") == "heading"

    def test_quantity_dominant(self) -> None:
        text = "Quantités: 25 m² de carrelage, 30 ml de plinthes, 5 U de regards, forfait nettoyage"
        result = _classify_content_type(text)
        assert result == "quantity"

    def test_admin_dominant(self) -> None:
        text = (
            "Conformément à la réglementation en vigueur, le titulaire devra "
            "respecter les prescriptions du CCTP. L'entrepreneur est responsable "
            "selon les règles de l'art. La réglementation impose des normes en vigueur."
        )
        result = _classify_content_type(text)
        assert result == "admin"

    def test_mixed_fallback(self) -> None:
        text = (
            "Le béton sera coulé en place. "
            "Épaisseur de 30 cm. "
            "Quantité: 5 m². "
            "Conformément à la norme."
        )
        result = _classify_content_type(text)
        assert result == "mixed"

    def test_empty_text(self) -> None:
        assert _classify_content_type("") == "mixed"


class TestExtractKeywords:
    def test_materials(self) -> None:
        kw = _extract_keywords("Semelle en béton armé avec acier HA")
        assert "béton" in kw

    def test_norms(self) -> None:
        kw = _extract_keywords("Selon DTU 13.12 et NF EN 206-1")
        assert any("dtu" in k for k in kw)

    def test_grades(self) -> None:
        kw = _extract_keywords("Béton C25/30 dosé à 350 kg/m3")
        assert "c25/30" in kw

    def test_performance(self) -> None:
        kw = _extract_keywords("Menuiserie aluminium Uw=1.4 W/m²K")
        assert any("uw" in k for k in kw)

    def test_max_10_keywords(self) -> None:
        """The cap is 10 — chunking.py `sorted(keywords)[:10]`, same cap on merge."""
        text = (
            "Béton C25/30, acier HA, bois, PVC, aluminium, zinc, cuivre, "
            "DTU 13.12, NF EN 206-1, RAL 7016, Ug=1.1"
        )
        kw = _extract_keywords(text)
        assert len(kw) <= 10

    def test_no_keywords(self) -> None:
        kw = _extract_keywords("Le titulaire devra respecter les délais.")
        assert kw == []


class TestChunkByArticlesEnrichment:
    def test_heading_metadata_propagated(self) -> None:
        text = (
            "LOT 03 - Maçonnerie\n\n"
            "3.1 - Fondations\n"
            "Les fondations seront réalisées en béton armé C25/30.\n\n"
            "3.2 - Élévations\n"
            "Les murs en parpaing de 20 cm."
        )
        pages = [ExtractedPage(text=text, page=1, source="test")]
        chunks = chunk_by_articles(pages)
        assert len(chunks) >= 2

        # Check that chunks have metadata
        for chunk in chunks:
            assert chunk.char_count > 0
            assert isinstance(chunk.content_type, str)
            assert isinstance(chunk.keywords, list)

    def test_lot_detected_in_chunks(self) -> None:
        text = (
            "LOT 02 - Gros oeuvre\n\n"
            "2.1 - Terrassement\n"
            "Fouilles en rigole pour semelles.\n\n"
            "2.2 - Béton\n"
            "Béton C25/30 pour semelles filantes."
        )
        pages = [ExtractedPage(text=text, page=1, source="test")]
        chunks = chunk_by_articles(pages)

        # At least some chunks should have chunk_lot set
        lots = [c.chunk_lot for c in chunks if c.chunk_lot]
        assert len(lots) > 0
        assert any("02" in lot for lot in lots)

    def test_heading_prefix_built(self) -> None:
        text = (
            "LOT 01 - VRD\n\n"
            "1.1 - Réseaux\n"
            "Pose de canalisations PVC."
        )
        pages = [ExtractedPage(text=text, page=1, source="test")]
        chunks = chunk_by_articles(pages)

        # At least one chunk should have a heading_prefix with " > "
        prefixes = [c.heading_prefix for c in chunks if " > " in c.heading_prefix]
        assert len(prefixes) > 0
