"""Tests for the vision extraction module."""

import base64
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion.extraction import ExtractedPage
from app.services.ingestion.vision import (
    PageImage,
    classify_page_by_vision,
    describe_fiche_page,
    describe_plan_page,
    extract_with_vision,
    ocr_sparse_pages,
    pdf_pages_to_images,
)


class TestPdfPagesToImages:
    def test_converts_pages_to_base64(self, tmp_pdf_empty: Path) -> None:
        images = pdf_pages_to_images(tmp_pdf_empty, dpi=72)
        assert len(images) == 2
        for img in images:
            assert isinstance(img, PageImage)
            assert img.page_number in (1, 2)
            # Verify valid base64
            decoded = base64.b64decode(img.image_base64)
            assert decoded[:4] == b"\x89PNG"

    def test_exceeds_limit_raises(self, tmp_pdf_many_pages: Path) -> None:
        with pytest.raises(ValueError, match="exceeds limit"):
            pdf_pages_to_images(tmp_pdf_many_pages)


class TestDescribePlanPage:
    @pytest.mark.asyncio
    async def test_returns_extracted_page(self, mock_pixtral_response: MagicMock) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            result = await describe_plan_page("fake_base64", page_number=3)

        assert isinstance(result, ExtractedPage)
        assert result.page == 3
        assert result.source == "vision page 3"
        assert "Description" in result.text


class TestDescribeFichePage:
    @pytest.mark.asyncio
    async def test_returns_extracted_page(self, mock_pixtral_response: MagicMock) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            result = await describe_fiche_page("fake_base64", page_number=5)

        assert isinstance(result, ExtractedPage)
        assert result.page == 5
        assert result.source == "vision page 5"


class TestExtractWithVision:
    @pytest.mark.asyncio
    async def test_plan_full_vision(
        self,
        tmp_pdf_empty: Path,
        tenant_id: uuid.UUID,
        mock_pixtral_response: MagicMock,
    ) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            pages = await extract_with_vision(tmp_pdf_empty, "plan", tenant_id)

        assert len(pages) == 2
        assert all(p.source.startswith("vision page") for p in pages)

    @pytest.mark.asyncio
    async def test_fiche_hybrid_mode(
        self,
        tmp_pdf_with_text: Path,
        tenant_id: uuid.UUID,
        sample_extracted_pages: list[ExtractedPage],
        mock_pixtral_response: MagicMock,
    ) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            pages = await extract_with_vision(
                tmp_pdf_with_text,
                "fiche_technique",
                tenant_id,
                text_pages=sample_extracted_pages,
            )

        # Page 1: <50 chars → skipped
        # Page 2: 50-200 chars → vision
        # Page 3: >200 chars → kept text
        assert len(pages) == 2
        # One page should be vision, one should be original text
        sources = {p.source for p in pages}
        assert "vision page 2" in sources
        assert "page 3" in sources

    @pytest.mark.asyncio
    async def test_single_page_failure_skipped(
        self,
        tmp_pdf_empty: Path,
        tenant_id: uuid.UUID,
        mock_pixtral_response: MagicMock,
    ) -> None:
        call_count = 0

        async def _side_effect(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:  # First page: 3 retries then fail
                raise RuntimeError("API error")
            return mock_pixtral_response  # Second page succeeds

        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(side_effect=_side_effect)
            pages = await extract_with_vision(tmp_pdf_empty, "plan", tenant_id)

        # First page failed, second page succeeded
        assert len(pages) == 1
        assert pages[0].page == 2

    @pytest.mark.asyncio
    async def test_all_pages_fail_returns_empty(
        self,
        tmp_pdf_empty: Path,
        tenant_id: uuid.UUID,
    ) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(side_effect=RuntimeError("API error"))
            pages = await extract_with_vision(tmp_pdf_empty, "plan", tenant_id)

        assert pages == []

    @pytest.mark.asyncio
    async def test_exceeds_page_limit_returns_empty(
        self,
        tmp_pdf_many_pages: Path,
        tenant_id: uuid.UUID,
    ) -> None:
        pages = await extract_with_vision(tmp_pdf_many_pages, "plan", tenant_id)
        assert pages == []


class TestClassifyPageByVision:
    @pytest.mark.asyncio
    async def test_classifies_with_high_confidence(
        self,
        tmp_pdf_empty: Path,
        mock_pixtral_classification_response: MagicMock,
    ) -> None:
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(
                return_value=mock_pixtral_classification_response
            )
            result = await classify_page_by_vision(tmp_pdf_empty)

        assert result["type"] == "plan"
        assert result["lot"] == "01 - Gros oeuvre"
        assert result["phase"] == "PRO"

    @pytest.mark.asyncio
    async def test_low_confidence_returns_autre(
        self,
        tmp_pdf_empty: Path,
    ) -> None:
        from dataclasses import dataclass

        @dataclass
        class _Msg:
            content: str = '{"type": "plan", "lot": "", "phase": "", "confidence": 0.3}'

        @dataclass
        class _Choice:
            message: _Msg

        low_conf = MagicMock()
        low_conf.choices = [_Choice(message=_Msg())]

        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=low_conf)
            result = await classify_page_by_vision(tmp_pdf_empty)

        assert result["type"] == "autre"


