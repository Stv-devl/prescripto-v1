"""Structured schema extraction and enrichment from document context."""

import json
import logging
import re
import uuid

from app.core.mistral import mistral_client
from app.schemas.chat import StructuredSchema
from app.schemas.search import SearchFilters
from app.services import search as search_service
from app.services.chat.prompts import (
    SCHEMA_EXTRACTION_PROMPT,
    SCHEMA_TYPES,
)

logger = logging.getLogger(__name__)

# ── Regex patterns for schema enrichment ─────────────────────────

_BON_SOL_RE = re.compile(
    r"(?:bon\s*sol|sol\s*porteur|terrain\s*naturel\s*porteur|assise)"
    r"[^.\n]{0,80}?"
    r"((?:argile|grave|marne|calcaire|sable|roche|limon)[^.\n]{0,30})",
    re.IGNORECASE,
)
_GROS_BETON_RE = re.compile(
    r"(?:gros\s*béton|béton\s*de\s*propreté)"
    r"[^.\n]{0,60}?"
    r"(\d+[.,]?\d*\s*(?:cm|m)\b)",
    re.IGNORECASE,
)

_NON_PRECISE_RE = re.compile(
    r"(non\s+pr[ée]cis[ée]e?|non\s+mentionn[ée]e?|non\s+d[ée]taill[ée]e?"
    r"|non\s+disponible|inconnue?|n/?a|—|-)\b",
    re.IGNORECASE,
)


