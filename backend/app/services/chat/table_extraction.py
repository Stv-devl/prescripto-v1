"""Structured table extraction from document context via Mistral."""

import json
import logging
import re
import unicodedata

from app.core.mistral import mistral_client
from app.schemas.chat import StructuredTable
from app.services.chat.prompts import TABLE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

TABLE_CONTEXT_LIMIT = 12000

_HAS_QUANTITY_RE = re.compile(r"\d+[.,]?\d*\s*(?:m[²³23]?|ml|kg|u|l)\b", re.IGNORECASE)


def _reorder_context_for_table(context_block: str) -> str:
    """Reorder context chunks: DPGF with quantities first, then other DPGF, then CCTP.

    The table LLM needs quantities above all. The raw context is ordered
    by semantic score, which often puts CCTP description chunks first
    and DPGF quantity chunks last — beyond the truncation limit.
    """
    chunks = context_block.split("\n---\n")
    dpgf_with_qty: list[str] = []
    dpgf_headings: list[str] = []
    other_chunks: list[str] = []

    for chunk in chunks:
        first_line = chunk.lstrip()[:120].upper()
        is_dpgf = "DPGF" in first_line or "DPFG" in first_line
        if is_dpgf:
            if _HAS_QUANTITY_RE.search(chunk):
                dpgf_with_qty.append(chunk)
            else:
                dpgf_headings.append(chunk)
        else:
            other_chunks.append(chunk)

    if dpgf_with_qty or dpgf_headings:
        logger.debug(
            f"[TABLE DEBUG] Context reordered: {len(dpgf_with_qty)} DPGF+qty, "
            f"{len(dpgf_headings)} DPGF headings, {len(other_chunks)} other"
        )

    return "\n---\n".join(dpgf_with_qty + dpgf_headings + other_chunks)


def _normalize_key(text: str) -> str:
    """Normalize text for dedup comparison: lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def _merge_duplicate_rows(
    rows: list[dict[str, str]],
    columns: list[str],
) -> list[dict[str, str]]:
    """Merge rows that have the same element and description but different locations.

    E.g. two rows for the same element with different locations are merged
    into one row with combined quantity and concatenated location text.
    """
    if len(rows) <= 1 or len(columns) < 2:
        return rows

    col_keys = [c.lower().replace("é", "e").replace(" ", "_") for c in columns]
    element_key = col_keys[0] if col_keys else ""
    desc_key = col_keys[1] if len(col_keys) > 1 else ""
    qty_key = ""
    loc_key = ""
    for ck in col_keys:
        if "quantite" in ck:
            qty_key = ck
        if "localisation" in ck:
            loc_key = ck

    if not element_key:
        return rows

    merged: list[dict[str, str]] = []
    seen: dict[str, int] = {}

    for row in rows:
        elem_val = row.get(element_key, "")
        norm_elem = _normalize_key(elem_val)

        if norm_elem in seen:
            idx = seen[norm_elem]
            existing = merged[idx]
            if qty_key:
                old_qty = existing.get(qty_key, "")
                new_qty = row.get(qty_key, "")
                if old_qty and new_qty and old_qty != new_qty:
                    existing[qty_key] = f"{old_qty} + {new_qty}"
            if loc_key:
                old_loc = existing.get(loc_key, "")
                new_loc = row.get(loc_key, "")
                if old_loc and new_loc and _normalize_key(new_loc) not in _normalize_key(old_loc):
                    existing[loc_key] = f"{old_loc}, {new_loc}"
            if desc_key:
                old_desc = existing.get(desc_key, "")
                new_desc = row.get(desc_key, "")
                if len(new_desc) > len(old_desc):
                    existing[desc_key] = new_desc
            logger.debug(
                f"[TABLE DEBUG] Merged duplicate row: '{elem_val}' "
                f"→ qty='{existing.get(qty_key, '')}', loc='{existing.get(loc_key, '')}'"
            )
        else:
            seen[norm_elem] = len(merged)
            merged.append(dict(row))

    return merged


async def extract_table(
    context_block: str,
    question: str,
) -> StructuredTable | None:
    """Extract a structured table from context via Mistral Large."""
    try:
        reordered = _reorder_context_for_table(context_block)
        truncated_context = reordered[:TABLE_CONTEXT_LIMIT]

        context_lines = truncated_context.split("\n")
        logger.debug(
            f"[TABLE DEBUG] Context sent to LLM: {len(truncated_context)} chars, "
            f"{len(context_lines)} lines (truncated={len(reordered) > TABLE_CONTEXT_LIMIT})"
        )
        for i, line in enumerate(context_lines):
            if line.startswith("[") and ", p." in line:
                logger.debug(f"[TABLE DEBUG]   chunk {i}: {line[:120]}")

        response = await mistral_client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": TABLE_EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Contexte :\n\n{truncated_context}\n\n---\n\nQuestion : {question}"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content  # type: ignore[union-attr]
        logger.debug(f"[TABLE DEBUG] Raw LLM response: {raw[:500] if raw else 'None'}")
        if not raw:
            return None

        data = json.loads(raw.strip())

        if data.get("skip"):
            logger.debug("[CHAT DEBUG] Table skipped by LLM (no quantities)")
            return None

        columns: list[str] = data.get("columns", [])
        raw_rows: list[dict[str, str]] = data.get("rows", [])[:8]

        if not columns or not raw_rows:
            return None

        rows: list[dict[str, str]] = []
        qty_key = ""
        for col in columns:
            if col.lower().replace("é", "e") in ("quantite", "quantité"):
                qty_key = col.lower().replace("é", "e")
                break

        no_qty_re = re.compile(
            r"^(—|-|non\s+chiffr[ée]e?|non\s+quantifi[ée]e?"
            r"|non\s+pr[ée]cis[ée]e?|non\s+mentionn[ée]e?"
            r"|n/?a|inconnue?|sans|aucune?|)$",
            re.IGNORECASE,
        )

        for r in raw_rows:
            if isinstance(r, dict):
                row = {k: str(v) for k, v in r.items()}
                if qty_key and no_qty_re.match(row.get(qty_key, "").strip()):
                    element = row.get("element", row.get(list(row.keys())[0], "?"))
                    logger.debug(
                        f"[TABLE DEBUG] Row filtered (no qty): '{element}' — qty='{row.get(qty_key, '')}'"
                    )
                    continue
                rows.append(row)

        if not rows:
            return None

        rows = _merge_duplicate_rows(rows, columns)

        total_cells = len(rows) * len(columns)
        filled = sum(1 for r in rows for v in r.values() if v and v.strip() and v.strip() != "—")
        fill_ratio = filled / total_cells if total_cells > 0 else 0
        if filled < 3 or fill_ratio < 0.4:
            logger.debug(
                f"[CHAT DEBUG] Table rejected (sparse): "
                f"filled={filled}/{total_cells} ({fill_ratio:.0%})"
            )
            return None

        table = StructuredTable(title=data.get("title", ""), columns=columns, rows=rows)
        logger.debug(
            f"[CHAT DEBUG] Extracted table: {table.title} ({len(table.rows)} rows, {filled}/{total_cells} filled)"
        )
        return table
    except Exception:
        logger.exception("Table extraction failed")
        return None
