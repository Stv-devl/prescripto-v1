"""DB metadata context enrichment for broad queries."""

import logging
import re
import uuid

from sqlalchemy import String as SAString
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.qdrant import qdrant_client
from app.models.document import Document
from app.models.project import Project
from app.services.ingestion.classification import TYPE_CCTP, TYPE_DPGF

logger = logging.getLogger(__name__)

_LOT_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:LOT|Lot)\s+[Nn°]*\s*(\d+)\s*[-–:.]?\s*(.+?)(?:\n|$)",
)

_FILENAME_LOT_RE = re.compile(
    r"^(\d{1,2})\s*[-_]\s*(.+?)[-_]\s*(?:DPGF|DPFG|CCTP)",
    re.IGNORECASE,
)


async def build_db_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> str:
    """Build structured context from DB metadata and CCTP content for broad queries.

    Returns a text block listing all distinct lots (from document metadata
    AND extracted from CCTP chunk headings) and document types, so the LLM
    can answer enumeration questions that semantic search alone cannot cover.
    """
    parts: list[str] = []

    lot_query = (
        select(Document.lot, Document.filename)
        .join(Project, Document.project_id == Project.id)
        .where(
            Project.tenant_id == tenant_id,
            Document.project_id == project_id,
            cast(Document.lot, SAString) != "",
        )
        .order_by(Document.lot)
    )
    result = await db.execute(lot_query)
    rows = result.all()

    lots_map: dict[str, list[str]] = {}
    if rows:
        for lot, filename in rows:
            lots_map.setdefault(lot, []).append(filename)

    cctp_lots = await _extract_lots_from_cctp(tenant_id, project_id)

    if cctp_lots:
        cctp_lot_nums = {label.split(" - ")[0].strip() for label in cctp_lots}

        for db_lot, fnames in lots_map.items():
            db_num_match = re.match(r"(\d{1,2})", db_lot)
            if db_num_match and db_num_match.group(1).zfill(2) in cctp_lot_nums:
                continue
            cctp_lots.setdefault(db_lot, fnames)

        final_lots = cctp_lots
    else:
        final_lots = lots_map

    if final_lots:
        sorted_lots = sorted(final_lots.items(), key=lambda x: x[0])
        lines = [
            f"- {lot} (documents : {', '.join(fnames)})" if fnames else f"- {lot}"
            for lot, fnames in sorted_lots
        ]
        parts.append(
            "MÉTADONNÉES DU PROJET — Liste officielle des lots "
            "(intitulés exacts des documents, à recopier tels quels) :\n" + "\n".join(lines)
        )

    type_query = (
        select(Document.type, func.count())
        .join(Project, Document.project_id == Project.id)
        .where(
            Project.tenant_id == tenant_id,
            Document.project_id == project_id,
            cast(Document.type, SAString) != "",
        )
        .group_by(Document.type)
        .order_by(Document.type)
    )
    result = await db.execute(type_query)
    type_rows = result.all()

    if type_rows:
        type_lines = [f"- {doc_type} ({count} document(s))" for doc_type, count in type_rows]
        parts.append("MÉTADONNÉES DU PROJET — Types de documents :\n" + "\n".join(type_lines))

    return "\n\n".join(parts)


async def _extract_lots_from_cctp(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> dict[str, list[str]]:
    """Scroll CCTP and DPGF chunks in Qdrant and extract lot headings.

    Also extracts lot numbers from document filenames (e.g. '04-MENUISERIE...-DPGF').
    Returns a dict mapping lot labels to a list of source filenames.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from app.services.ingestion.embedding import COLLECTION_NAME

    lots: dict[str, list[str]] = {}
    for doc_type in (TYPE_CCTP, TYPE_DPGF):
        all_records = []
        next_offset = None
        try:
            while True:
                records, next_offset = await qdrant_client.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                            FieldCondition(
                                key="project_id", match=MatchValue(value=str(project_id))
                            ),
                            FieldCondition(key="type", match=MatchValue(value=doc_type)),
                        ]
                    ),
                    limit=100,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                all_records.extend(records)
                if next_offset is None:
                    break
        except Exception:
            logger.exception("Failed to scroll %s chunks from Qdrant", doc_type)
            continue

        seen_filenames: set[str] = set()
        for record in all_records:
            payload = record.payload or {}
            text = payload.get("text", "")
            filename = payload.get("filename", "")

            for match in _LOT_HEADING_RE.finditer(text):
                lot_num = match.group(1).strip().zfill(2)
                lot_name = match.group(2).strip().rstrip(".")
                label = f"{lot_num} - {lot_name}"
                if label not in lots:
                    lots[label] = [filename]

            if filename and filename not in seen_filenames:
                seen_filenames.add(filename)
                fm = _FILENAME_LOT_RE.match(filename)
                if fm:
                    lot_num = fm.group(1).zfill(2)
                    lot_name = fm.group(2).replace("_", " ").strip()
                    label = f"{lot_num} - {lot_name}"
                    if label not in lots:
                        lots[label] = [filename]

    return lots
