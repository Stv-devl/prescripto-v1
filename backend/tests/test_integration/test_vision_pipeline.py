"""Integration test for the full vision pipeline (plan document)."""

import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.ingestion.pipeline import run_ingestion


@pytest.fixture
def tmp_pdf_plan(tmp_path: Path) -> Path:
    """Create a 2-page PDF with no text (simulates an architectural plan)."""
    pdf_path = tmp_path / "plan_archi.pdf"
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def mock_document() -> Document:
    """A mock Document ORM instance."""
    doc = MagicMock(spec=Document)
    doc.id = uuid.uuid4()
    doc.project_id = uuid.uuid4()
    doc.filename = "plan_archi.pdf"
    doc.status = "processing"
    doc.type = ""
    doc.lot = ""
    doc.phase = ""
    return doc


@pytest.fixture
def mock_db() -> AsyncMock:
    """A mock async DB session."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


class TestVisionPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_plan_document(
        self,
        tmp_pdf_plan: Path,
        mock_document: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Plan document: classified by vision, kept in the GED, NOT indexed in RAG.

        The pipeline short-circuits on `type == "plan"` (pipeline.py, step 2b):
        the document is marked ready with zero chunks — no chunking, no
        embedding, no chunk rows.
        """
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # Mock classification response (vision fallback)
        @dataclass
        class _ClassMsg:
            content: str = (
                '{"type": "plan", "lot": "01 - Gros oeuvre", "phase": "PRO", "confidence": 0.95}'
            )

        @dataclass
        class _ClassChoice:
            message: _ClassMsg

        classification_response = MagicMock()
        classification_response.choices = [_ClassChoice(message=_ClassMsg())]

        # Mock vision description response
        @dataclass
        class _VisionMsg:
            content: str = (
                "## Plan RDC\n"
                "### Identification\n"
                "Type: Plan d'étage RDC\n"
                "Échelle: 1/100\n\n"
                "### Pièces\n"
                "- Séjour: 35m², 7.0m × 5.0m\n"
                "- Cuisine: 12m²\n"
            )

        @dataclass
        class _VisionChoice:
            message: _VisionMsg

        vision_response = MagicMock()
        vision_response.choices = [_VisionChoice(message=_VisionMsg())]

        # Mock embedding
        mock_point_ids = [uuid.uuid4(), uuid.uuid4()]

        with (
            patch("app.services.ingestion.vision.mistral_client") as mock_vision_client,
            patch("app.services.ingestion.classification.mistral_client") as mock_class_client,
            patch(
                "app.services.ingestion.embedding.index_chunks",
                new_callable=AsyncMock,
                return_value=mock_point_ids,
            ),
            patch("app.services.ingestion.vision.asyncio.sleep"),
        ):
            # Classification calls use Pixtral 12B, vision calls use Pixtral Large
            mock_vision_client.chat.complete_async = AsyncMock(
                side_effect=[
                    classification_response,  # classify_page_by_vision
                    vision_response,  # describe_plan_page (page 1)
                    vision_response,  # describe_plan_page (page 2)
                ]
            )
            mock_class_client.chat.complete_async = AsyncMock()

            await run_ingestion(mock_db, mock_document, tmp_pdf_plan, tenant_id)

        # Document should be classified as plan
        assert mock_document.type == "plan"
        assert mock_document.lot == "01 - Gros oeuvre"
        assert mock_document.phase == "PRO"
        assert mock_document.status == "ready"

        # Plans are not indexed: no chunk row, no chunk count
        assert mock_db.add.call_count == 0
        assert mock_document.chunk_count == 0
        assert mock_db.commit.call_count >= 1
