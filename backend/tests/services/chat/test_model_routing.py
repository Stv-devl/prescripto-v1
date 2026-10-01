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
