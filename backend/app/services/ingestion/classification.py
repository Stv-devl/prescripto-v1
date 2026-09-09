"""Document classification using Mistral AI — detect type, lot, and phase."""

import json
import logging
from pathlib import Path

from app.core.mistral import mistral_client

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """\
Tu es un assistant specialise dans les documents de construction (BTP).
Analyse l'extrait suivant et retourne un JSON avec exactement ces 3 champs:
- "type": le type de document parmi: CCTP, CR, fiche_technique, plan, email, estimatif, DPGF, etude_sol, etude_thermique, rapport_amiante, autre
- "lot": le lot principal concerne (ex: "01 - Gros oeuvre", "06 - Menuiseries exterieures", "" si non applicable)
- "phase": la phase du projet (ex: "ESQ", "APS", "APD", "PRO", "DCE", "EXE", "" si non determinable)

Reponds UNIQUEMENT avec le JSON, sans commentaire ni markdown.

Extrait du document:
---
{text}
---
"""

MAX_CLASSIFICATION_CHARS = 3000
_VISION_FALLBACK_CHARS_PER_PAGE = 30

TYPE_CCTP = "CCTP"
TYPE_DPGF = "DPGF"

VALID_TYPES = frozenset(
    {
        TYPE_CCTP,
        "CR",
        "fiche_technique",
        "plan",
        "email",
        "estimatif",
        TYPE_DPGF,
        "etude_sol",
        "etude_thermique",
        "rapport_amiante",
        "rapport_diagnostic",
        "autre",
    }
)
VALID_PHASES = frozenset({"ESQ", "APS", "APD", "PRO", "DCE", "EXE", ""})


def _validate_classification(result: dict[str, str]) -> dict[str, str]:
    """Validate and sanitize classification output against known enum values."""
    doc_type = result.get("type", "")
    phase = result.get("phase", "")
    lot = result.get("lot", "")

    if doc_type and doc_type not in VALID_TYPES:
        logger.warning(
            "Unknown document type '%s' from classification, falling back to 'autre'",
            doc_type,
        )
        doc_type = "autre"

    if phase and phase not in VALID_PHASES:
        logger.warning(
            "Unknown phase '%s' from classification, clearing",
            phase,
        )
        phase = ""

    return {"type": doc_type, "lot": lot, "phase": phase}


async def classify_document(
    full_text: str,
    file_path: Path | None = None,
    nb_pages: int = 1,
) -> dict[str, str]:
    """Classify a document by sending its beginning to Mistral.

    Falls back to vision classification (Pixtral 12B) when the text is too
    sparse (chars per page < 30), which usually indicates a scanned plan.

    Returns dict with keys: type, lot, phase.
    Falls back to empty strings on error.
    """
    default: dict[str, str] = {"type": "", "lot": "", "phase": ""}

    chars_per_page = len(full_text.strip()) / max(nb_pages, 1)
    if (
        chars_per_page < _VISION_FALLBACK_CHARS_PER_PAGE
        and file_path is not None
        and file_path.suffix.lower() == ".pdf"
    ):
        logger.info(
            "Text too sparse (%.1f chars/page < %d), falling back to vision classification",
            chars_per_page,
            _VISION_FALLBACK_CHARS_PER_PAGE,
        )
        from app.services.ingestion.vision import classify_page_by_vision

        return await classify_page_by_vision(file_path)

    excerpt = full_text[:MAX_CLASSIFICATION_CHARS]

    if not excerpt.strip():
        return default

    try:
        response = await mistral_client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "user", "content": CLASSIFICATION_PROMPT.format(text=excerpt)},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content  # type: ignore[union-attr]
        if content is None:
            return default

        result = json.loads(content)
        raw = {
            "type": str(result.get("type", "")),
            "lot": str(result.get("lot", "")),
            "phase": str(result.get("phase", "")),
        }
        return _validate_classification(raw)
    except Exception:
        logger.exception("Classification failed for %s", file_path.name if file_path else "unknown")
        return default
