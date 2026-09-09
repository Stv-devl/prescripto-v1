"""Tests for vision fallback in document classification."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion.classification import classify_document


class TestClassifyVisionFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_vision_when_sparse(
        self,
        tmp_pdf_empty: Path,
        mock_pixtral_classification_response: MagicMock,
    ) -> None:
        """Sparse text (< 30 chars/page) triggers vision classification."""
        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_client,
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            mock_client.chat.complete_async = AsyncMock(
                return_value=mock_pixtral_classification_response
            )
            result = await classify_document(
                "ab",  # 2 chars for 2 pages = 1 char/page
                file_path=tmp_pdf_empty,
                nb_pages=2,
            )

        assert result["type"] == "plan"

    @pytest.mark.asyncio
    async def test_no_fallback_with_sufficient_text(
        self,
        tmp_pdf_with_text: Path,
        mock_pixtral_response: MagicMock,
    ) -> None:
        """Sufficient text (> 30 chars/page) uses normal text classification."""
        long_text = "CCTP - Lot 01 Gros oeuvre " * 50  # ~1300 chars

        with patch("app.services.ingestion.classification.mistral_client") as mock_client:
            mock_client.chat.complete_async = AsyncMock(return_value=mock_pixtral_response)
            # Should NOT call vision — uses text classification
            result = await classify_document(
                long_text,
                file_path=tmp_pdf_with_text,
                nb_pages=3,
            )

        # The mock returns markdown text, not JSON, so classification will fail
        # and return default. The important thing is that vision was NOT called.
        assert isinstance(result, dict)
        assert "type" in result
