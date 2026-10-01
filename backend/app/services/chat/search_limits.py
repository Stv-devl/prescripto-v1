"""How many passages the narrow-scope chat search asks for.

Under `RETRIEVAL_MODE=v1` the narrow-scope search limit is configurable; the per-query floor of
`search_merged` scales with it, so a smaller limit is not undone by the number of queries. At the
baseline limit (20) the limits are the historical `max(20, n * 5)`. Pure functions: no I/O, no
settings.
"""

from typing import Literal

BASELINE_SEARCH_LIMIT = 20


def narrow_search_limit(mode: Literal["baseline", "v1"], configured: int) -> int:
    """Narrow-scope search limit: BASELINE_SEARCH_LIMIT under baseline, `configured` under v1."""
    return configured if mode == "v1" else BASELINE_SEARCH_LIMIT


def query_limits(search_limit: int, *, main_queries: int, forced_queries: int) -> tuple[int, int]:
    """`(main_limit, forced_limit)` for `search_merged`, at least one result per query."""
    per_query = max(1, search_limit // 4)
    return (
        max(search_limit, main_queries * per_query),
        max(search_limit, forced_queries * per_query),
    )
