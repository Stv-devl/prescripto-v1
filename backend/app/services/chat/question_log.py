"""Per-question log record — ids, flags, tokens, cost and timings, never free text.

One record per served question, read by CloudWatch Logs Insights and metric filters
(J3). The record is built from a whitelist of state keys: the question, the rewrite,
the context, the answer and the judge's `missing` text never enter it.
"""

import uuid
from collections.abc import Mapping
from typing import Literal

Outcome = Literal["answered", "no_context", "search_error", "failed"]


def _outcome(state: Mapping[str, object], *, failed: bool) -> Outcome:
    if failed:
        return "failed"
    if state.get("error"):
        return "search_error"
    if not state.get("context_block"):
        return "no_context"
    return "answered"


def build_question_record(
    *,
    state: Mapping[str, object],
    usage: Mapping[str, Mapping[str, int | float]],
    mode: str,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    latency_ms: int,
    ttft_ms: int | None,
    failed: bool,
) -> dict[str, object]:
    """Build the JSON-serialisable `chat_question` record for one question.

    Top-level tokens and cost are `usage["total"]`; `legs` holds every other usage key
    as-is. `judged` is true as soon as the judge node wrote `judgment_missing`, even as
    None (sufficient)."""
    total = usage["total"]
    scope = state.get("scope")
    return {
        "event": "chat_question",
        "tenant_id": str(tenant_id),
        "conversation_id": str(conversation_id),
        "mode": mode,
        "scope": scope if isinstance(scope, str) else None,
        "judged": "judgment_missing" in state,
        "retried": bool(state.get("retried", False)),
        "outcome": _outcome(state, failed=failed),
        "latency_ms": latency_ms,
        "ttft_ms": ttft_ms,
        "input_tokens": total["input_tokens"],
        "cached_tokens": total["cached_tokens"],
        "output_tokens": total["output_tokens"],
        "cost_usd": total["cost_usd"],
        "legs": {name: dict(leg) for name, leg in usage.items() if name != "total"},
    }
