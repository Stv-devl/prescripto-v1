"""Vision-based extraction for architectural plans and technical data sheets.

Converts PDF pages to images and sends them to Pixtral (Mistral Vision)
to generate textual descriptions indexable in Qdrant.
"""

import asyncio
import base64
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.config import settings
from app.core.mistral import mistral_client
from app.services.ingestion.extraction import ExtractedPage

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0

_SPARSE_PAGE_CHARS = 50
_VISION_THRESHOLD_CHARS = 200


@dataclass
class PageImage:
    """A rendered PDF page as base64 PNG."""

    page_number: int
    image_base64: str


_PLAN_PROMPT = """\
Tu es un architecte DPLG expert en lecture de plans de construction. \
Analyse ce plan et produis une description EXHAUSTIVE en markdown structuré.

Cette description sera la SEULE source d'information pour répondre à des \
questions futures — l'image ne sera plus disponible. Chaque détail compte.

## RÈGLES DE LECTURE IMPORTANTES

- Les cotes sur un plan sont TOUJOURS en centimètres (cm) sauf mention \
contraire. Un mur fait 20 cm d'épaisseur, PAS 200 cm. Une pièce fait \
500 cm (5 m), PAS 5000 cm.
- Un arc de cercle sur une porte = sens d'ouverture (l'arc montre le \
débattement du vantail).
- Une flèche dans un escalier indique le sens de montée (la flèche \
pointe vers le haut).
- Les traits épais = murs porteurs. Les traits fins = cloisons.
- Les hachures sur un mur = coupe ou matériau spécifique (béton, bois, \
isolation).

## Extrais TOUTES les informations visibles :

### 1. Identification
- Type de plan (étage, coupe, élévation, masse, etc.)
- Niveau/étage concerné (RDC, R+1, sous-sol, combles)
- Échelle indiquée (1/50, 1/100, etc.)
- Numéro de plan / indice de révision
- Cartouche : architecte, projet, date, phase, indice

### 2. Pièces et espaces
Pour CHAQUE pièce identifiable :
- Nom/désignation exacte (telle qu'écrite sur le plan)
- Surface (si indiquée, en m²)
- Cotes intérieures exactes (L × l en cm, telles que cotées)
- Usage/fonction
- Hauteur sous plafond (si coupe ou indiqué)

### 3. Relations spatiales
- Adjacences : quelle pièce touche quelle pièce, et par quel côté
- Circulations : couloirs, halls, dégagements, paliers
- Accès extérieurs : portes donnant sur l'extérieur, terrasse, jardin
- Orientation (Nord si indiqué, position de la flèche Nord)

### 4. Ouvertures — DÉTAILLER CHAQUE OUVERTURE
Pour CHAQUE porte :
- Type : porte simple, double, coulissante, galandage, pliante, \
porte-fenêtre, baie vitrée
- Largeur de passage (cote en cm si lisible)
- Sens d'ouverture : poussant gauche/droit (lire l'arc de cercle)
- Localisation : entre quelles pièces
Pour CHAQUE fenêtre / châssis :
- Type : ouvrant, fixe, oscillo-battant, coulissant, velux
- Dimensions (largeur × hauteur en cm si cotées)
- Allège (hauteur du bas de la fenêtre par rapport au sol)
- Façade concernée (Nord, Sud, Est, Ouest)

### 5. Escaliers — DÉTAILLER PRÉCISÉMENT
- Type : droit, quart tournant, deux quarts tournant, hélicoïdal
- Nombre de marches (compter sur le plan)
- Sens de montée (suivre la flèche : elle pointe vers le haut)
- Largeur de l'escalier (cote en cm)
- Palier intermédiaire (oui/non, dimensions)
- Position : entre quels niveaux, dans quelle pièce
- Trémie visible (oui/non)
- Ligne de foulée si visible

### 6. Éléments techniques
- Points d'eau : évier, lave-vaisselle, lave-linge, douche, \
baignoire, WC, lavabo (position exacte dans la pièce)
- Gaines techniques, colonnes, regards
- Tableau électrique, chaudière, ballon d'eau chaude, VMC
- Garde-corps, rampes, mains courantes
- Placards intégrés, dressings (dimensions si cotées)

### 7. Cotes et dimensions — LIRE AVEC PRÉCISION
- Reporter TOUTES les cotes lisibles avec leur valeur exacte en cm
- Cotes extérieures du bâtiment (emprise totale)
- Cotes intérieures de chaque pièce
- Épaisseurs de murs (porteurs vs cloisons)
- Cotes des trumeaux (entre ouvertures)
- Chaînes de cotes si présentes

### 8. Structure visible
- Murs porteurs (traits épais) vs cloisons (traits fins)
- Poteaux, poutres (symboles carrés/rectangles pleins)
- Joints de dilatation
- Type de plancher si annoté

### 9. Annotations et notes
- TOUTES les notes textuelles sur le plan
- Renvois vers d'autres plans (ex: "voir coupe AA")
- Niveaux altimétriques (NGF, niveaux finis)
- Pentes (terrasse, rampe d'accès)

Sois EXHAUSTIF et PRÉCIS sur les valeurs numériques. \
Relis chaque cote attentivement. Il vaut mieux trop de détails que pas assez."""

