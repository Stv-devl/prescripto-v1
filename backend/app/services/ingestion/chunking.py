"""Intelligent document chunking based on document type."""

import logging
import re
from dataclasses import dataclass, field

from app.services.ingestion.extraction import ExtractedPage

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A chunk of text ready for embedding."""

    text: str
    page: int
    position: int
    parent_sections: list[str] = field(default_factory=list)
    section_title: str = ""
    heading_prefix: str = ""
    chunk_lot: str = ""
    content_type: str = "mixed"
    keywords: list[str] = field(default_factory=list)
    localisation: list[str] = field(default_factory=list)
    char_count: int = 0


CHUNK_SIZE = 2500
CHUNK_OVERLAP = 300
MIN_CHUNK_SIZE = 250

LOT_RE = re.compile(r"^\s*(?:LOT|Lot)\s*[Nn°]*\s*(\d+)\s*[-–:.]\s*(.+)", re.IGNORECASE)
ARTICLE_RE = re.compile(
    r"^\s*(?:Art(?:icle)?\.?\s+)?(\d+)[.\-](\d+)\s*[-–:.]\s*(.+)", re.IGNORECASE
)
SUBARTICLE_RE = re.compile(r"^\s*(\d+)[.\-](\d+)[.\-](\d+)\s*[-–:.)\s]\s*(.+)")

_TABLE_BLOCK_RE = re.compile(
    r"<!-- TABLE -->\n(.*?)\n<!-- /TABLE -->",
    re.DOTALL,
)

_QUANTITY_RE = re.compile(r"\b(?:m[²³23]|ml|kg|[Uu]|ens|forfait)\b")
_ADMIN_PHRASES = re.compile(
    r"(?:conformément à|le titulaire devra|selon les règles|"
    r"à la charge de|l'entrepreneur|prescriptions|obligation|"
    r"responsabilité|réglementation|normes en vigueur)",
    re.IGNORECASE,
)
_SPEC_RE = re.compile(
    r"(?:épaisseur|résistance|classe|type|dimension|section|diamètre|"
    r"capacité|performance|coefficient|conductivité|densité)\s*"
    r"(?::|=|de\s)?\s*\d",
    re.IGNORECASE,
)
_DESC_VERBS = re.compile(
    r"\b(?:comprend|comporte|constitué|composé|réalisé|mis en œuvre|posé|fixé|"
    r"scellé|coulé|appliqué|disposé)\b",
    re.IGNORECASE,
)

_MATERIAL_RE = re.compile(
    r"\b(?:béton|acier|bois|aluminium|PVC|zinc|cuivre|plomb|inox|verre|"
    r"laine de (?:verre|roche)|polystyrène|polyuréthane|plâtre|mortier|"
    r"ciment|gravier|sable|enrobé|bitume|ardoise|tuile|brique|parpaing|"
    r"agglo|BA13|fermacell|OSB)\b",
    re.IGNORECASE,
)
_NORM_RE = re.compile(
    r"\b(?:DTU\s+\d[\d\-.]*|NF\s*(?:EN\s*)?[A-Z]{0,2}\s*\d[\d\-.:]*|EN\s+\d[\d\-.]*)\b"
)
_GRADE_RE = re.compile(r"\bC\d{2}/\d{2}\b")
_RAL_RE = re.compile(r"\bRAL\s*\d{4}\b")
_PERF_RE = re.compile(r"\b(?:Ug|Uw|R|Up|Ucw)\s*=\s*[\d.,]+")
_BRAND_RE = re.compile(
    r"\b(?:Knauf|Isover|Weber|Sika|Schüco|Schuco|Saint-Gobain|Velux|Grohe|"
    r"Legrand|Schneider|Hager|Geberit|Rockwool|Placo|Siniat|Mapei|Parex|"
    r"Hilti|Fischer|Rehau|Daikin|Atlantic|Thermor|Viessmann|Bosch|"
    r"Giacomini|Caleffi|Grundfos|Wilo|ABB|Siemens)\b",
    re.IGNORECASE,
)
_OUVRAGE_RE = re.compile(
    r"\b(?:fondation|dalle|cloison|faux[- ]plafond|chape|étanchéité|"
    r"gouttière|VRD|menuiserie|serrurerie|couverture|bardage|"
    r"revêtement|carrelage|peinture|plomberie|ventilation|"
    r"chauffage|électricité|isolation|doublage|escalier|"
    r"garde[- ]corps|acrotère|seuil|appui|linteau|"
    r"enduit|ravalement|terrasse|balcon|plancher)\b",
    re.IGNORECASE,
)
_DIMENSION_RE = re.compile(
    r"\b\d+\s*[xX×]\s*\d+(?:\s*[xX×]\s*\d+)?\s*(?:mm|cm|m)\b|"
    r"(?:ép(?:aisseur)?\.?\s*[:=]?\s*\d+\s*(?:mm|cm|m))|"
    r"(?:[ØDd]\s*[:=]?\s*\d+\s*(?:mm|cm|m))|"
    r"(?:[LlHh]\s*[:=]\s*\d+[.,]?\d*\s*(?:mm|cm|m))",
    re.IGNORECASE,
)
_FIRE_RE = re.compile(
    r"\b(?:A[12](?:-s[12],d[012])?|M[0-4]|"
    r"(?:EI|REI|E|R)\s*\d{2,3}|"
    r"coupe[- ]feu|pare[- ]flamme|"
    r"incombustible|ignifug[ée])\b",
    re.IGNORECASE,
)
_CERTIFICATION_RE = re.compile(
    r"\b(?:ACERMI|CSTB|CSTBat|Avis\s+Technique|"
    r"marquage\s+CE|QB|HQE|BREEAM|LEED|"
    r"Qualibat|RGE|Effinergie)\b",
    re.IGNORECASE,
)

_AMIANTE_RE = re.compile(
    r"\b(?:amiante|chrysotile|crocidolite|amosite|trémolite|"
    r"actinolite|anthophyllite|"
    r"MPCA|MCA|fibro[- ]ciment|amiante[- ]ciment|"
    r"flocage|calorifugeage|déflocage|"
    r"prélèvement|échantillon|sondage|"
    r"sous[- ]section\s*[1-4]|SS[1-4])\b",
    re.IGNORECASE,
)
_DIAG_RESULT_RE = re.compile(
    r"\b(?:positif|négatif|présence|absence|"
    r"détecté|non\s+détecté|identifié|"
    r"amianté|non\s+amianté|"
    r"résultat|conclusion|diagnostic)\b",
    re.IGNORECASE,
)

_LOCALISATION_RE = re.compile(
    r"\b(?:RDC|rez[- ]de[- ]chauss[ée]e|"
    r"R\+\d|R-\d|"
    r"sous[- ]sol|SS[- ]?\d|"
    r"[ée]tage\s+\d+|niveau\s+\d+|"
    r"toiture|terrasse|façade|combles?|"
    r"sanitaires?|hall|circulations?|"
    r"parking|cave|local\s+technique|"
    r"chaufferie|buanderie|vide[- ]sanitaire|"
    r"palier|cage\s+d['\u2019]escalier)\b",
    re.IGNORECASE,
)


def _detect_heading_level(line: str) -> tuple[int, str] | None:
    """Detect if a line is a heading and return (level, heading_text).

    Tests from most specific to most general:
    - Level 2: sub-article (1.2.3 - Title)
    - Level 1: article (1.2 - Title)
    - Level 0: lot (LOT 03 - Title)
    """
    m = SUBARTICLE_RE.match(line)
    if m:
        return 2, line.strip()
    m = ARTICLE_RE.match(line)
    if m:
        return 1, line.strip()
    m = LOT_RE.match(line)
    if m:
        lot_num = m.group(1).zfill(2)
        lot_name = m.group(2).strip()
        return 0, f"LOT {lot_num} - {lot_name}"
    return None


def _update_heading_stack(stack: list[str], level: int, heading: str) -> list[str]:
    """Update heading stack: truncate to level and append new heading."""
    new_stack = stack[:level]
    new_stack.append(heading)
    return new_stack


def _classify_content_type(text: str) -> str:
    """Classify chunk content type based on signal frequency.

    Returns one of: heading, quantity, admin, specification, description, mixed.
    """
    if "<!-- TABLE -->" in text:
        return "table"

    is_heading_pattern = LOT_RE.match(text) or ARTICLE_RE.match(text) or SUBARTICLE_RE.match(text)
    if len(text) < 100 and is_heading_pattern:
        return "heading"

    signals = {
        "quantity": len(_QUANTITY_RE.findall(text)),
        "admin": len(_ADMIN_PHRASES.findall(text)),
        "specification": len(_SPEC_RE.findall(text)),
        "description": len(_DESC_VERBS.findall(text)),
    }

    total = sum(signals.values())
    if total == 0:
        return "mixed"

    sorted_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)
    top_type, top_count = sorted_signals[0]
    second_count = sorted_signals[1][1] if len(sorted_signals) > 1 else 0

    top_ratio = top_count / total
    if top_ratio > 0.6:
        return top_type
    if top_count > 0 and second_count > 0 and abs(top_count - second_count) / total < 0.2:
        return "mixed"
    return "mixed"


def _extract_keywords(text: str) -> list[str]:
    """Extract up to 10 technical keywords from text."""
    keywords: set[str] = set()

    for pattern in (
        _MATERIAL_RE,
        _NORM_RE,
        _GRADE_RE,
        _RAL_RE,
        _PERF_RE,
        _BRAND_RE,
        _OUVRAGE_RE,
        _DIMENSION_RE,
        _FIRE_RE,
        _CERTIFICATION_RE,
        _AMIANTE_RE,
        _DIAG_RESULT_RE,
    ):
        for match in pattern.finditer(text):
            keywords.add(match.group(0).strip().lower())

    return sorted(keywords)[:10]


def _extract_localisation(text: str) -> list[str]:
    """Extract building location references from text."""
    locations: set[str] = set()
    for match in _LOCALISATION_RE.finditer(text):
        locations.add(match.group(0).strip().lower())
    return sorted(locations)


def chunk_by_articles(pages: list[ExtractedPage]) -> list[TextChunk]:
    """Chunk a CCTP by article/sub-article patterns (e.g. 1.2.3, Article 2, LOT 03)."""
    full_text = "\n\n".join(p.text for p in pages)
    pattern = r"(?=(?:^|\n)(?:(?:Article|ARTICLE)\s+\d|(?:LOT|Lot)\s+\d|\d+\.\d+(?:\.\d+)?))"
    sections = re.split(pattern, full_text)
    sections = [s.strip() for s in sections if s.strip()]

    chunks: list[TextChunk] = []
    heading_stack: list[str] = []
    current_lot = ""

    for i, section in enumerate(sections):
        first_line = section.split("\n", 1)[0]
        heading_info = _detect_heading_level(first_line)

        if heading_info is not None:
            level, heading_text = heading_info
            heading_stack = _update_heading_stack(heading_stack, level, heading_text)
            if level == 0:
                m = LOT_RE.match(first_line)
                if m:
                    current_lot = f"{m.group(1).zfill(2)} - {m.group(2).strip()}"

        parent_sections = list(heading_stack)
        section_title = heading_stack[-1] if heading_stack else ""
        heading_prefix = " > ".join(heading_stack) if heading_stack else ""
        content_type = _classify_content_type(section)
        keywords = _extract_keywords(section)
        localisation = _extract_localisation(section)

        if len(section) <= CHUNK_SIZE:
            chunks.append(
                TextChunk(
                    text=section,
                    page=_find_page(pages, section),
                    position=i,
                    parent_sections=parent_sections,
                    section_title=section_title,
                    heading_prefix=heading_prefix,
                    chunk_lot=current_lot,
                    content_type=content_type,
                    keywords=keywords,
                    localisation=localisation,
                    char_count=len(section),
                )
            )
        else:
            sub_chunks = _split_preserving_tables(section)
            for j, sub in enumerate(sub_chunks):
                chunks.append(
                    TextChunk(
                        text=sub,
                        page=_find_page(pages, sub[:100]),
                        position=i + j,
                        parent_sections=parent_sections,
                        section_title=section_title,
                        heading_prefix=heading_prefix,
                        chunk_lot=current_lot,
                        content_type=_classify_content_type(sub),
                        keywords=_extract_keywords(sub),
                        localisation=_extract_localisation(sub),
                        char_count=len(sub),
                    )
                )

    return chunks if chunks else chunk_by_paragraphs(pages)


_CR_HEADING_RE = re.compile(r"^\s*\d+[\.\)]\s+(\S.{9,})")


def chunk_by_points(pages: list[ExtractedPage]) -> list[TextChunk]:
    """Chunk a CR (compte-rendu) by discussion points / numbered sections.

    Splits on numbered sections with actual content (not bare TOC numbers).
    Merges tiny fragments and propagates section titles.
    """
    full_text = "\n\n".join(p.text for p in pages)

    pattern = r"(?=(?:^|\n)(?:\d+[\.\)]\s+\S.{9,}|Point\s+\d))"
    sections = re.split(pattern, full_text)
    sections = [s.strip() for s in sections if s.strip()]

    sections = _merge_tiny_sections(sections, MIN_CHUNK_SIZE)

    chunks: list[TextChunk] = []
    current_section_title = ""

    for i, section in enumerate(sections):
        first_line = section.split("\n", 1)[0].strip()
        heading_match = _CR_HEADING_RE.match(first_line)
        if heading_match:
            current_section_title = first_line

        content_type = _classify_content_type(section)
        keywords = _extract_keywords(section)
        localisation = _extract_localisation(section)

        if len(section) <= CHUNK_SIZE:
            chunks.append(
                TextChunk(
                    text=section,
                    page=_find_page(pages, section),
                    position=i,
                    section_title=current_section_title,
                    content_type=content_type,
                    keywords=keywords,
                    localisation=localisation,
                    char_count=len(section),
                )
            )
        else:
            sub_chunks = _split_preserving_tables(section)
            for j, sub in enumerate(sub_chunks):
                chunks.append(
                    TextChunk(
                        text=sub,
                        page=_find_page(pages, sub[:100]),
                        position=i + j,
                        section_title=current_section_title,
                        content_type=_classify_content_type(sub),
                        keywords=_extract_keywords(sub),
                        localisation=_extract_localisation(sub),
                        char_count=len(sub),
                    )
                )

    return chunks if chunks else chunk_by_paragraphs(pages)


def _merge_tiny_sections(sections: list[str], min_size: int) -> list[str]:
    """Merge sections smaller than min_size with the following section."""
    if not sections:
        return sections

    merged: list[str] = []
    buffer = ""

    for section in sections:
        if buffer:
            section = buffer + "\n\n" + section
            buffer = ""

        if len(section) < min_size:
            buffer = section
        else:
            merged.append(section)

    if buffer:
        if merged:
            merged[-1] = merged[-1] + "\n\n" + buffer
        else:
            merged.append(buffer)

    return merged


def chunk_by_paragraphs(pages: list[ExtractedPage]) -> list[TextChunk]:
    """Fallback: chunk by paragraphs with overlap."""
    full_text = "\n\n".join(p.text for p in pages)
    if not full_text.strip():
        return []

    sub_chunks = _split_preserving_tables(full_text)
    return [
        TextChunk(
            text=text,
            page=_find_page(pages, text[:100]),
            position=i,
            content_type=_classify_content_type(text),
            keywords=_extract_keywords(text),
            localisation=_extract_localisation(text),
            char_count=len(text),
        )
        for i, text in enumerate(sub_chunks)
    ]


def chunk_plan_pages(pages: list[ExtractedPage]) -> list[TextChunk]:
    """One chunk per page for plans (each Pixtral description is a coherent unit)."""
    return [
        TextChunk(
            text=page.text,
            page=page.page,
            position=i,
            content_type=_classify_content_type(page.text),
            keywords=_extract_keywords(page.text),
            localisation=_extract_localisation(page.text),
            char_count=len(page.text),
        )
        for i, page in enumerate(pages)
        if page.text.strip()
    ]


def chunk_fiche_sections(pages: list[ExtractedPage]) -> list[TextChunk]:
    """Chunk technical data sheets by markdown ## headings from Pixtral output.

    Falls back to chunk_by_paragraphs if no headings are found.
    """
    full_text = "\n\n".join(p.text for p in pages)
    if not full_text.strip():
        return []

    sections = re.split(r"(?=^## )", full_text, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()]

    if len(sections) <= 1:
        return chunk_by_paragraphs(pages)

    chunks: list[TextChunk] = []
    for i, section in enumerate(sections):
        content_type = _classify_content_type(section)
        keywords = _extract_keywords(section)
        localisation = _extract_localisation(section)
        if len(section) <= CHUNK_SIZE:
            chunks.append(
                TextChunk(
                    text=section,
                    page=_find_page(pages, section),
                    position=i,
                    content_type=content_type,
                    keywords=keywords,
                    localisation=localisation,
                    char_count=len(section),
                )
            )
        else:
            sub_chunks = _split_preserving_tables(section)
            for j, sub in enumerate(sub_chunks):
                chunks.append(
                    TextChunk(
                        text=sub,
                        page=_find_page(pages, sub[:100]),
                        position=i + j,
                        content_type=_classify_content_type(sub),
                        keywords=_extract_keywords(sub),
                        localisation=_extract_localisation(sub),
                        char_count=len(sub),
                    )
                )

    return chunks if chunks else chunk_by_paragraphs(pages)


def _merge_tiny_chunks(chunks: list[TextChunk]) -> list[TextChunk]:
    """Post-process: merge chunks smaller than MIN_CHUNK_SIZE into their neighbor."""
    if not chunks:
        return chunks

    merged: list[TextChunk] = []
    for chunk in chunks:
        if chunk.char_count < MIN_CHUNK_SIZE and merged:
            prev = merged[-1]
            prev.text = prev.text + "\n\n" + chunk.text
            prev.char_count = len(prev.text)
            prev.keywords = list(set(prev.keywords + chunk.keywords))[:10]
            prev.localisation = list(set(prev.localisation + chunk.localisation))
            prev.content_type = _classify_content_type(prev.text)
        else:
            merged.append(chunk)

    return merged


# ── Diagnostic report support (amiante, sol, thermique) ────────────

_BOILERPLATE_RE = re.compile(
    r"(?:"
    r"recommandations?\s+(?:générales?\s+)?(?:de\s+)?sécurité|"
    r"ne\s+se\s+substitu(?:e|ent)\s+en\s+aucun\s+cas|"
    r"obligations?\s+réglementaires?\s+existant|"
    r"l['']émission\s+de\s+poussières?\s+peut\s+être\s+limitée|"
    r"déchets?\s+(?:amianté|lié|contenant)|"
    r"installation\s+de\s+stockage\s+pour\s+déchets\s+dangereux|"
    r"code\s+de\s+l['']environnement|"
    r"sclérose\s*\(?asbestose\)?|"
    r"insuffisance\s+respiratoire|"
    r"mésothéliome|"
    r"article\s+L[\s.]?\d{3,4}[- ]\d+\s+du\s+code|"
    r"diagnostiqueurs?\s+pour\s+la\s+gestion|"
    r"maintien\s+en\s+bon\s+état\s+de\s+conservation|"
    r"installation\s+de\s+stockage\s+pour\s+déchets|"
    r"déchet\s+amianté\s+doit\s+être\s+éliminé|"
    r"producteurs?\s+des?\s+déchets\s+au\s+sens|"
    r"filières?\s+(?:d[''])?élimination\s+(?:des?\s+)?déchets"
    r")",
    re.IGNORECASE,
)

_RESULT_TABLE_RE = re.compile(
    r"(?:"
    r"(?:résultat|amiante)\s*[:\s]*(?:positif|négatif)|"
    r"(?:positif|négatif)\s*[:\s]*(?:amiante|présence|absence)|"
    r"identifiant\s+(?:du\s+)?(?:matériau|prélèvement)|"
    r"conclusion\s*\(?justification\)?|"
    r"résultat\s+(?:d[''])?analyse|"
    r"composant.*résultat|"
    r"localisation.*(?:conclusion|résultat)|"
    r"n[°o]\s*(?:échantillon|prélèvement|rapport)|"
    r"(?:présence|absence)\s+d['']amiante"
    r")",
    re.IGNORECASE,
)

_CHECKLIST_TABLE_RE = re.compile(
    r"(?:"
    r"composant\s+de\s+la\s+construction.*(?:à\s+vérifier|à\s+sonder)|"
    r"partie\s+du\s+composant\s+(?:à\s+vérifier|ayant\s+été)"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def _is_checklist_table(text: str) -> bool:
    """Detect normative checklist tables from the NF X 46-020 inspection program.

    These tables list building components to inspect — they are identical
    across reports and have no diagnostic value for RAG.
    """
    if "<!-- TABLE -->" not in text:
        return False
    if _CHECKLIST_TABLE_RE.search(text):
        return True
    checklist_sections = re.findall(
        r"(?:toiture\s+et\s+étanchéité|"
        r"parois\s+verticales?\s+intérieures?|"
        r"plafonds?\s+et\s+faux[- ]plafonds?|"
        r"planchers?\s+et\s+marches|"
        r"equipements?\s+divers|"
        r"conduits?\s+(?:de\s+)?(?:vapeur|fumée|liquides)|"
        r"gaines?\s+et\s+coffres?\s+verticaux|"
        r"ascenseurs?\s+et\s+monte[- ]charge)",
        text,
        re.IGNORECASE,
    )
    has_result_cols = bool(
        re.search(
            r"(?:conclusion|résultat|positif|négatif|absence\s+d)",
            text,
            re.IGNORECASE,
        )
    )
    return len(checklist_sections) >= 1 and not has_result_cols


_CONTEXT_RE = re.compile(
    r"(?:"
    r"adresse\s+du\s+bâtiment|"
    r"opérateur.*certifi|"
    r"date.*(?:visite|commande|mission)|"
    r"numéro\s+de\s+dossier|"
    r"périmètre\s+de\s+repérage"
    r")",
    re.IGNORECASE,
)


def _infer_diagnostic_section(text: str) -> str:
    """Infer a section title for a diagnostic chunk based on semantic signals."""
    text_lower = text.lower()

    if _RESULT_TABLE_RE.search(text):
        if "analyse" in text_lower or "laboratoire" in text_lower:
            return "Résultats d'analyses"
        return "Conclusions / Résultats de repérage"

    if _is_checklist_table(text):
        return "Programme de repérage (normatif)"

    if _is_regulatory_text(text) or _BOILERPLATE_RE.search(text):
        if "recommandation" in text_lower:
            return "Recommandations générales"
        if "références réglementaires" in text_lower or "références normatives" in text_lower:
            return "Références réglementaires"
        return ""

    if _CONTEXT_RE.search(text):
        if "adresse" in text_lower:
            return "Identification du bâtiment"
        if "opérateur" in text_lower or "certifi" in text_lower:
            return "Opérateur de repérage"
        if "périmètre" in text_lower:
            return "Périmètre de repérage"
        return "Contexte de la mission"

    if "programme de repérage" in text_lower:
        return "Programme de repérage"

    return ""


def _is_regulatory_text(text: str) -> bool:
    """Detect regulatory / normative reference text (not specific to the building)."""
    text_lower = text.lower()
    signals = 0
    if "références réglementaires" in text_lower or "références normatives" in text_lower:
        signals += 2
    if re.search(r"article\s+[lr][\s.]?\d{3,4}", text_lower):
        signals += 1
    if re.search(r"(?:arrêté|décret|code\s+du\s+travail|code\s+de\s+la\s+santé)", text_lower):
        signals += 1
    if re.search(r"nf\s*x?\s*46[- ]0\d{2}", text_lower):
        signals += 1
    return signals >= 2


def _classify_diagnostic_content(text: str) -> str:
    """Classify diagnostic chunk: result, context, or admin (boilerplate).

    Priority: result tables > checklist tables > boilerplate > fallback.
    Result signals always win over boilerplate signals (a conclusion table
    that mentions regulatory text is still a result table).
    """
    is_result = _RESULT_TABLE_RE.search(text)

    if is_result:
        if "<!-- TABLE -->" in text:
            return "table"
        return "description"

    if _is_checklist_table(text):
        return "admin"

    if _is_regulatory_text(text):
        return "admin"

    boilerplate_hits = len(_BOILERPLATE_RE.findall(text))
    if boilerplate_hits >= 2:
        return "admin"

    base = _classify_content_type(text)
    if base in ("mixed", "admin") and boilerplate_hits >= 1 and len(text) > 500:
        return "admin"
    return base


def chunk_rapport_diagnostic(pages: list[ExtractedPage]) -> list[TextChunk]:
    """Chunk diagnostic reports (amiante, sol, thermique) with semantic enrichment.

    Uses paragraph-based splitting as base (report structure varies by lab),
    then post-processes each chunk to:
    - Infer section titles from content signals
    - Detect and tag boilerplate as admin
    - Reclassify result tables for higher search priority
    """
    chunks = chunk_by_paragraphs(pages)

    for chunk in chunks:
        if not chunk.section_title:
            chunk.section_title = _infer_diagnostic_section(chunk.text)

        chunk.content_type = _classify_diagnostic_content(chunk.text)

        chunk.keywords = _extract_keywords(chunk.text)
        chunk.localisation = _extract_localisation(chunk.text)

    return chunks


# ── Empty / useless chunk detection ──────────────────────────────

_EMPTY_TABLE_RE = re.compile(
    r"<!-- TABLE -->\s*\n"
    r"(?:\|[^\n]*\n){1,2}"
    r"(?:\|[\s\-–—|Nn/Aaéant]*\n)*"
    r"\s*<!-- /TABLE -->",
    re.IGNORECASE,
)

_EMPTY_TABLE_CELLS_RE = re.compile(
    r"^[\s|]*(?:néant|n[/.]?a|aucun|rien|sans\s+objet|\-|–|—|\s)*$",
    re.IGNORECASE | re.MULTILINE,
)


def _is_boilerplate_chunk(chunk: TextChunk) -> bool:
    """Detect generic safety/regulatory boilerplate with no project-specific value."""
    if chunk.content_type != "admin":
        return False
    hits = len(_BOILERPLATE_RE.findall(chunk.text))
    return hits >= 2


def _is_empty_chunk(chunk: TextChunk) -> bool:
    """Detect chunks with no useful content (empty tables, empty-value-only text, boilerplate)."""
    text = chunk.text.strip()

    if _is_boilerplate_chunk(chunk):
        return True

    if _EMPTY_TABLE_RE.fullmatch(text):
        return True

    if "<!-- TABLE -->" in text:
        lines = text.split("\n")
        table_rows = [line for line in lines if line.strip().startswith("|")]
        if len(table_rows) >= 2:
            data_rows = table_rows[2:]
            if data_rows and all(_EMPTY_TABLE_CELLS_RE.match(row) for row in data_rows):
                return True

    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned in ("néant", "n/a", "aucun", "sans objet", "-", "–", "—", "")


def _remove_empty_chunks(chunks: list[TextChunk]) -> list[TextChunk]:
    """Remove chunks with no useful content."""
    filtered = []
    removed = 0
    for chunk in chunks:
        if _is_empty_chunk(chunk):
            removed += 1
            continue
        filtered.append(chunk)
    if removed:
        logger.info("Removed %d empty/useless chunk(s) during ingestion", removed)
    return filtered


def chunk_document(pages: list[ExtractedPage], doc_type: str) -> list[TextChunk]:
    """Route to the appropriate chunking strategy based on document type."""
    if doc_type == "plan":
        chunks = chunk_plan_pages(pages)
    elif doc_type == "fiche_technique":
        chunks = chunk_fiche_sections(pages)
    elif doc_type in ("CCTP", "DPGF", "etude_thermique"):
        chunks = chunk_by_articles(pages)
    elif doc_type == "CR":
        chunks = chunk_by_points(pages)
    elif doc_type in ("rapport_amiante", "etude_sol"):
        chunks = chunk_rapport_diagnostic(pages)
    else:
        chunks = chunk_by_paragraphs(pages)

    chunks = _merge_tiny_chunks(chunks)
    return _remove_empty_chunks(chunks)


def _split_table_by_rows(table_md: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    """Split a large markdown table into sub-tables that fit within max_chars.

    Each sub-table repeats the header row and separator line.
    """
    lines = table_md.strip().split("\n")
    if len(lines) < 3:
        return [f"<!-- TABLE -->\n{table_md.strip()}\n<!-- /TABLE -->"]

    header = lines[0]
    separator = lines[1]
    data_lines = lines[2:]
    header_block = f"{header}\n{separator}"
    header_len = len(header_block) + len("<!-- TABLE -->\n") + len("\n<!-- /TABLE -->") + 2

    chunks: list[str] = []
    current_rows: list[str] = []
    current_len = header_len

    for row in data_lines:
        row_len = len(row) + 1
        if current_rows and current_len + row_len > max_chars:
            body = "\n".join(current_rows)
            chunks.append(f"<!-- TABLE -->\n{header_block}\n{body}\n<!-- /TABLE -->")
            current_rows = []
            current_len = header_len

        current_rows.append(row)
        current_len += row_len

    if current_rows:
        body = "\n".join(current_rows)
        chunks.append(f"<!-- TABLE -->\n{header_block}\n{body}\n<!-- /TABLE -->")

    return chunks


def _split_preserving_tables(text: str) -> list[str]:
    """Split text into chunks while preserving tables as atomic units.

    Tables smaller than CHUNK_SIZE become a single chunk.
    Tables larger than CHUNK_SIZE are split by row groups with repeated headers.
    Non-table text is split with the standard overlap strategy.
    """
    if "<!-- TABLE -->" not in text:
        return _split_with_overlap(text)

    parts = _TABLE_BLOCK_RE.split(text)

    chunks: list[str] = []

    for i, part in enumerate(parts):
        stripped = part.strip()
        if not stripped:
            continue

        if i % 2 == 0:
            if len(stripped) > CHUNK_SIZE:
                chunks.extend(_split_with_overlap(stripped))
            else:
                chunks.append(stripped)
        else:
            full_table = f"<!-- TABLE -->\n{stripped}\n<!-- /TABLE -->"
            if len(full_table) <= CHUNK_SIZE:
                chunks.append(full_table)
            else:
                chunks.extend(_split_table_by_rows(stripped, CHUNK_SIZE))

    return [c for c in chunks if c.strip()]


def _split_with_overlap(text: str) -> list[str]:
    """Split text into chunks of CHUNK_SIZE with CHUNK_OVERLAP overlap."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]

        if end < len(text):
            last_break = chunk.rfind("\n\n")
            if last_break == -1:
                last_break = chunk.rfind(". ")
            if last_break > CHUNK_SIZE // 2:
                end = start + last_break + 1
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end - CHUNK_OVERLAP

    return [c for c in chunks if c]


def _find_page(pages: list[ExtractedPage], text_snippet: str) -> int:
    """Find which page a text snippet belongs to."""
    snippet = text_snippet[:100]
    for page in pages:
        if snippet in page.text:
            return page.page
    return pages[0].page if pages else 1
