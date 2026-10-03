from app.services.chat.model_routing import (
    is_large,
    price_for,
    short_call_model,
)


def test_short_call_model_in_v1_is_the_configured_fast_model() -> None:
    assert short_call_model("v1", "mistral-small-latest") == "mistral-small-latest"


def test_short_call_model_in_baseline_is_mistral_large() -> None:
    assert short_call_model("baseline", "mistral-small-latest") == "mistral-large-latest"


def test_price_of_mistral_small_latest_is_0_15_in_and_0_6_out() -> None:
    assert price_for("mistral-small-latest") == {"input": 0.15, "output": 0.6}


def test_price_of_mistral_large_is_0_5_in_and_1_5_out() -> None:
    assert price_for("mistral-large-latest") == {"input": 0.5, "output": 1.5}


def test_short_call_model_follows_any_configured_fast_model() -> None:
    assert short_call_model("v1", "ministral-8b-latest") == "ministral-8b-latest"


def test_price_of_mistral_small_2603_matches_small_latest() -> None:
    assert price_for("mistral-small-2603") == {"input": 0.15, "output": 0.6}


def test_is_large_is_true_only_for_mistral_large_latest() -> None:
    assert is_large("mistral-large-latest") is True
    assert is_large("mistral-small-latest") is False
    assert is_large("mistral-small-2603") is False


def test_price_of_an_unknown_model_falls_back_to_the_large_price() -> None:
    assert price_for("some-unlisted-model") == {"input": 0.5, "output": 1.5}


def test_short_call_model_in_an_unknown_mode_is_mistral_large() -> None:
    assert short_call_model("v2", "mistral-small-latest") == "mistral-large-latest"


def test_is_large_is_true_for_a_pinned_mistral_large_version() -> None:
    assert is_large("mistral-large-2411") is True


def test_prompt_cache_key_under_v1_is_the_fixed_key_of_each_prompt() -> None:
    from app.services.chat.model_routing import prompt_cache_key

    assert prompt_cache_key("v1", "generation") == "prescripto-v1-generation"
    assert prompt_cache_key("v1", "rewrite") == "prescripto-v1-rewrite"
    assert prompt_cache_key("v1", "judge") == "prescripto-v1-judge"
    assert prompt_cache_key("v1", "reformulate") == "prescripto-v1-reformulate"


def test_prompt_cache_key_under_baseline_is_none_for_every_prompt() -> None:
    from app.services.chat.model_routing import prompt_cache_key

    assert prompt_cache_key("baseline", "generation") is None
    assert prompt_cache_key("baseline", "rewrite") is None
    assert prompt_cache_key("baseline", "judge") is None
    assert prompt_cache_key("baseline", "reformulate") is None


def test_input_cost_bills_cached_tokens_at_a_tenth_of_the_large_input_price() -> None:
    import pytest

    from app.services.chat.model_routing import input_cost_usd

    large = {"input": 0.5, "output": 1.5}
    assert input_cost_usd(1_000_000, 1_000_000, large) == pytest.approx(0.05)


def test_input_cost_bills_cached_tokens_at_a_tenth_of_the_small_input_price() -> None:
    import pytest

    from app.services.chat.model_routing import input_cost_usd

    small = {"input": 0.15, "output": 0.6}
    assert input_cost_usd(1_000_000, 1_000_000, small) == pytest.approx(0.015)


def test_input_cost_mixes_full_and_cached_price() -> None:
    import pytest

    from app.services.chat.model_routing import input_cost_usd

    large = {"input": 0.5, "output": 1.5}
    assert input_cost_usd(1_000_000, 400_000, large) == pytest.approx(0.32)


def test_input_cost_without_cached_tokens_equals_the_full_input_price() -> None:
    import pytest

    from app.services.chat.model_routing import input_cost_usd

    small = {"input": 0.15, "output": 0.6}
    assert input_cost_usd(1_000_000, 0, small) == pytest.approx(0.15)


def test_prompt_cache_key_does_not_depend_on_tenant_conversation_or_question() -> None:
    import inspect
    import re

    from app.services.chat.model_routing import prompt_cache_key

    assert list(inspect.signature(prompt_cache_key).parameters) == ["mode", "prompt"]
    assert prompt_cache_key("v1", "rewrite") == "prescripto-v1-rewrite"
    assert prompt_cache_key("v1", "rewrite") == "prescripto-v1-rewrite"
    uuid_prefix = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-")
    for prompt in ("generation", "rewrite", "judge", "reformulate"):
        key = prompt_cache_key("v1", prompt)
        assert key is not None
        assert uuid_prefix.search(key) is None


def test_cached_tokens_of_reads_prompt_tokens_details_from_the_usage_extras() -> None:
    from mistralai.client.models import UsageInfo

    from app.services.chat.model_routing import cached_tokens_of

    usage = UsageInfo.model_validate(
        {
            "prompt_tokens": 1192,
            "completion_tokens": 5,
            "total_tokens": 1197,
            "prompt_tokens_details": {"cached_tokens": 1152},
        }
    )
    assert cached_tokens_of(usage) == 1152


def test_cached_tokens_of_none_usage_is_zero() -> None:
    from app.services.chat.model_routing import cached_tokens_of

    assert cached_tokens_of(None) == 0


def test_cached_tokens_of_usage_without_details_is_zero() -> None:
    from mistralai.client.models import UsageInfo

    from app.services.chat.model_routing import cached_tokens_of

    usage = UsageInfo.model_validate(
        {"prompt_tokens": 1192, "completion_tokens": 5, "total_tokens": 1197}
    )
    assert cached_tokens_of(usage) == 0


def test_cached_tokens_of_null_or_non_integer_cached_tokens_is_zero() -> None:
    from mistralai.client.models import UsageInfo

    from app.services.chat.model_routing import cached_tokens_of

    for details in ({"cached_tokens": None}, {"cached_tokens": "64"}, None):
        usage = UsageInfo.model_validate(
            {
                "prompt_tokens": 1192,
                "completion_tokens": 5,
                "total_tokens": 1197,
                "prompt_tokens_details": details,
            }
        )
        assert cached_tokens_of(usage) == 0


def test_cached_tokens_of_is_clamped_to_prompt_tokens() -> None:
    from mistralai.client.models import UsageInfo

    from app.services.chat.model_routing import cached_tokens_of

    usage = UsageInfo.model_validate(
        {
            "prompt_tokens": 100,
            "completion_tokens": 5,
            "total_tokens": 105,
            "prompt_tokens_details": {"cached_tokens": 128},
        }
    )
    assert cached_tokens_of(usage) == 100
