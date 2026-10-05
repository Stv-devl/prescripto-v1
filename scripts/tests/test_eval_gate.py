import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from eval_gate import (
    GateError,
    Measure,
    compare,
    guard_event,
    hits,
    load_measure,
    render_summary,
)

SCRIPT = Path(__file__).resolve().parents[1] / "eval_gate.py"
FP = "a" * 64
OTHER_FP = "b" * 64
REPO = "owner/prescripto-v1"

RESEARCH_RANKS: dict[str, int | None] = {
    "1": 12,
    "2": 2,
    "3": 9,
    "4": 0,
    "5": 0,
    "6": None,
    "7": 0,
    "8": 0,
    "9": 10,
    "10": 0,
    "11": 0,
    "12": 0,
    "13": 8,
    "16": 8,
    "17": 2,
    "18": 1,
    "19": 2,
    "20": None,
}

FAIL_SUMMARY = (
    "### Eval — retrieval recall (18 questions)\n"
    "\n"
    "| metric | reference | current | delta |\n"
    "| --- | --- | --- | --- |\n"
    "| hit@5 | 11 | 9 | -2 |\n"
    "| hit@15 | 16 | 16 | 0 |\n"
    "\n"
    "**Verdict: FAIL** — hit@5 9 < 11\n"
    "\n"
    "Regressed questions — hit@5: 2, 17; hit@15: none\n"
)

PASS_SUMMARY = (
    "### Eval — retrieval recall (18 questions)\n"
    "\n"
    "| metric | reference | current | delta |\n"
    "| --- | --- | --- | --- |\n"
    "| hit@5 | 11 | 11 | 0 |\n"
    "| hit@15 | 16 | 16 | 0 |\n"
    "\n"
    "**Verdict: PASS**\n"
    "\n"
    "Regressed questions — hit@5: none; hit@15: none\n"
)

SMALL_REF: dict[str, int | None] = {"1": 0, "2": 10}

SMALL_PASS_SUMMARY = (
    "### Eval — retrieval recall (2 questions)\n"
    "\n"
    "| metric | reference | current | delta |\n"
    "| --- | --- | --- | --- |\n"
    "| hit@5 | 1 | 1 | 0 |\n"
    "| hit@15 | 2 | 2 | 0 |\n"
    "\n"
    "**Verdict: PASS**\n"
    "\n"
    "Regressed questions — hit@5: none; hit@15: none\n"
)

SMALL_FAIL_SUMMARY = (
    "### Eval — retrieval recall (2 questions)\n"
    "\n"
    "| metric | reference | current | delta |\n"
    "| --- | --- | --- | --- |\n"
    "| hit@5 | 1 | 0 | -1 |\n"
    "| hit@15 | 2 | 1 | -1 |\n"
    "\n"
    "**Verdict: FAIL** — hit@5 0 < 1; hit@15 1 < 2\n"
    "\n"
    "Regressed questions — hit@5: 1; hit@15: 1\n"
)


def measure(ranks: dict[str, int | None], fingerprint: str = FP) -> Measure:
    return Measure(fingerprint=fingerprint, ranks=ranks)


def write_measure(
    path: Path, ranks: dict[str, int | None], fingerprint: str = FP
) -> Path:
    path.write_text(
        json.dumps({"fingerprint": fingerprint, "ranks": ranks}), encoding="utf-8"
    )
    return path