class TestOcrSparsePages:
    """OCR fallback: pages are rendered in a worker thread, then OCR'd here."""

    @pytest.mark.asyncio
    async def test_pages_with_enough_text_are_untouched(
        self, tmp_pdf_with_text: Path
    ) -> None:
        pages = [
            ExtractedPage(text="C" * 500, page=1, source="page 1"),
            ExtractedPage(text="D" * 500, page=2, source="page 2"),
        ]

        with patch("app.services.ingestion.vision.mistral_client") as mock_client:
            mock_client.chat.complete_async = AsyncMock()
            result = await ocr_sparse_pages(tmp_pdf_with_text, pages)

        assert result == pages
        mock_client.chat.complete_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_sparse_page_is_replaced_by_its_ocr_text(
        self, tmp_pdf_with_text: Path, mock_pixtral_response: MagicMock
    ) -> None:
        pages = [
            ExtractedPage(text="E" * 500, page=1, source="page 1"),
            ExtractedPage(text="tiny", page=2, source="page 2"),  # sparse
            ExtractedPage(text="F" * 500, page=3, source="page 3"),
        ]

        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            result = await ocr_sparse_pages(tmp_pdf_with_text, pages)

        assert "Mocked vision description" in result[1].text
        assert result[1].source == "ocr page 2"
        assert result[0].text == pages[0].text  # untouched
        assert result[2].text == pages[2].text
        assert mock_client.chat.complete_async.await_count == 1

    @pytest.mark.asyncio
    async def test_fully_scanned_document_skips_ocr(
        self, tmp_pdf_with_text: Path
    ) -> None:
        """>80% sparse and almost no text: full vision extraction handles it later."""
        pages = [ExtractedPage(text="", page=i + 1, source=f"page {i + 1}") for i in range(3)]

        with patch("app.services.ingestion.vision.mistral_client") as mock_client:
            mock_client.chat.complete_async = AsyncMock()
            result = await ocr_sparse_pages(tmp_pdf_with_text, pages)

        assert result == pages
        mock_client.chat.complete_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_page_outside_the_pdf_is_skipped(
        self, tmp_pdf_with_text: Path, mock_pixtral_response: MagicMock
    ) -> None:
        """A page number the PDF does not have must not abort the other OCRs."""
        pages = [
            ExtractedPage(text="G" * 500, page=1, source="page 1"),
            ExtractedPage(text="tiny", page=2, source="page 2"),  # sparse, exists
            ExtractedPage(text="tiny", page=99, source="page 99"),  # sparse, missing
        ]

        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            result = await ocr_sparse_pages(tmp_pdf_with_text, pages)

        assert "Mocked vision description" in result[1].text
        assert result[2].text == "tiny"  # untouched, no crash
        assert mock_client.chat.complete_async.await_count == 1

    @pytest.mark.asyncio
    async def test_non_pdf_is_returned_as_is(self, tmp_path: Path) -> None:
        docx = tmp_path / "doc.docx"
        docx.write_bytes(b"PK\x03\x04")
        pages = [ExtractedPage(text="tiny", page=1, source="page 1")]

        assert await ocr_sparse_pages(docx, pages) == pages