_FICHE_PROMPT = """\
Tu es un expert technique du BTP. Analyse cette page de fiche technique \
fabricant et extrais TOUTES les informations en markdown structuré.

Cette description sera la SEULE source d'information pour répondre à des \
questions futures — l'image ne sera plus disponible.

## Extrais :

### 1. Identification produit
- Nom du produit / gamme
- Référence(s) commerciale(s)
- Fabricant / marque
- Catégorie (menuiserie, isolation, revêtement, sanitaire, etc.)

### 2. Spécifications techniques
- TOUTES les dimensions (H, L, P, épaisseur)
- Poids
- Matériaux / composition
- Performances (thermiques, acoustiques, mécaniques, feu)
- Certifications et normes (CE, NF, Euroclass)
- Classes de performance (AEV pour menuiseries, etc.)

### 3. Schémas et dessins
Pour CHAQUE schéma :
- Type (coupe, vue éclatée, détail de pose)
- Ce qu'il représente
- Cotes indiquées
- Annotations

### 4. Tableaux
Reproduis INTÉGRALEMENT chaque tableau en markdown.

### 5. Instructions de pose
- Conditions de mise en œuvre
- Supports compatibles
- Fixations requises

### 6. Visuels produit
Décris chaque photo : couleur, finition, contexte.

N'invente RIEN — extrais uniquement ce qui est visible."""

_OCR_PROMPT = """\
Tu es un système OCR. Extrais TOUT le texte visible sur cette image de document.
Reproduis fidèlement le texte tel qu'il apparaît, en préservant :
- La structure des paragraphes
- Les listes numérotées ou à puces
- Les tableaux (en format markdown avec | séparateurs)
- Les titres et sous-titres
N'ajoute aucun commentaire ni interprétation. Retourne uniquement le texte extrait."""

_CLASSIFICATION_VISION_PROMPT = """\
Tu es un classificateur de documents du BTP et de la construction.

Analyse cette image et classifie le document parmi ces types :
- "plan" — Plan d'étage, coupe, élévation, plan masse, plan électrique, \
plomberie, CVC, structure. Caractéristiques : lignes techniques, cotes, \
échelle, cartouche, symboles normalisés.
- "fiche_technique" — Fiche technique produit fabricant, catalogue. \
Caractéristiques : photos/rendus de produit, tableaux de specs, schémas de \
montage, références commerciales.
- "CCTP" / "CR" / "estimatif" / "DPGF" / autre — Documents principalement \
textuels.

Réponds UNIQUEMENT avec un JSON :
{
  "type": "plan" | "fiche_technique" | "CCTP" | "CR" | "estimatif" | "DPGF" \
| "autre",
  "lot": "XX - Nom du lot" ou "" si non déterminable,
  "phase": "ESQ" | "APS" | "APD" | "PRO" | "DCE" | "EXE" | "" si non \
déterminable,
  "confidence": 0.0 à 1.0
}"""