def write_raw(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_cli(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


HOOK_VARS = {
    "GITHUB_EVENT_NAME",
    "GITHUB_EVENT_PATH",
    "GITHUB_REPOSITORY",
    "GITHUB_TRIGGERING_ACTOR",
    "GITHUB_ACTOR",
    "PRESCRIPTO_EVAL_ACTORS",
}


def hook_env(**overrides: str) -> dict[str, str]:
    """Hook environment with an allowed actor by default; tests override what they exercise."""
    env = {k: v for k, v in os.environ.items() if k not in HOOK_VARS}
    env.update(
        {"PRESCRIPTO_EVAL_ACTORS": "Stv-devl", "GITHUB_TRIGGERING_ACTOR": "Stv-devl"}
    )
    env.update(overrides)
    return {k: v for k, v in env.items() if v != "<unset>"}


def pr_event(path: Path, full_name: str) -> Path:
    return write_raw(
        path, {"pull_request": {"head": {"repo": {"full_name": full_name}}}}
    )


# --- Core behaviour ---


def test_hits_counts_ranks_strictly_below_k() -> None:
    assert hits({"1": 0, "2": 4, "3": 5, "4": None}, 5) == 2


def test_hits_at_15_counts_rank_14_and_not_15() -> None:
    assert hits({"1": 14, "2": 15}, 15) == 1


def test_identical_measures_pass() -> None:
    ranks: dict[str, int | None] = {"1": 0, "2": 9, "3": None}
    v = compare(measure(ranks), measure(dict(ranks)))
    assert v.ok is True
    assert v.reason == ""
    assert v.regressed == {5: [], 15: []}


def test_a_drop_in_hit_at_15_fails_with_the_exact_reason() -> None:
    v = compare(measure({"1": 3, "2": None}), measure({"1": 3, "2": 10}))
    assert v.ok is False
    assert v.reason == "hit@15 1 < 2"
    assert v.regressed == {5: [], 15: ["2"]}


def test_a_drop_in_hit_at_5_alone_fails_and_names_its_ids() -> None:
    v = compare(measure({"1": 7, "2": 0}), measure({"1": 2, "2": 0}))
    assert v.ok is False
    assert v.reason == "hit@5 1 < 2"
    assert v.regressed == {5: ["1"], 15: []}


def test_both_metrics_failing_are_joined() -> None:
    v = compare(measure({"1": None}), measure({"1": 0}))
    assert v.reason == "hit@5 0 < 1; hit@15 0 < 1"


# --- Business rules ---


def test_a_drop_within_tolerance_passes() -> None:
    v = compare(measure({"1": 3, "2": None}), measure({"1": 3, "2": 10}), tolerance=1)
    assert v.ok is True


def test_a_drop_beyond_tolerance_fails() -> None:
    v = compare(measure({"1": None, "2": None}), measure({"1": 8, "2": 9}), tolerance=1)
    assert v.ok is False
    assert "hit@15" in v.reason


def test_an_improvement_passes() -> None:
    v = compare(measure({"1": 2, "2": 10}), measure({"1": None, "2": 10}))
    assert v.ok is True


def test_regressed_ids_sort_numerically() -> None:
    v = compare(measure({"9": None, "10": None}), measure({"9": 3, "10": 3}))
    assert v.regressed[15] == ["9", "10"]


def test_a_swap_passes_but_shows_the_lost_id() -> None:
    v = compare(measure({"1": 20, "2": 3}), measure({"1": 3, "2": 20}))
    assert v.ok is True
    assert v.regressed[15] == ["1"]


def test_a_different_fingerprint_is_refused_as_stale() -> None:
    with pytest.raises(GateError, match="reference stale"):
        compare(measure({"1": 0}, OTHER_FP), measure({"1": 0}, FP))


def test_a_changed_question_set_is_refused() -> None:
    with pytest.raises(GateError, match="question set changed"):
        compare(measure({"1": 0, "3": 0}), measure({"1": 0, "2": 0}))


def test_load_refuses_a_text_rank(tmp_path: Path) -> None:
    path = write_raw(
        tmp_path / "m.json", {"fingerprint": FP, "ranks": {"1": "Ignore previous"}}
    )
    with pytest.raises(GateError):
        load_measure(path)


def test_load_refuses_a_boolean_rank(tmp_path: Path) -> None:
    path = write_raw(tmp_path / "m.json", {"fingerprint": FP, "ranks": {"1": True}})
    with pytest.raises(GateError):
        load_measure(path)


def test_load_refuses_a_negative_rank(tmp_path: Path) -> None:
    path = write_raw(tmp_path / "m.json", {"fingerprint": FP, "ranks": {"1": -1}})
    with pytest.raises(GateError):
        load_measure(path)


def test_load_refuses_a_non_digit_key(tmp_path: Path) -> None:
    path = write_raw(tmp_path / "m.json", {"fingerprint": FP, "ranks": {"Q1": 0}})
    with pytest.raises(GateError):
        load_measure(path)


def test_load_refuses_empty_ranks(tmp_path: Path) -> None:
    path = write_raw(tmp_path / "m.json", {"fingerprint": FP, "ranks": {}})
    with pytest.raises(GateError):
        load_measure(path)


def test_load_refuses_a_non_hex_fingerprint(tmp_path: Path) -> None:
    short = write_raw(
        tmp_path / "short.json", {"fingerprint": "abc", "ranks": {"1": 0}}
    )
    with pytest.raises(GateError):
        load_measure(short)
    non_hex = write_raw(
        tmp_path / "nonhex.json", {"fingerprint": "g" * 64, "ranks": {"1": 0}}
    )
    with pytest.raises(GateError):
        load_measure(non_hex)


def test_load_refuses_an_extra_key(tmp_path: Path) -> None:
    path = write_raw(
        tmp_path / "m.json", {"fingerprint": FP, "ranks": {"1": 0}, "note": "x"}
    )
    with pytest.raises(GateError):
        load_measure(path)


def test_summary_renders_the_fail_example_exactly() -> None:
    current = dict(RESEARCH_RANKS)
    current["2"] = 7
    current["17"] = 7
    v = compare(measure(current), measure(dict(RESEARCH_RANKS)))
    assert render_summary(v) == FAIL_SUMMARY


def test_summary_renders_a_pass_exactly() -> None:
    v = compare(measure(dict(RESEARCH_RANKS)), measure(dict(RESEARCH_RANKS)))
    assert render_summary(v) == PASS_SUMMARY


def test_summary_renders_a_positive_delta_with_a_plus() -> None:
    current = dict(RESEARCH_RANKS)
    current["6"] = 3
    v = compare(measure(current), measure(dict(RESEARCH_RANKS)))
    assert "| hit@5 | 11 | 12 | +1 |" in render_summary(v).split("\n")


def test_summary_of_a_pass_with_a_swap_lists_the_lost_id() -> None:
    current = dict(RESEARCH_RANKS)
    current["6"] = 3
    current["2"] = 7
    v = compare(measure(current), measure(dict(RESEARCH_RANKS)))
    text = render_summary(v)
    assert "**Verdict: PASS**" in text
    assert "Regressed questions — hit@5: 2; hit@15: none" in text


def test_guard_event_accepts_an_internal_pull_request() -> None:
    event = {
        "pull_request": {"head": {"repo": {"full_name": "Stv-devl/prescripto-v1"}}}
    }
    assert guard_event("pull_request", event, "Stv-devl/prescripto-v1") is True


def test_guard_event_refuses_a_fork() -> None:
    event = {"pull_request": {"head": {"repo": {"full_name": "someone/prescripto-v1"}}}}
    assert guard_event("pull_request", event, REPO) is False


def test_guard_event_refuses_a_missing_head_repo() -> None:
    assert (
        guard_event("pull_request", {"pull_request": {"head": {"repo": None}}}, REPO)
        is False
    )
    assert guard_event("pull_request", {"pull_request": {"head": {}}}, REPO) is False
    assert guard_event("pull_request", {"pull_request": {}}, REPO) is False
    assert guard_event("pull_request", {}, REPO) is False


def test_guard_event_accepts_workflow_dispatch() -> None:
    assert guard_event("workflow_dispatch", {}, REPO) is True


def test_guard_event_refuses_other_events() -> None:
    event = {"pull_request": {"head": {"repo": {"full_name": REPO}}}}
    assert guard_event("pull_request_target", event, REPO) is False
    assert guard_event("push", event, REPO) is False


# --- CLI (edge cases) ---


def test_cli_check_appends_the_summary_and_exits_0_on_pass(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    summary = tmp_path / "summary.md"
    summary.write_text("prior\n", encoding="utf-8")
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--summary", str(summary)
    )
    assert result.returncode == 0
    assert summary.read_text(encoding="utf-8") == "prior\n" + SMALL_PASS_SUMMARY


def test_cli_check_exits_1_on_regression(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", {"1": None, "2": 10})
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    summary = tmp_path / "summary.md"
    summary.write_text("prior\n", encoding="utf-8")
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--summary", str(summary)
    )
    assert result.returncode == 1
    assert summary.read_text(encoding="utf-8") == "prior\n" + SMALL_FAIL_SUMMARY


def test_cli_check_missing_reference_prints_one_line(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(tmp_path / "absent.json")
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate: reference missing\n"


def test_cli_check_unreadable_reference_exits_1(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    r = tmp_path / "r.json"
    r.write_text("{", encoding="utf-8")
    result = run_cli("check", "--measure", str(m), "--reference", str(r))
    assert result.returncode == 1
    assert result.stdout == "eval gate: reference unreadable\n"


def test_cli_check_missing_measure_prints_one_line(tmp_path: Path) -> None:
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli(
        "check", "--measure", str(tmp_path / "absent.json"), "--reference", str(r)
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate: measure missing\n"
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_check_invalid_measure_prints_one_line(tmp_path: Path) -> None:
    m = write_raw(tmp_path / "m.json", {"ranks": {}})
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli("check", "--measure", str(m), "--reference", str(r))
    assert result.returncode == 1
    assert result.stdout == "eval gate: invalid measure\n"


def test_cli_usage_error_exits_2() -> None:
    result = run_cli("frobnicate")
    assert result.returncode == 2


def test_cli_reference_force_overwrites(tmp_path: Path) -> None:
    first = write_measure(tmp_path / "first.json", {"1": 0})
    second = write_measure(tmp_path / "second.json", {"1": 9, "2": None})
    out = tmp_path / "ref.json"
    assert (
        run_cli("reference", "--measure", str(first), "--out", str(out)).returncode == 0
    )
    result = run_cli(
        "reference", "--measure", str(second), "--out", str(out), "--force"
    )
    assert result.returncode == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "fingerprint": FP,
        "ranks": {"1": 9, "2": None},
    }


def test_cli_never_echoes_input_content(tmp_path: Path) -> None:
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    bad_payloads: list[object] = [
        {"fingerprint": FP, "ranks": {"1": "SECRET-TEXT"}},
        {"fingerprint": FP, "ranks": {"SECRET-TEXT": 0}},
        {"fingerprint": "SECRET-TEXT", "ranks": {"1": 0}},
    ]
    for i, payload in enumerate(bad_payloads):
        m = write_raw(tmp_path / f"m{i}.json", payload)
        result = run_cli("check", "--measure", str(m), "--reference", str(r))
        assert result.returncode == 1
        assert result.stdout == "eval gate: invalid measure\n"
        assert result.stderr == ""


def test_cli_reference_writes_the_measure_and_refuses_to_overwrite(
    tmp_path: Path,
) -> None:
    first = write_measure(tmp_path / "first.json", {"1": 0, "2": None})
    second = write_measure(tmp_path / "second.json", {"1": 9})
    out = tmp_path / "ref.json"
    ok = run_cli("reference", "--measure", str(first), "--out", str(out))
    assert ok.returncode == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "fingerprint": FP,
        "ranks": {"1": 0, "2": None},
    }
    before = out.read_bytes()
    refused = run_cli("reference", "--measure", str(second), "--out", str(out))
    assert refused.returncode == 1
    assert out.read_bytes() == before


def test_cli_hook_reads_github_env(tmp_path: Path) -> None:
    fork_event = pr_event(tmp_path / "fork.json", "someone/prescripto-v1")
    internal_event = pr_event(tmp_path / "internal.json", REPO)

    fork = run_cli(
        "hook",
        env=hook_env(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_EVENT_PATH=str(fork_event),
            GITHUB_REPOSITORY=REPO,
        ),
    )
    assert fork.returncode == 1
    assert fork.stdout == "eval gate hook: refused\n"

    internal = run_cli(
        "hook",
        env=hook_env(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_EVENT_PATH=str(internal_event),
            GITHUB_REPOSITORY=REPO,
        ),
    )
    assert internal.returncode == 0
    assert internal.stdout == "eval gate hook: allowed\n"

    no_path = run_cli(
        "hook",
        env=hook_env(GITHUB_EVENT_NAME="pull_request", GITHUB_REPOSITORY=REPO),
    )
    assert no_path.returncode == 1
    assert no_path.stdout == "eval gate hook: refused\n"


def test_cli_hook_never_prints_event_fields(tmp_path: Path) -> None:
    event = pr_event(tmp_path / "fork.json", "SECRET-ORG/x")
    result = run_cli(
        "hook",
        env=hook_env(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_EVENT_PATH=str(event),
            GITHUB_REPOSITORY=REPO,
        ),
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate hook: refused\n"
    assert result.stderr == ""


def test_cli_selfcheck_exits_0() -> None:
    result = run_cli("selfcheck")
    assert result.returncode == 0
    assert result.stdout == "eval gate: ok\n"


# --- Review additions (2026-10-05) ---


def test_tolerance_applies_to_each_metric_separately() -> None:
    v = compare(measure({"1": 7, "2": None}), measure({"1": 3, "2": 10}), tolerance=1)
    assert v.ok is True


def test_cli_check_passes_the_tolerance_option(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", {"1": 0, "2": None})
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--tolerance", "1"
    )
    assert result.returncode == 0


def test_cli_rejects_a_negative_tolerance(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--tolerance", "-1"
    )
    assert result.returncode == 2


def test_cli_check_stale_reference_prints_one_line(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF), OTHER_FP)
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli("check", "--measure", str(m), "--reference", str(r))
    assert result.returncode == 1
    assert (
        result.stdout == "eval gate: reference stale: corpus or question set changed\n"
    )
    assert result.stderr == ""


def test_cli_check_summary_write_failure_prints_one_line(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    result = run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--summary", str(tmp_path)
    )
    assert result.returncode == 1
    assert result.stdout.endswith("eval gate: summary not writable\n")
    assert result.stderr == ""


def test_cli_check_creates_a_missing_summary_file(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    r = write_measure(tmp_path / "r.json", dict(SMALL_REF))
    summary = tmp_path / "new-summary.md"
    run_cli(
        "check", "--measure", str(m), "--reference", str(r), "--summary", str(summary)
    )
    assert summary.read_text(encoding="utf-8") == SMALL_PASS_SUMMARY


def test_cli_reference_missing_measure_prints_one_line(tmp_path: Path) -> None:
    result = run_cli(
        "reference",
        "--measure",
        str(tmp_path / "absent.json"),
        "--out",
        str(tmp_path / "r.json"),
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate: measure missing\n"


def test_cli_reference_invalid_measure_prints_one_line(tmp_path: Path) -> None:
    m = write_raw(tmp_path / "m.json", {"ranks": {}})
    result = run_cli(
        "reference", "--measure", str(m), "--out", str(tmp_path / "r.json")
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate: invalid measure\n"


def test_cli_reference_refusal_prints_one_line(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    out = tmp_path / "ref.json"
    run_cli("reference", "--measure", str(m), "--out", str(out))
    result = run_cli("reference", "--measure", str(m), "--out", str(out))
    assert result.stdout == "eval gate: reference exists, use --force to replace it\n"


def test_cli_reference_write_failure_prints_one_line(tmp_path: Path) -> None:
    m = write_measure(tmp_path / "m.json", dict(SMALL_REF))
    result = run_cli(
        "reference",
        "--measure",
        str(m),
        "--out",
        str(tmp_path / "absent-dir" / "r.json"),
    )
    assert result.returncode == 1
    assert result.stdout == "eval gate: reference not writable\n"
    assert result.stderr == ""


def test_cli_hook_refuses_a_malformed_event_file(tmp_path: Path) -> None:
    as_list = write_raw(tmp_path / "list.json", ["pull_request"])
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    for path in (as_list, broken, tmp_path):
        result = run_cli(
            "hook",
            env=hook_env(
                GITHUB_EVENT_NAME="pull_request",
                GITHUB_EVENT_PATH=str(path),
                GITHUB_REPOSITORY=REPO,
            ),
        )
        assert result.returncode == 1
        assert result.stdout == "eval gate hook: refused\n"
        assert result.stderr == ""


def test_guard_event_refuses_an_empty_repo() -> None:
    event = {"pull_request": {"head": {"repo": {"full_name": ""}}}}
    assert guard_event("pull_request", event, "") is False


# --- Review attempt 2: the hook also requires an allowed triggering actor ---
# The event file lives in the runner's _work dir, which a lingering process could rewrite;
# the actor comes from the Worker's environment and the allowlist from the root-owned .env.


def _internal_hook(
    tmp_path: Path, **overrides: str
) -> subprocess.CompletedProcess[str]:
    event = pr_event(tmp_path / "internal.json", REPO)
    return run_cli(
        "hook",
        env=hook_env(
            GITHUB_EVENT_NAME="pull_request",
            GITHUB_EVENT_PATH=str(event),
            GITHUB_REPOSITORY=REPO,
            **overrides,
        ),
    )


def test_cli_hook_refuses_an_actor_outside_the_allowlist(tmp_path: Path) -> None:
    result = _internal_hook(tmp_path, GITHUB_TRIGGERING_ACTOR="someone")
    assert result.returncode == 1
    assert result.stdout == "eval gate hook: refused\n"


def test_cli_hook_refuses_without_an_allowlist(tmp_path: Path) -> None:
    result = _internal_hook(tmp_path, PRESCRIPTO_EVAL_ACTORS="<unset>")
    assert result.returncode == 1
    assert result.stdout == "eval gate hook: refused\n"


def test_cli_hook_refuses_without_any_actor(tmp_path: Path) -> None:
    result = _internal_hook(tmp_path, GITHUB_TRIGGERING_ACTOR="<unset>")
    assert result.returncode == 1


def test_cli_hook_falls_back_to_github_actor(tmp_path: Path) -> None:
    result = _internal_hook(
        tmp_path, GITHUB_TRIGGERING_ACTOR="<unset>", GITHUB_ACTOR="Stv-devl"
    )
    assert result.returncode == 0
    assert result.stdout == "eval gate hook: allowed\n"


def test_cli_hook_accepts_an_actor_from_a_comma_separated_allowlist(
    tmp_path: Path,
) -> None:
    result = _internal_hook(
        tmp_path,
        PRESCRIPTO_EVAL_ACTORS="someone-else, Stv-devl",
        GITHUB_TRIGGERING_ACTOR="Stv-devl",
    )
    assert result.returncode == 0


def test_cli_hook_actor_match_is_exact(tmp_path: Path) -> None:
    result = _internal_hook(tmp_path, GITHUB_TRIGGERING_ACTOR="Stv-devl-bot")
    assert result.returncode == 1


def test_cli_hook_refuses_an_actor_that_is_a_substring_of_the_allowlist(
    tmp_path: Path,
) -> None:
    result = _internal_hook(tmp_path, GITHUB_TRIGGERING_ACTOR="devl")
    assert result.returncode == 1
