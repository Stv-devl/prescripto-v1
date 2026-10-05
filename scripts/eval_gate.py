"""Verdict of the retrieval-recall eval gate (J4) — stdlib only.

Reads a measure (question ids, integer ranks, a hex fingerprint) produced by the private harness,
compares it to a reference and renders the public job summary. It never reads, prints or stores
corpus text: anything that is not an id, an integer or a hex digest is refused.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

KS = (5, 15)
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_STALE = "reference stale: corpus or question set changed"


class GateError(Exception):
    """A refusal whose message is a fixed English phrase, never input content."""


@dataclass(frozen=True)
class Measure:
    fingerprint: str
    ranks: dict[str, int | None]


@dataclass(frozen=True)
class Verdict:
    ok: bool
    n_questions: int
    current: dict[int, int]
    reference: dict[int, int]
    regressed: dict[int, list[str]]
    reason: str


def _valid_rank(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _parse_measure(payload: object) -> Measure:
    if not isinstance(payload, dict) or set(payload) != {"fingerprint", "ranks"}:
        raise GateError("invalid measure")
    fingerprint = payload["fingerprint"]
    ranks = payload["ranks"]
    if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
        raise GateError("invalid measure")
    if not isinstance(ranks, dict) or not ranks:
        raise GateError("invalid measure")
    for key, value in ranks.items():
        if not (isinstance(key, str) and key.isdigit() and key.isascii()) or not _valid_rank(value):
            raise GateError("invalid measure")
    return Measure(fingerprint=fingerprint, ranks=dict(ranks))


def load_measure(path: Path) -> Measure:
    """Load and validate a measure file; any malformed content raises GateError."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError("invalid measure") from exc
    return _parse_measure(payload)


def hits(ranks: dict[str, int | None], k: int) -> int:
    """Number of questions whose expected passage ranks strictly below k."""
    return sum(1 for rank in ranks.values() if rank is not None and rank < k)


def _lost(current: dict[str, int | None], reference: dict[str, int | None], k: int) -> list[str]:
    lost = [
        qid
        for qid, ref_rank in reference.items()
        if ref_rank is not None and ref_rank < k and (current[qid] is None or current[qid] >= k)  # type: ignore[operator]
    ]
    return sorted(lost, key=int)


def compare(current: Measure, reference: Measure, tolerance: int = 0) -> Verdict:
    """Compare a measure to the reference; fails when any hit@k drops beyond the tolerance."""
    if current.fingerprint != reference.fingerprint:
        raise GateError(_STALE)
    if set(current.ranks) != set(reference.ranks):
        raise GateError("question set changed")
    cur = {k: hits(current.ranks, k) for k in KS}
    ref = {k: hits(reference.ranks, k) for k in KS}
    failing = [k for k in KS if cur[k] < ref[k] - tolerance]
    return Verdict(
        ok=not failing,
        n_questions=len(current.ranks),
        current=cur,
        reference=ref,
        regressed={k: _lost(current.ranks, reference.ranks, k) for k in KS},
        reason="; ".join(f"hit@{k} {cur[k]} < {ref[k]}" for k in failing),
    )


