"""The single place a Qdrant chunk payload is built.

Two paths reach it — the ingestion pipeline and the admin chunk mutations —
and used to build this dict independently, drifting apart on keys and fields.

Rationale: docs/work/qdrant-payload-unifie/plan.md.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.models.chunk import Chunk

_DIAGNOSTIC_TYPES = frozenset({"rapport_amiante", "etude_sol"})

_NORM_KEYWORD_RE = re.compile(r"^(?:dtu|nf|en)\s", re.IGNORECASE)

_THERMIQUE_KEYWORD_RE = re.compile(
    r"(?:"
    r"^(?:dtu|nf|en)\s|"
    r"^(?:ug|uw|r|up|ucw)\s*=|"
    r"^(?:acermi|cstb|cstbat|avis technique|"
    r"marquage ce|effinergie|hqe|rge|qualibat)|"
    r"^(?:isolation|chauffage|ventilation|doublage|"
    r"étanchéité|plancher|dalle|chape|"
    r"faux[- ]plafond|couverture|cloison)|"
    r"^(?:laine de verre|laine de roche|"
    r"polystyrène|polyuréthane)|"
    r"^(?:a[12](?:-s|$)|m[0-4]$|"
    r"(?:ei|rei|e|r)\s*\d)|"
    r"^c\d{2}/\d{2}$"
    r")",
    re.IGNORECASE,
)


def _filter_diagnostic_keywords(keywords: list[str]) -> list[str]:
    """Diagnostic reports carry findings, not prescriptions: keep only norms."""
    return [k for k in keywords if _NORM_KEYWORD_RE.match(k)]


def _filter_thermique_keywords(keywords: list[str]) -> list[str]:
    """Thermal studies: keep the norms and the thermal vocabulary."""
    return [k for k in keywords if _THERMIQUE_KEYWORD_RE.match(k)]


def _keywords_for(doc_type: str, keywords: list[str]) -> list[str]:
    """Apply the filter this document type calls for, if any."""
    if doc_type in _DIAGNOSTIC_TYPES:
        return _filter_diagnostic_keywords(keywords)
    if doc_type == "etude_thermique":
        return _filter_thermique_keywords(keywords)
    return keywords


@dataclass(frozen=True)
class ChunkPayloadFields:
    """What a payload reads off a chunk, whatever produced it.

    A dataclass and not a Protocol: Protocol members are invariant, `TextChunk`
    declares seven of these non-optional, and no type checker runs on this
    backend to catch the mismatch.
    """

    text: str
    page: int
    position: int
    parent_sections: list[str]
    section_title: str
    heading_prefix: str
    content_type: str
    keywords: list[str]
    localisation: list[str]
    char_count: int
    lot: str

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> "ChunkPayloadFields":
        """Adapt an ORM row, normalising its nullable columns.

        The one and only normalisation point. The ingestion pipeline writes most
        of these columns as `x or None`, so they are commonly NULL; a `None`
        reaching the payload raises at query time on `SearchResult.keywords`.
        """
        return cls(
            text=chunk.text,
            page=chunk.page,
            position=chunk.position,
            parent_sections=chunk.parent_sections or [],
            section_title=chunk.section_title or "",
            heading_prefix=chunk.heading_prefix or "",
            content_type=chunk.content_type or "",
            keywords=chunk.keywords or [],
            localisation=chunk.localisation or [],
            char_count=chunk.char_count or 0,
            lot=chunk.lot or "",
        )


def build_chunk_payload(
    fields: ChunkPayloadFields,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
    filename: str,
    phase: str,
    document_lot: str,
    ingested_at: datetime | None,
) -> dict[str, object]:
    """Build the Qdrant payload for one chunk.

    `tenant_id` is the isolation key every Qdrant query filters on, and nothing
    else enforces it — a wrong value here is a cross-tenant leak written into
    the index.
    """
    payload: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "document_id": str(document_id),
        "type": doc_type,
        "lot": fields.lot or document_lot,
        "phase": phase,
        "filename": filename,
        "page": fields.page,
        "position": fields.position,
        "text": fields.text,
        "heading_prefix": fields.heading_prefix,
        "section_title": fields.section_title,
        "parent_sections": fields.parent_sections,
        "content_type": fields.content_type,
        "keywords": _keywords_for(doc_type, fields.keywords),
        "char_count": fields.char_count,
        "localisation": fields.localisation,
    }
    if ingested_at is not None:
        payload["ingested_at"] = ingested_at.isoformat()
    return payload
