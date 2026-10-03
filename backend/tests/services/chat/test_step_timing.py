from app.services.chat.step_timing import STEP_NAMES, step_fields


def test_step_fields_turns_each_known_step_into_a_flat_ms_key() -> None:
    assert step_fields([("rewrite", 812), ("search", 430)]) == {
        "rewrite_ms": 812,
        "search_ms": 430,
    }


def test_step_fields_keeps_the_first_value_of_a_repeated_duration() -> None:
    assert step_fields([("search", 400), ("search", 900)]) == {"search_ms": 400}


def test_step_fields_sums_the_waits_of_one_step() -> None:
    assert step_fields([("judge_wait", 300), ("judge_wait", 650)]) == {
        "judge_wait_ms": 950
    }


def test_step_fields_ignores_unknown_step_names() -> None:
    assert step_fields([("rewrite", 10), ("question_text", 5)]) == {"rewrite_ms": 10}


def test_step_fields_clamps_negative_values_to_zero() -> None:
    assert step_fields([("enrich", -3)]) == {"enrich_ms": 0}


def test_step_names_cover_every_measured_step() -> None:
    assert sorted(STEP_NAMES) == sorted(
        [
            "rewrite",
            "rewrite_wait",
            "search",
            "enrich",
            "judge",
            "judge_wait",
            "retry_search",
            "enrich_retry",
            "generate",
            "generate_wait",
            "generate_first_token",
            "generate_stream",
            "extract_table",
            "extract_table_wait",
            "extract_schema",
            "extract_schema_wait",
        ]
    )


def test_every_limited_step_has_its_wait_name() -> None:
    for name in ["rewrite", "judge", "generate", "extract_table", "extract_schema"]:
        assert f"{name}_wait" in STEP_NAMES


def test_step_fields_keeps_a_zero_wait() -> None:
    assert step_fields([("generate_wait", 0)]) == {"generate_wait_ms": 0}


def test_step_fields_of_nothing_is_empty() -> None:
    assert step_fields([]) == {}


def test_step_fields_values_are_ints() -> None:
    fields = step_fields([("rewrite", 812), ("judge_wait", 300), ("judge_wait", 650)])
    assert fields == {"rewrite_ms": 812, "judge_wait_ms": 950}
    assert all(type(value) is int for value in fields.values())