def _render_pages_b64(
    file_path: Path,
    page_indices: list[int],
    dpi: int,
) -> dict[int, str]:
    """Render selected 0-indexed PDF pages to base64 PNG.

    Returns {page_index: base64}. Out-of-range indices and pages that fail to
    render are omitted rather than raising: one unreadable page must not lose the
    OCR of the others.

    Blocking and CPU-bound — always called through `asyncio.to_thread`.
    """
    images: dict[int, str] = {}
    doc = fitz.open(str(file_path))
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for index in page_indices:
            if index < 0 or index >= doc.page_count:
                continue
            try:
                pixmap = doc.load_page(index).get_pixmap(matrix=matrix)
                images[index] = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            except Exception:
                logger.exception("Failed to render page %d of %s", index + 1, file_path.name)
    finally:
        doc.close()
    return images


def pdf_pages_to_images(file_path: Path, dpi: int = 200) -> list[PageImage]:
    """Convert each PDF page to a base64 PNG image via PyMuPDF.

    Processes page by page to limit memory consumption.
    Raises ValueError if the PDF exceeds max_vision_pages.

    Blocking and CPU-bound: from async code, call it through `asyncio.to_thread`.
    Rendering a 50-page PDF inline freezes the whole event loop, every request
    included.
    """
    doc = fitz.open(str(file_path))
    page_count = doc.page_count
    logger.info("PDF → images: %s (%d pages, %d DPI)", file_path.name, page_count, dpi)

    if page_count > settings.max_vision_pages:
        doc.close()
        raise ValueError(
            f"PDF has {page_count} pages, exceeds limit of {settings.max_vision_pages}"
        )

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    images: list[PageImage] = []

    for i in range(page_count):
        page = doc.load_page(i)
        pixmap = page.get_pixmap(matrix=matrix)
        png_bytes = pixmap.tobytes("png")
        b64 = base64.b64encode(png_bytes).decode("ascii")
        images.append(PageImage(page_number=i + 1, image_base64=b64))
        logger.debug(
            "  Page %d/%d rendered (%d bytes PNG, %d chars base64)",
            i + 1,
            page_count,
            len(png_bytes),
            len(b64),
        )

    doc.close()
    logger.info("PDF → images complete: %d images generated", len(images))
    return images


async def _call_with_retry(
    coro_factory: Callable[[], Coroutine[object, object, str]],
) -> str:
    """Call an async function with exponential backoff retry.

    coro_factory must return a fresh coroutine on each call.
    """
    last_exc: BaseException | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            delay = _RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                "Vision API call failed (attempt %d/%d): %s. Retrying in %.1fs",
                attempt + 1,
                _RETRY_ATTEMPTS,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


def _build_vision_messages(image_base64: str, prompt: str) -> list[dict[str, object]]:
    """Build the messages payload for a Pixtral vision call."""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]


async def describe_plan_page(image_base64: str, page_number: int) -> ExtractedPage:
    """Send a plan page image to Pixtral Large and return a textual description."""

    async def _call() -> str:
        response = await mistral_client.chat.complete_async(
            model=settings.pixtral_large_model,
            messages=_build_vision_messages(image_base64, _PLAN_PROMPT),
            temperature=0.1,
        )
        content = response.choices[0].message.content  # type: ignore[union-attr]
        return content or ""

    logger.info("Pixtral Large → plan page %d (sending...)", page_number)
    text = await _call_with_retry(_call)
    logger.info("Pixtral Large → plan page %d: %d chars returned", page_number, len(text))
    logger.debug("Plan page %d preview: %.200s...", page_number, text.replace("\n", " "))
    return ExtractedPage(
        text=text,
        page=page_number,
        source=f"vision page {page_number}",
    )


