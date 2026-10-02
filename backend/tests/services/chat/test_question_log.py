import json
import uuid
from collections.abc import Mapping

from app.services.chat.question_log import build_question_record

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CONVERSATION = uuid.UUID("22222222-2222-2222-2222-222222222222")

CONTRACT_KEYS = {
    "event",
    "tenant_id",
    "conversation_id",
    "mode",
    "scope",
    "judged",
    "retried",
    "outcome",
    "latency_ms",
    "ttft_ms",
    "input_tokens",
    "cached_tokens",
    "output_tokens",
    "cost_usd",
    "legs",
}

V1_USAGE: dict[str, dict[str, int | float]] = {
    "rewrite": {
        "input_tokens": 1000,
        "cached_tokens": 0,
        "output_tokens": 100,
        "cost_usd": 0.0024,
    },
    "generation": {
        "input_tokens": 3000,
        "cached_tokens": 1000,
        "output_tokens": 400,
        "cost_usd": 0.0062,
    },
    "agent": {
        "input_tokens": 500,
        "cached_tokens": 0,
        "output_tokens": 20,
        "cost_usd": 0.00011,
    },
    "total": {
        "input_tokens": 4500,
        "cached_tokens": 1000,
        "output_tokens": 520,
        "cost_usd": 0.00871,
    },
}

ZERO_LEG: dict[str, int | float] = {
    "input_tokens": 0,
    "cached_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
}


def _build(
    *,
    state: Mapping[str, object] | None = None,
    usage: Mapping[str, Mapping[str, int | float]] | None = None,
    mode: str = "v1",
    ttft_ms: int | None = 1840,
    failed: bool = False,
) -> dict[str, object]:
    return build_question_record(
        state={"context_block": "ctx"} if state is None else state,
        usage=V1_USAGE if usage is None else usage,
        mode=mode,
        tenant_id=TENANT,
        conversation_id=CONVERSATION,
        latency_ms=5230,
        ttft_ms=ttft_ms,
        failed=failed,
    )


def test_v1_answered_record_carries_every_field_with_totals_copied_from_usage_total() -> None:
    record = _build()

    assert record["event"] == "chat_question"
    assert record["mode"] == "v1"
    assert record["outcome"] == "answered"
    assert record["latency_ms"] == 5230
    assert record["ttft_ms"] == 1840
    assert record["input_tokens"] == 4500
    assert record["cached_tokens"] == 1000
    assert record["output_tokens"] == 520
    assert record["cost_usd"] == 0.00871
    legs = record["legs"]
    assert isinstance(legs, dict)
    assert legs["agent"] == {
        "input_tokens": 500,
        "cached_tokens": 0,
        "output_tokens": 20,
        "cost_usd": 0.00011,
    }
    assert set(legs) == {"rewrite", "generation", "agent"}


def test_record_is_json_serialisable_and_round_trips_to_the_same_dict() -> None:
    record = _build(state={"context_block": "ctx", "scope": "broad", "judgment_missing": None})

    assert json.loads(json.dumps(record)) == record


def test_judged_is_true_when_the_judge_wrote_judgment_missing_even_as_none() -> None:
    record = _build(state={"context_block": "ctx", "judgment_missing": None})

    assert record["judged"] is True


def test_judged_is_false_when_judgment_missing_key_is_absent() -> None:
    record = _build(state={"context_block": "ctx"})

    assert record["judged"] is False


def test_retried_true_and_scope_broad_are_copied_from_state() -> None:
    record = _build(state={"context_block": "ctx", "retried": True, "scope": "broad"})

    assert record["retried"] is True
    assert record["scope"] == "broad"


def test_record_contains_no_free_text_from_state() -> None:
    state: dict[str, object] = {
        "context_block": "SENTINEL_CONTEXT",
        "question": "SENTINEL_QUESTION",
        "search_query": "SENTINEL_SEARCH",
        "related_queries": ["SENTINEL_RELATED"],
        "full_response": "SENTINEL_ANSWER",
        "judgment_missing": "SENTINEL_JUDGMENT",
        "retry_query": "SENTINEL_RETRY",
        "mistral_messages": [{"role": "user", "content": "SENTINEL_MESSAGES"}],
        "sources": [{"text": "SENTINEL_SOURCE"}],
        "scope": "broad",
        "retried": True,
    }

    dumped = json.dumps(_build(state=state))

    assert "SENTINEL" not in dumped


def test_record_keys_are_exactly_the_contract_keys() -> None:
    record = _build(state={"context_block": "ctx", "question": "extra", "scope": "specific"})

    assert set(record) == CONTRACT_KEYS


def test_baseline_usage_without_agent_leg_yields_legs_without_agent_and_judged_false() -> None:
    usage: dict[str, dict[str, int | float]] = {
        "rewrite": V1_USAGE["rewrite"],
        "generation": V1_USAGE["generation"],
        "total": {
            "input_tokens": 4000,
            "cached_tokens": 1000,
            "output_tokens": 500,
            "cost_usd": 0.0086,
        },
    }

    record = _build(usage=usage, mode="baseline", state={"context_block": "ctx"})

    legs = record["legs"]
    assert isinstance(legs, dict)
    assert set(legs) == {"rewrite", "generation"}
    assert record["judged"] is False
    assert record["mode"] == "baseline"
    assert record["input_tokens"] == 4000


def test_ttft_none_is_kept_as_null() -> None:
    record = _build(ttft_ms=None)

    assert "ttft_ms" in record
    assert record["ttft_ms"] is None
    assert json.loads(json.dumps(record))["ttft_ms"] is None


def test_search_error_state_gives_outcome_search_error_and_zero_generation_leg() -> None:
    usage: dict[str, dict[str, int | float]] = {
        "rewrite": V1_USAGE["rewrite"],
        "generation": dict(ZERO_LEG),
        "total": V1_USAGE["rewrite"],
    }

    record = _build(state={"error": "qdrant down", "context_block": "ctx"}, usage=usage)

    assert record["outcome"] == "search_error"
    legs = record["legs"]
    assert isinstance(legs, dict)
    assert legs["generation"] == {
        "input_tokens": 0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }


def test_empty_context_block_gives_outcome_no_context() -> None:
    record = _build(state={"context_block": ""})

    assert record["outcome"] == "no_context"


def test_failed_flag_wins_over_any_state_and_gives_outcome_failed() -> None:
    record = _build(state={"context_block": "ctx", "error": "boom"}, failed=True)

    assert record["outcome"] == "failed"


def test_empty_state_and_zero_usage_still_build_a_record_without_raising() -> None:
    record = _build(state={}, usage={"total": dict(ZERO_LEG)})

    assert record["scope"] is None
    assert record["judged"] is False
    assert record["outcome"] == "no_context"
    assert record["legs"] == {}
    assert record["cost_usd"] == 0.0


def test_tenant_and_conversation_ids_are_serialised_as_strings() -> None:
    record = _build()

    assert record["tenant_id"] == "11111111-1111-1111-1111-111111111111"
    assert record["conversation_id"] == "22222222-2222-2222-2222-222222222222"
