"""Agent layer of the v1 chat, broad scope only: judge whether the retrieved passages can answer,
and reformulate one retry search on what is missing (j2-agent-recommencer-large)."""

import json
import logging
import re
import uuid
from dataclasses import dataclass

from mistralai.models import UsageInfo

from app.core.config import settings
from app.core.mistral import mistral_client, mistral_fast_limiter, mistral_large_limiter
from app.schemas.search import SearchResult
from app.services.chat.model_routing import is_large, short_call_model

logger = logging.getLogger(__name__)

JUDGE_PASSAGE_CHARS = 150
MISSING_MAX_CHARS = 300
REFORMULATED_MAX_WORDS = 25
PASSAGE_SEPARATOR = "\n---\n"

JUDGE_PROMPT = (
    "Tu es un contrôleur de pertinence pour un assistant qui répond à des questions sur des "
    "documents de construction (CCTP, DPGF). On te donne une question et le début de chacun des "
    "passages récupérés pour y répondre.\n"
    "Décide si ces passages contiennent l'information demandée par la question.\n"
    "- « suffisant » : au moins un passage traite directement de ce que demande la question.\n"
    "- « insuffisant » : aucun passage ne traite de ce que demande la question, ou il en manque "
    "une partie essentielle. Dis alors en quelques mots ce qui manque.\n"
    "Réponds UNIQUEMENT en JSON, sans texte autour :\n"
    '{"verdict": "suffisant" | "insuffisant", "manque": "<ce qui manque, court, vide si suffisant>"}'
)

REFORMULATE_PROMPT = (
    "Tu écris une requête de recherche pour retrouver, dans des documents de construction "
    "(CCTP, DPGF), l'information qui manque pour répondre à une question. Une première recherche "
    "n'a pas suffi.\n"
    "Écris une requête courte (mots-clés techniques, termes du métier, synonymes usuels), centrée "
    "sur ce qui manque, différente de la première requête.\n"
    "Réponds UNIQUEMENT en JSON, sans texte autour :\n"
    '{"query": "<requête de recherche>"}'
)

_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*")
_FENCE_CLOSE_RE = re.compile(r"\s*```$")


@dataclass(frozen=True)
class Judgment:
    """Verdict of the sufficiency judge; `missing` is empty when sufficient."""

    sufficient: bool
    missing: str


_SUFFICIENT = Judgment(True, "")


def should_judge(mode: str, scope: str, *, has_query: bool, retried: bool) -> bool:
    """Judge only a broad, on-topic v1 question that has not been retried yet."""
    return mode == "v1" and scope == "broad" and has_query and not retried


def should_retry(judgment: Judgment, *, retried: bool) -> bool:
    """One retry at most, on an insufficient judgment."""
    return not judgment.sufficient and not retried


def _load_json_object(raw: str | None) -> dict[str, object] | None:
    if raw is None:
        return None
    text = _FENCE_CLOSE_RE.sub("", _FENCE_OPEN_RE.sub("", raw.strip()))
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_judgment(raw: str | None) -> Judgment:
    """Parse the judge reply; anything unreadable counts as sufficient (never retry on a failure)."""
    data = _load_json_object(raw)
    if data is None:
        return _SUFFICIENT
    verdict = data.get("verdict")
    if not isinstance(verdict, str) or verdict.strip().lower() != "insuffisant":
        return _SUFFICIENT
    missing = data.get("manque")
    text = missing.strip() if isinstance(missing, str) else ""
    return Judgment(False, text[:MISSING_MAX_CHARS])


def condense_passages(context_block: str, *, max_chars: int = JUDGE_PASSAGE_CHARS) -> str:
    """Cut every passage of a rendered context block to its first `max_chars` characters."""
    if not context_block:
        return ""
    return PASSAGE_SEPARATOR.join(
        part[:max_chars] for part in context_block.split(PASSAGE_SEPARATOR)
    )


def _merge_key(result: SearchResult) -> tuple[uuid.UUID, int, int, str]:
    return (result.document_id, result.page, result.position, result.text[:200])


def merge_results(first: list[SearchResult], second: list[SearchResult]) -> list[SearchResult]:
    """First results in order, then unseen second results in order; a duplicate keeps its first copy."""
    merged: list[SearchResult] = []
    seen: set[tuple[uuid.UUID, int, int, str]] = set()
    for result in [*first, *second]:
        key = _merge_key(result)
        if key in seen:
            continue
        seen.add(key)
        merged.append(result)
    return merged


def _normalize_query(query: str) -> str:
    return " ".join(query.split()).lower()


def parse_reformulation(raw: str | None, *, first_query: str) -> str | None:
    """Parse the reformulated query; None when unreadable, blank or equal to the first query."""
    data = _load_json_object(raw)
    if data is None:
        return None
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        return None
    reformulated = " ".join(query.split()[:REFORMULATED_MAX_WORDS])
    if _normalize_query(reformulated) == _normalize_query(first_query):
        return None
    return reformulated


async def _complete(system: str, user: str, usage_sink: list[UsageInfo]) -> str | None:
    model = short_call_model(settings.retrieval_mode, settings.v1_fast_model)
    limiter = mistral_large_limiter if is_large(model) else mistral_fast_limiter
    await limiter.wait()
    response = await mistral_client.chat.complete_async(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_tokens=150,
    )
    if response.usage is not None:
        usage_sink.append(response.usage)
    content = response.choices[0].message.content  # type: ignore[union-attr]
    return content if isinstance(content, str) else None


async def judge_sufficiency(
    question: str, context_block: str, *, usage_sink: list[UsageInfo]
) -> Judgment:
    """Ask Mistral whether the passages entering the context can answer the question."""
    if not context_block.strip():
        return Judgment(False, "")
    user = f"Question : {question}\n\nPassages (début de chacun) :\n\n{condense_passages(context_block)}"
    try:
        raw = await _complete(JUDGE_PROMPT, user, usage_sink)
    except Exception:
        logger.exception("Sufficiency judge failed, serving the first search")
        return _SUFFICIENT
    return parse_judgment(raw)


async def reformulate(
    question: str, missing: str, *, first_query: str, usage_sink: list[UsageInfo]
) -> str | None:
    """Write the retry search query from the question and what the judge found missing."""
    user = (
        f"Question : {question}\n"
        f"Ce qui manque : {missing or 'non précisé'}\n"
        f"Première requête : {first_query}"
    )
    try:
        raw = await _complete(REFORMULATE_PROMPT, user, usage_sink)
    except Exception:
        logger.exception("Retry query reformulation failed, no retry")
        return None
    return parse_reformulation(raw, first_query=first_query)
