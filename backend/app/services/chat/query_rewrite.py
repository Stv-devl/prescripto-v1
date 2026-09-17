"""Query rewriting — reformulate user questions for optimal search."""

import json
import logging
import re

from mistralai.models import UsageInfo

from app.core.mistral import mistral_client, mistral_large_limiter
from app.models.message import Message
from app.services.chat.prompts import OFF_TOPIC, REWRITE_PROMPT

logger = logging.getLogger(__name__)


async def rewrite_query(
    question: str,
    history: list[Message],
    usage_sink: list[UsageInfo] | None = None,
) -> tuple[str | None, list[str], str, str, str]:
    """Rewrite a user question into an optimized search query.

    Returns (query, related, scope, structured, schema); query is None if
    off-topic. usage_sink, when given, receives the call's token usage.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": REWRITE_PROMPT}]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": question})

    try:
        await mistral_large_limiter.wait()
        response = await mistral_client.chat.complete_async(
            model="mistral-large-latest",
            messages=messages,
            temperature=0.0,
            max_tokens=300,
        )
        if usage_sink is not None:
            usage_sink.append(response.usage)
        rewritten = response.choices[0].message.content  # type: ignore[union-attr]
        if rewritten and rewritten.strip():
            cleaned = rewritten.strip()
            if OFF_TOPIC in cleaned:
                logger.debug(f"[SEARCH DEBUG] Off-topic detected: '{question}'")
                return None, [], "specific", "none", "none"

            query, related, scope, structured, schema = _parse_rewrite_response(cleaned)
            logger.debug(
                f"[SEARCH DEBUG] Rewrite: '{question}' → '{query}' "
                f"(related={related}, scope={scope}, structured={structured}, schema={schema})"
            )
            return query, related, scope, structured, schema
    except Exception:
        logger.exception("Query rewrite failed, using original question")

    return question, [], "specific", "none", "none"


def _parse_rewrite_response(raw: str) -> tuple[str, list[str], str, str, str]:
    """Parse the JSON rewrite response, with fallback to raw string."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        query = data.get("query", "").strip()
        scope = data.get("scope", "specific").strip().lower()
        if scope not in ("broad", "specific"):
            scope = "specific"
        structured = data.get("structured", "none").strip().lower()
        if structured not in ("table", "none"):
            structured = "none"
        schema = data.get("schema", "none").strip().lower()
        if schema not in ("schema", "none"):
            schema = "none"

        if query:
            words = query.split()
            if len(words) > 25:
                query = " ".join(words[:25])
                logger.info("Rewrite query truncated from %d to 25 words", len(words))

        raw_related = data.get("related", [])
        related: list[str] = []
        if isinstance(raw_related, list):
            for item in raw_related[:2]:
                if isinstance(item, str) and item.strip():
                    trimmed = item.strip()
                    words_r = trimmed.split()
                    if len(words_r) > 15:
                        trimmed = " ".join(words_r[:15])
                    related.append(trimmed)

        return query or raw, related, scope, structured, schema
    except (json.JSONDecodeError, AttributeError):
        return raw, [], "specific", "none", "none"