async def describe_fiche_page(image_base64: str, page_number: int) -> ExtractedPage:
    """Send a technical data sheet page to Pixtral Large and return a description."""

    async def _call() -> str:
        response = await mistral_client.chat.complete_async(
            model=settings.pixtral_large_model,
            messages=_build_vision_messages(image_base64, _FICHE_PROMPT),
            temperature=0.1,
        )
        content = response.choices[0].message.content  # type: ignore[union-attr]
        return content or ""

    logger.info("Pixtral Large → fiche page %d (sending...)", page_number)
    text = await _call_with_retry(_call)
    logger.info("Pixtral Large → fiche page %d: %d chars returned", page_number, len(text))
    logger.debug("Fiche page %d preview: %.200s...", page_number, text.replace("\n", " "))
    return ExtractedPage(
        text=text,
        page=page_number,
        source=f"vision page {page_number}",
    )


async def classify_page_by_vision(file_path: Path) -> dict[str, str]:
    """Classify a document by sending its first page to Pixtral 12B.

    Returns dict with keys: type, lot, phase.
    Falls back to empty type if confidence < 0.6 or on error.
    """
    default: dict[str, str] = {"type": "", "lot": "", "phase": ""}
    logger.info("Vision classification starting for %s", file_path.name)
    try:
        images = await asyncio.to_thread(pdf_pages_to_images, file_path, settings.vision_dpi)
        if not images:
            logger.warning("No images generated for %s, returning default", file_path.name)
            return default

        first_page = images[0]
        logger.info("Pixtral 12B → classifying page 1 of %s (sending...)", file_path.name)

        async def _call() -> str:
            response = await mistral_client.chat.complete_async(
                model=settings.pixtral_small_model,
                messages=_build_vision_messages(
                    first_page.image_base64, _CLASSIFICATION_VISION_PROMPT
                ),
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content  # type: ignore[union-attr]
            return content or ""

        raw = await _call_with_retry(_call)
        logger.info("Pixtral 12B → raw response: %s", raw)
        result = json.loads(raw)

        confidence = float(result.get("confidence", 0.0))
        if confidence < 0.6:
            logger.info(
                "Vision classification confidence %.2f < 0.6, falling back to 'autre'",
                confidence,
            )
            return {"type": "autre", "lot": "", "phase": ""}

        classified = {
            "type": str(result.get("type", "")),
            "lot": str(result.get("lot", "")),
            "phase": str(result.get("phase", "")),
        }
        logger.info(
            "Vision classification result for %s: type=%s, lot=%s, phase=%s (confidence=%.2f)",
            file_path.name,
            classified["type"],
            classified["lot"],
            classified["phase"],
            confidence,
        )
        return classified
    except Exception:
        logger.exception("Vision classification failed for %s", file_path.name)
        return default


async def extract_with_vision(
    file_path: Path,
    doc_type: str,
    tenant_id: uuid.UUID,
    text_pages: list[ExtractedPage] | None = None,
) -> list[ExtractedPage]:
    """Orchestrate vision extraction for a document.

    Plans: full vision (all pages sent to Pixtral).
    Fiches techniques: hybrid per page (<50 chars → skip, 50-200 → Pixtral,
    >200 → keep PyMuPDF text).

    Returns empty list if all pages fail.
    """
    dpi = settings.vision_plan_dpi if doc_type == "plan" else settings.vision_dpi

    try:
        images = await asyncio.to_thread(pdf_pages_to_images, file_path, dpi)
    except ValueError:
        logger.exception("Cannot convert PDF to images: %s", file_path.name)
        return []

    if not images:
        return []

    text_by_page: dict[int, ExtractedPage] = {}
    if text_pages:
        for tp in text_pages:
            text_by_page[tp.page] = tp

    pages: list[ExtractedPage] = []
    logger.info(
        "Starting vision extraction for %s (%s, %d pages)",
        file_path.name,
        doc_type,
        len(images),
    )

    for img in images:
        try:
            if doc_type == "plan":
                page = await describe_plan_page(img.image_base64, img.page_number)
                if page.text.strip():
                    pages.append(page)
                else:
                    logger.warning(
                        "Plan page %d returned empty description, skipping",
                        img.page_number,
                    )

            elif doc_type == "fiche_technique":
                existing = text_by_page.get(img.page_number)
                char_count = len(existing.text.strip()) if existing else 0

                if char_count < _SPARSE_PAGE_CHARS:
                    logger.info(
                        "Fiche page %d: SKIP (%d chars < %d, too sparse)",
                        img.page_number,
                        char_count,
                        _SPARSE_PAGE_CHARS,
                    )
                    continue
                elif char_count <= _VISION_THRESHOLD_CHARS:
                    logger.info(
                        "Fiche page %d: VISION (%d chars, between %d-%d)",
                        img.page_number,
                        char_count,
                        _SPARSE_PAGE_CHARS,
                        _VISION_THRESHOLD_CHARS,
                    )
                    page = await describe_fiche_page(img.image_base64, img.page_number)
                    if page.text.strip():
                        pages.append(page)
                else:
                    logger.info(
                        "Fiche page %d: KEEP TEXT (%d chars > %d)",
                        img.page_number,
                        char_count,
                        _VISION_THRESHOLD_CHARS,
                    )
                    pages.append(existing)  # type: ignore[arg-type]

        except Exception:
            logger.exception(
                "Vision extraction failed for page %d of %s",
                img.page_number,
                file_path.name,
            )

    logger.info(
        "Vision extraction complete for %s: %d/%d pages extracted",
        file_path.name,
        len(pages),
        len(images),
    )
    return pages


async def ocr_sparse_pages(
    file_path: Path,
    pages: list[ExtractedPage],
    threshold_chars: int = _SPARSE_PAGE_CHARS,
) -> list[ExtractedPage]:
    """OCR fallback for scanned PDF pages with sparse extractable text.

    Identifies pages with fewer than threshold_chars of text, renders them
    as images, and sends them to Pixtral Large for OCR extraction.
    Pages with adequate text are returned unchanged.

    Skips OCR if the document appears to be fully image-based (>80% sparse
    pages with <10 avg chars), since those will likely go through full vision
    extraction after classification.
    """
    if file_path.suffix.lower() != ".pdf":
        return pages

    if not pages:
        return pages

    sparse_indices = [i for i, p in enumerate(pages) if len(p.text.strip()) < threshold_chars]

    if not sparse_indices:
        return pages

    sparse_ratio = len(sparse_indices) / len(pages)
    avg_chars = sum(len(p.text.strip()) for p in pages) / len(pages)
    if sparse_ratio > 0.8 and avg_chars < 10:
        logger.info(
            "OCR skip for %s: %.0f%% sparse pages, avg %.0f chars/page "
            "(likely full-image document, will use vision extraction)",
            file_path.name,
            sparse_ratio * 100,
            avg_chars,
        )
        return pages

    logger.info(
        "OCR fallback for %s: %d/%d pages are sparse (<%d chars)",
        file_path.name,
        len(sparse_indices),
        len(pages),
        threshold_chars,
    )

    result = list(pages)

    rendered = await asyncio.to_thread(
        _render_pages_b64,
        file_path,
        [result[idx].page - 1 for idx in sparse_indices],
        settings.vision_dpi,
    )

    for idx in sparse_indices:
        page_obj = result[idx]
        image_b64 = rendered.get(page_obj.page - 1)
        if image_b64 is None:
            continue

        try:

            async def _call(img: str = image_b64) -> str:
                response = await mistral_client.chat.complete_async(
                    model=settings.pixtral_large_model,
                    messages=_build_vision_messages(img, _OCR_PROMPT),
                    temperature=0.1,
                )
                content = response.choices[0].message.content  # type: ignore[union-attr]
                return content or ""

            ocr_text = await _call_with_retry(_call)

            if ocr_text.strip():
                logger.info(
                    "OCR page %d: %d chars extracted (was %d)",
                    page_obj.page,
                    len(ocr_text),
                    len(page_obj.text.strip()),
                )
                result[idx] = ExtractedPage(
                    text=ocr_text.strip(),
                    page=page_obj.page,
                    source=f"ocr page {page_obj.page}",
                    has_tables=page_obj.has_tables,
                )
            else:
                logger.warning("OCR page %d returned empty text", page_obj.page)

        except Exception:
            logger.exception("OCR failed for page %d of %s", page_obj.page, file_path.name)

    return result
