"""Qdrant async client singleton.

`AsyncQdrantClient.search()` was removed in qdrant-client 1.10+ in favour of
`query_points()`, which takes `query=` instead of `query_vector=` and returns
a `QueryResponse` wrapping the hits in `.points` instead of a bare list. The
services under `services/` (frozen test-first files) call `.search(...)` with
the old keyword and expect a bare list back — patched here, at the client
boundary, instead of touching every call site.
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, ScoredPoint

from app.core.config import settings

qdrant_client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


async def _search_compat(
    self: AsyncQdrantClient,
    *,
    collection_name: str,
    query_vector: list[float],
    query_filter: Filter | None = None,
    limit: int = 10,
    score_threshold: float | None = None,
) -> list[ScoredPoint]:
    """Every keyword a `services/` call site actually passes, named explicitly.

    A `**kwargs` passthrough would forward a typo'd or renamed keyword straight
    into `query_points` — which itself ends its signature in `**kwargs: Any` —
    instead of raising. `query_filter` is exactly where the `tenant_id` isolation
    condition lives, so a silently-swallowed keyword there is the silent
    cross-tenant leak `06-database.md` warns about, not just a crash.
    """
    if settings.retrieval_mode == "v1":
        response = await self.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            using="dense",
        )
    else:
        response = await self.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )
    return response.points


qdrant_client.search = _search_compat.__get__(qdrant_client, AsyncQdrantClient)