def _strip_non_precise(params: dict[str, str]) -> dict[str, str]:
    """Remove params with an unspecified value and filter couches layers accordingly."""
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if key == "couches":
            try:
                couches = json.loads(value)
                filtered = [
                    c for c in couches if not _NON_PRECISE_RE.match(c.get("epaisseur", "").strip())
                ]
                if not filtered:
                    continue
                removed = len(couches) - len(filtered)
                if removed:
                    logger.debug(
                        f"[SCHEMA DEBUG] Stripped {removed} layer(s) with 'non précisée' epaisseur"
                    )
                cleaned[key] = json.dumps(filtered, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                cleaned[key] = value
        elif _NON_PRECISE_RE.match(value.strip()):
            logger.debug(f"[SCHEMA DEBUG] Stripped param '{key}' = '{value}' (non précisé)")
        else:
            cleaned[key] = value
    return cleaned


async def extract_schema(
    context_block: str,
    question: str,
) -> StructuredSchema | None:
    """Extract a parametric schema description from context via Mistral Large."""
    try:
        response = await mistral_client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": SCHEMA_EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Question : {question}\n\n---\n\nContexte :\n\n{context_block[:10000]}"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content  # type: ignore[union-attr]
        if not raw:
            logger.debug("[SCHEMA DEBUG] LLM returned empty response")
            return None

        data = json.loads(raw.strip())
        logger.debug(f"[SCHEMA DEBUG] Raw LLM response: {raw.strip()[:500]}")
        schema_type = data.get("schema_type", "none").strip().lower()

        if schema_type == "none" or schema_type not in SCHEMA_TYPES:
            logger.debug(
                f"[SCHEMA DEBUG] Rejected: type='{schema_type}' not in {list(SCHEMA_TYPES.keys())}"
            )
            return None

        params: dict[str, str] = {}
        raw_params = data.get("params", {})
        allowed_keys = SCHEMA_TYPES[schema_type]
        for key in allowed_keys:
            val = raw_params.get(key)
            if val:
                if key == "couches" and isinstance(val, list):
                    params[key] = json.dumps(val, ensure_ascii=False)
                else:
                    params[key] = str(val)

        params = _strip_non_precise(params)

        logger.debug(
            f"[SCHEMA DEBUG] Parsed params keys: {list(params.keys())} (from allowed: {allowed_keys})"
        )

        if not params:
            logger.debug(
                f"[SCHEMA DEBUG] Rejected (no params): type='{schema_type}', raw_params={raw_params}"
            )
            return None

        title = data.get("title", "").strip() or f"Coupe — {schema_type.replace('_', ' ')}"

        params = _enrich_schema_from_context(schema_type, params, context_block)

        schema = StructuredSchema(schema_type=schema_type, title=title, params=params)
        logger.debug(
            f"[SCHEMA DEBUG] SUCCESS: {schema_type} ({len(params)} params) — {list(params.keys())}"
        )
        return schema
    except Exception as exc:
        logger.debug(f"[SCHEMA DEBUG] EXCEPTION: {exc}")
        logger.exception("Schema extraction failed")
        return None


def _enrich_schema_from_context(
    schema_type: str,
    params: dict[str, str],
    context: str,
) -> dict[str, str]:
    """Enrich schema params by regex-extracting values from context.

    Fills gros_beton and bon_sol for semelle_filante when Mistral
    didn't extract them.
    """
    if schema_type != "semelle_filante":
        return params

    fouille_lines = [
        line.strip()[:120]
        for line in context.split("\n")
        if re.search(r"fouille|fond|cote|profondeur", line, re.IGNORECASE)
    ]
    logger.debug(f"[CHAT DEBUG] Fond de fouille context scan: {len(fouille_lines)} lines found")
    for fl in fouille_lines[:5]:
        logger.debug(f"  → {fl}")

    if "gros_beton" not in params:
        m = _GROS_BETON_RE.search(context)
        if m:
            value = m.group(1).strip()
            params["gros_beton"] = value
            logger.debug(f"[CHAT DEBUG] Enriched gros_beton from context: '{value}'")

    if "bon_sol" not in params:
        m = _BON_SOL_RE.search(context)
        if m:
            value = m.group(1).strip().rstrip(".,;:")
            params["bon_sol"] = value
            logger.debug(f"[CHAT DEBUG] Enriched bon_sol from context: '{value}'")

    return params


async def enrich_schema_with_search(
    schema: StructuredSchema,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> StructuredSchema:
    """Enrich a semelle_filante schema with fond_fouille/bon_sol via targeted search.

    Runs a dedicated semantic search for cote/depth values and extracts
    them with regex from the results.
    """
    targeted_queries = [
        "cote fond de fouille en rigole profondeur niveau",
        "fouille en rigole semelle fondation profondeur cote",
        "gros béton béton de propreté épaisseur sous semelle",
        "terrassement pleine masse plateforme niveau cote",
    ]
    try:
        results = await search_service.search_merged(
            tenant_id=tenant_id,
            project_id=project_id,
            queries=targeted_queries,
            filters=SearchFilters(),
            limit=6,
            score_threshold=0.40,
        )
    except Exception:
        logger.exception("Targeted fond de fouille search failed")
        return schema

    if not results:
        return schema

    targeted_text = "\n".join(sr.text for sr in results)
    logger.debug(
        f"[CHAT DEBUG] Targeted fond de fouille search: "
        f"{len(results)} results, text length={len(targeted_text)}"
    )
    fouille_lines = [
        line.strip()[:120]
        for line in targeted_text.split("\n")
        if re.search(r"cote|niveau|profondeur|fouille|rigole|\d+[.,]\d+\s*m", line, re.IGNORECASE)
    ]
    for fl in fouille_lines[:8]:
        logger.debug(f"  → {fl}")

    params = dict(schema.params)

    if "gros_beton" not in params:
        m = _GROS_BETON_RE.search(targeted_text)
        if m:
            value = m.group(1).strip()
            params["gros_beton"] = value
            logger.debug(f"[CHAT DEBUG] Enriched gros_beton: '{value}'")

    if "bon_sol" not in params:
        m = _BON_SOL_RE.search(targeted_text)
        if m:
            value = m.group(1).strip().rstrip(".,;:")
            params["bon_sol"] = value
            logger.debug(f"[CHAT DEBUG] Enriched bon_sol: '{value}'")

    return StructuredSchema(
        schema_type=schema.schema_type,
        title=schema.title,
        params=params,
    )