def _delta(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def render_summary(verdict: Verdict) -> str:
    """Markdown summary for the public job page: aggregates and question ids only."""
    rows = "".join(
        f"| hit@{k} | {verdict.reference[k]} | {verdict.current[k]} | "
        f"{_delta(verdict.current[k] - verdict.reference[k])} |\n"
        for k in KS
    )
    line = "**Verdict: PASS**" if verdict.ok else f"**Verdict: FAIL** — {verdict.reason}"
    regressed = "; ".join(f"hit@{k}: {', '.join(verdict.regressed[k]) or 'none'}" for k in KS)
    return (
        f"### Eval — retrieval recall ({verdict.n_questions} questions)\n"
        "\n"
        "| metric | reference | current | delta |\n"
        "| --- | --- | --- | --- |\n"
        f"{rows}"
        "\n"
        f"{line}\n"
        "\n"
        f"Regressed questions — {regressed}\n"
    )


def guard_event(event_name: str, event: dict[str, object], repo: str) -> bool:
    """True only for a manual dispatch or a pull request whose branch lives in `repo`."""
    if event_name == "workflow_dispatch":
        return True
    if event_name != "pull_request":
        return False
    head_repo: object = event
    for key in ("pull_request", "head", "repo", "full_name"):
        if not isinstance(head_repo, dict):
            return False
        head_repo = head_repo.get(key)
    return isinstance(head_repo, str) and bool(head_repo) and head_repo == repo


def _fail(message: str) -> int:
    print(f"eval gate: {message}")
    return 1


def _cmd_check(args: argparse.Namespace) -> int:
    if not Path(args.measure).is_file():
        return _fail("measure missing")
    try:
        current = load_measure(Path(args.measure))
    except GateError:
        return _fail("invalid measure")
    if not Path(args.reference).is_file():
        return _fail("reference missing")
    try:
        reference = load_measure(Path(args.reference))
    except GateError:
        return _fail("reference unreadable")
    try:
        verdict = compare(current, reference, tolerance=args.tolerance)
    except GateError as exc:
        return _fail(str(exc))
    summary = render_summary(verdict)
    print(summary, end="")
    if args.summary:
        try:
            with Path(args.summary).open("a", encoding="utf-8") as handle:
                handle.write(summary)
        except OSError:
            return _fail("summary not writable")
    return 0 if verdict.ok else 1


def _cmd_reference(args: argparse.Namespace) -> int:
    if not Path(args.measure).is_file():
        return _fail("measure missing")
    try:
        measure = load_measure(Path(args.measure))
    except GateError:
        return _fail("invalid measure")
    out = Path(args.out)
    if out.exists() and not args.force:
        return _fail("reference exists, use --force to replace it")
    try:
        out.write_text(
            json.dumps({"fingerprint": measure.fingerprint, "ranks": measure.ranks}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        return _fail("reference not writable")
    print("eval gate: reference written")
    return 0


def _actor_allowed() -> bool:
    """The triggering actor (set by the Worker, not read from a file) must be allowlisted.

    The event file sits in the runner's work dir, which a process left by an earlier job could
    rewrite; the actor comes from the job environment and the allowlist from the runner's
    root-owned .env, neither reachable from a job.
    """
    allowlist = {
        name.strip()
        for name in os.environ.get("PRESCRIPTO_EVAL_ACTORS", "").split(",")
        if name.strip()
    }
    actor = os.environ.get("GITHUB_TRIGGERING_ACTOR") or os.environ.get("GITHUB_ACTOR", "")
    return bool(actor) and actor in allowlist


def _cmd_hook(_args: argparse.Namespace) -> int:
    allowed = False
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    try:
        if event_path and _actor_allowed():
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            if isinstance(event, dict):
                allowed = guard_event(
                    os.environ.get("GITHUB_EVENT_NAME", ""),
                    event,
                    os.environ.get("GITHUB_REPOSITORY", ""),
                )
    except (OSError, ValueError):
        allowed = False
    print("eval gate hook: allowed" if allowed else "eval gate hook: refused")
    return 0 if allowed else 1


def _cmd_selfcheck(_args: argparse.Namespace) -> int:
    print("eval gate: ok")
    return 0


def _non_negative_int(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("tolerance must be >= 0")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval_gate.py")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--measure", required=True)
    check.add_argument("--reference", required=True)
    check.add_argument("--tolerance", type=_non_negative_int, default=0)
    check.add_argument("--summary")
    check.set_defaults(run=_cmd_check)

    reference = sub.add_parser("reference")
    reference.add_argument("--measure", required=True)
    reference.add_argument("--out", required=True)
    reference.add_argument("--force", action="store_true")
    reference.set_defaults(run=_cmd_reference)

    sub.add_parser("hook").set_defaults(run=_cmd_hook)
    sub.add_parser("selfcheck").set_defaults(run=_cmd_selfcheck)

    args = parser.parse_args(argv)
    return int(args.run(args))


if __name__ == "__main__":
    sys.exit(main())
