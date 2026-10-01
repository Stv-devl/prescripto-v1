"""Merge chat context passages that are copies of one another up to their leading article number.

A CCTP repeats the same general clause at the head of every lot (`1.1.3.9.`, `4.1.3.11.`...). The
copies are distinct chunks, so they reach the model once per lot. Under `RETRIEVAL_MODE=v1` the
context builders render each such paragraph once, under a header naming every copy's location.
Pure functions: no I/O, no settings.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.search import SearchResult

_LEADING_ARTICLE_RE = re.compile(
    r"^\s*(?:(?>\d+(?:\.\d+)+)\.|(?>\d+(?:\.\d+)+)(?!\s*(?:m[²³23]?|mm|cm|ml|kg|l|u)\b))\s*",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MergedPassage:
    """One passage of the context: the copy whose text is rendered, and every copy it stands for."""

    kept: SearchResult
    copies: tuple[SearchResult, ...]


def article_dedup_key(text: str) -> str:
    """Key under which two passages are the same paragraph.

    Strips a leading article number of at least two levels. With a final dot it is always an
    article; without one it is kept when a unit follows (a quantity such as `1.25 m²`). The number
    is matched atomically so a failed unit guard cannot backtrack into a shorter prefix. Then
    collapses whitespace and lowercases.
    """
    stripped = _LEADING_ARTICLE_RE.sub("", text, count=1)
    return _WHITESPACE_RE.sub(" ", stripped).strip().lower()


def merge_article_copies(passages: Sequence[SearchResult]) -> list[MergedPassage]:
    """Group passages by `article_dedup_key`, in input order.

    The kept copy is the highest-scored one, the first in input order on a tie. Each group is
    placed where its kept copy stood; the other passages keep their relative order.
    """
    keyed = [(article_dedup_key(passage.text), passage) for passage in passages]
    groups: dict[str, list[SearchResult]] = {}
    kept_by_key: dict[str, SearchResult] = {}
    for key, passage in keyed:
        groups.setdefault(key, []).append(passage)
        current = kept_by_key.get(key)
        if current is None or passage.score > current.score:
            kept_by_key[key] = passage

    merged: list[MergedPassage] = []
    emitted: set[str] = set()
    for key, passage in keyed:
        if key not in emitted and kept_by_key[key] is passage:
            emitted.add(key)
            merged.append(MergedPassage(kept=passage, copies=tuple(groups[key])))
    return merged


def _location(passage: SearchResult) -> tuple[str, int]:
    return (passage.filename, passage.page)


def _format_location(location: tuple[str, int]) -> str:
    filename, page = location
    return f"{filename}, p.{page}"


def passage_header(passage: MergedPassage) -> str:
    """One-line header of a context passage, naming file and page of every copy.

    The lot is left out on purpose: it is document-level metadata, so a multi-lot CCTP carries a
    single lot for all its pages and would mislabel most copies. A single distinct location keeps
    the builder's historical `[filename, p.N]` form. Several are listed kept copy first, then the
    others in input order, each location once.
    """
    locations = [_location(passage.kept)]
    for copy in passage.copies:
        location = _location(copy)
        if location not in locations:
            locations.append(location)

    if len(locations) == 1:
        return f"[{passage.kept.filename}, p.{passage.kept.page}]"
    head, *others = (_format_location(location) for location in locations)
    return f"[{head} ; aussi : {' ; '.join(others)}]"


def render_merged_context(passages: Sequence[SearchResult], *, multiple_lots: bool) -> str | None:
    """Render the context block with copies merged, or None when no passage has a copy.

    Same layout as the context builders: an optional `=== lot ===` part whenever the kept copy's
    lot changes, header and text per passage, parts joined by `\\n---\\n`.
    """
    merged = merge_article_copies(passages)
    if len(merged) == len(passages):
        return None

    parts: list[str] = []
    previous_lot: str | None = None
    for passage in merged:
        lot_key = passage.kept.lot or "unknown"
        if multiple_lots and lot_key != previous_lot:
            parts.append(f"\n=== {lot_key} ===\n")
            previous_lot = lot_key
        parts.append(f"{passage_header(passage)}\n{passage.kept.text}")
    return "\n---\n".join(parts)
