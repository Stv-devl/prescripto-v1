"""Select which chat context passages fit the `context_max` budget, best scored first.

Under `RETRIEVAL_MODE=v1` the context builders take passages by descending score until the next one
no longer fits, then render the retained set in document order. The cost of a candidate set is the
exact length of what will be rendered: headers, lot separators and `\\n---\\n` joins, plain or with
article copies merged, whichever is longer. Pure functions: no I/O, no settings.
"""

from collections.abc import Sequence

from app.schemas.search import SearchResult
from app.services.chat.context_dedup import layout_context_parts, render_merged_context

_JOIN = "\n---\n"


def document_order(passages: Sequence[SearchResult]) -> list[SearchResult]:
    """Sort passages by lot, then filename, then position; stable on ties."""
    return sorted(passages, key=lambda p: (p.lot or "unknown", p.filename or "", p.position))


def render_context_parts(passages: Sequence[SearchResult], *, multiple_lots: bool) -> list[str]:
    """Plain context parts of passages already in document order, to be joined by `\\n---\\n`.

    A `=== lot ===` part opens each lot when `multiple_lots`, then one `[file, p.N]` part per
    passage — the layout of `context_dedup.layout_context_parts`, with the plain header.
    """
    entries = [(passage, f"[{passage.filename}, p.{passage.page}]") for passage in passages]
    return layout_context_parts(entries, multiple_lots=multiple_lots)


def _rendered_length(passages: Sequence[SearchResult], *, multiple_lots: bool) -> int:
    ordered = document_order(passages)
    plain = len(_JOIN.join(render_context_parts(ordered, multiple_lots=multiple_lots)))
    merged = render_merged_context(ordered, multiple_lots=multiple_lots)
    return plain if merged is None else max(plain, len(merged))


def select_by_score(
    passages: Sequence[SearchResult], *, context_max: int, multiple_lots: bool
) -> list[SearchResult]:
    """Retain passages by descending score while their rendering fits `context_max`.

    Ties keep input order. Selection stops at the first passage that does not fit, so no passage
    is left out while a lower-scored one is kept. The retained set is returned in document order,
    input order breaking ties, as the historical fill does.
    """
    retained: list[int] = []
    for index in sorted(range(len(passages)), key=lambda i: -passages[i].score):
        candidate = sorted([*retained, index])
        subset = [passages[i] for i in candidate]
        if _rendered_length(subset, multiple_lots=multiple_lots) > context_max:
            break
        retained = candidate
    return document_order([passages[i] for i in retained])
