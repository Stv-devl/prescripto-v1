"""Per-step timings of one chat question, turned into flat `<step>_ms` record keys.

Nodes and the Mistral limiter append `(name, ms)` pairs to a per-question collector
(`app.core.timing`); `step_fields` folds them into the `chat_question` record fields.
A duration that repeats keeps its first value; the waits of one step add up.
"""

from collections.abc import Iterable

REWRITE = "rewrite"
SEARCH = "search"
ENRICH = "enrich"
ENRICH_RETRY = "enrich_retry"
JUDGE = "judge"
RETRY_SEARCH = "retry_search"
GENERATE = "generate"
GENERATE_FIRST_TOKEN = "generate_first_token"
GENERATE_STREAM = "generate_stream"
EXTRACT_TABLE = "extract_table"
EXTRACT_SCHEMA = "extract_schema"

WAIT_SUFFIX = "_wait"
LIMITED_STEPS = (REWRITE, JUDGE, GENERATE, EXTRACT_TABLE, EXTRACT_SCHEMA)

STEP_NAMES: tuple[str, ...] = (
    REWRITE,
    REWRITE + WAIT_SUFFIX,
    SEARCH,
    ENRICH,
    JUDGE,
    JUDGE + WAIT_SUFFIX,
    RETRY_SEARCH,
    ENRICH_RETRY,
    GENERATE,
    GENERATE + WAIT_SUFFIX,
    GENERATE_FIRST_TOKEN,
    GENERATE_STREAM,
    EXTRACT_TABLE,
    EXTRACT_TABLE + WAIT_SUFFIX,
    EXTRACT_SCHEMA,
    EXTRACT_SCHEMA + WAIT_SUFFIX,
)

_KNOWN = frozenset(STEP_NAMES)


def step_fields(entries: Iterable[tuple[str, int]]) -> dict[str, int]:
    """Fold collected `(name, ms)` pairs into `<name>_ms` keys for known steps only."""
    fields: dict[str, int] = {}
    for name, ms in entries:
        if name not in _KNOWN:
            continue
        key = f"{name}_ms"
        value = max(0, int(ms))
        if name.endswith(WAIT_SUFFIX):
            fields[key] = fields.get(key, 0) + value
        elif key not in fields:
            fields[key] = value
    return fields
