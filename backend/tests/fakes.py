"""Test doubles that carry behaviour, not just recorded calls.

Their own module rather than `conftest.py`: pytest discourages importing a
conftest, and the two files that use these are about to freeze — so the import
path freezes with them.
"""

from dataclasses import dataclass, replace

from qdrant_client.http.exceptions import UnexpectedResponse


@dataclass
class FakePoint:
    """One stored point: what a Qdrant hit exposes to the search service."""

    id: str
    payload: dict[str, object]
    score: float = 0.9


@dataclass
class FakeCollection:
    """One collection name, as `ensure_collection` reads it."""

    name: str


@dataclass
class FakeCollections:
    """What `get_collections()` returns — only `.collections` is read."""

    collections: list[FakeCollection]


class FakeQdrant:
    """In-memory Qdrant double that really applies `Filter(must=[FieldCondition])`.

    Tenant isolation on the vector store IS the filter, so a double that ignores
    filters lets every cross-tenant test pass while proving nothing. This one
    keeps its points and answers from them: the assertion is on which points
    survive, an observable effect, rather than on a call argument.

    It holds its points, so `delete` is observable and a search that queries
    twice — `search_documents` retries at a lower threshold when the first pass
    finds nothing — sees the same store both times.

    Deliberately partial: only `must` with `MatchValue`, which is all
    `search.py` and `embedding.py` build. Every unsupported shape (`should`,
    `must_not`, a nested filter) either returns too many points or raises, never
    too few — so the double cannot make a test pass that should have failed.

    `score_rounds` overrides the scores for successive `search` calls, one entry
    per call. It exists because the double ignores the query vector, so without
    it every query of a multi-query search sees identical hits — and a guarantee
    phrased per query cannot be told apart from one that ignores them.
    """

    def __init__(
        self,
        points: list[FakePoint] | None = None,
        *,
        payload_index_error: UnexpectedResponse | None = None,
        score_rounds: list[dict[str, float]] | None = None,
    ) -> None:
        self.points: list[FakePoint] = list(points or [])
        self.created_indexes: list[str] = []
        self.payload_batches: list[int] = []
        self._payload_index_error = payload_index_error
        self._score_rounds = list(score_rounds or [])
        self.search_calls = 0

    async def batch_update_points(
        self, *, collection_name: str, update_operations: list[object]
    ) -> None:
        """Applies each payload operation, and records how many travelled together.

        The size of each round trip is the point: an enrichment that sends one
        request per chunk and one that groups them both end with the same
        payloads in store, so only the batching is observable.
        """
        self.payload_batches.append(len(update_operations))
        for operation in update_operations:
            merge = getattr(operation, "set_payload", None)
            replace_with = getattr(operation, "overwrite_payload", None)
            change = merge or replace_with
            if change is None:
                continue
            for point_id in change.points:
                for point in self.points:
                    if str(point.id) != str(point_id):
                        continue
                    # The difference is the whole point of the repair: a merge
                    # leaves the legacy `doc_type` key in place, so the point
                    # would still look legacy on the next run.
                    if replace_with is not None:
                        point.payload = dict(change.payload)
                    else:
                        point.payload.update(change.payload)

    @staticmethod
    def _matches(point: FakePoint, condition_filter: object) -> bool:
        """Every `must` condition holds. Values compare as strings, as Qdrant stores them."""
        for condition in getattr(condition_filter, "must", None) or []:
            if str(point.payload.get(condition.key)) != str(condition.match.value):
                return False
        return True

    async def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        query_filter: object = None,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[FakePoint]:
        round_scores = (
            self._score_rounds[self.search_calls]
            if self.search_calls < len(self._score_rounds)
            else {}
        )
        self.search_calls += 1

        matched = [p for p in self.points if self._matches(p, query_filter)]
        scored = [(round_scores.get(str(p.id), p.score), p) for p in matched]
        above = [(score, p) for score, p in scored if score >= score_threshold]
        ordered = sorted(above, key=lambda pair: pair[0], reverse=True)[:limit]
        return [replace(point, score=score) for score, point in ordered]

    async def delete(self, *, collection_name: str, points_selector: object = None) -> None:
        """Delete by filter, or by a bare list of point ids.

        The list form is the one the chunk mutations pass. Sent through
        `_matches` it would look like "no conditions" and empty the whole store,
        so a test asserting another tenant's point survived would fail on the
        double rather than on the service.
        """
        if isinstance(points_selector, list):
            wanted = {str(i) for i in points_selector}
            self.points = [p for p in self.points if str(p.id) not in wanted]
            return
        self.points = [p for p in self.points if not self._matches(p, points_selector)]

    async def upsert(self, *, collection_name: str, points: list[object]) -> None:
        """Store points so a test can assert the payload a write produced.

        Converts to `FakePoint`: a `PointStruct` has no `.score`, and a later
        `search()` reads it.
        """
        for point in points:
            point_id = str(getattr(point, "id", ""))
            payload = getattr(point, "payload", None) or {}
            self.points = [p for p in self.points if str(p.id) != point_id]
            self.points.append(FakePoint(id=point_id, payload=dict(payload)))

    async def get_collections(self) -> "FakeCollections":
        """What `ensure_collection` reads before indexing.

        Reports the collection as already there, which makes the
        `create_collection` branch unreachable — so the double does not need it.
        """
        return FakeCollections(collections=[FakeCollection(name="documents")])

    async def create_collection(self, *, collection_name: str, vectors_config: object) -> None:
        """Unreachable while `get_collections` reports the collection present.

        Kept so the double's shape matches the real client's, in case a future
        test drives the collection-creation branch.
        """

    async def create_payload_index(
        self,
        *,
        collection_name: str,
        field_name: str,
        field_schema: object = None,
    ) -> None:
        """Record the field as indexed. Idempotent on a repeat, like the real server.

        Verified against a real `qdrant:v1.13.2` server (this repo's pin): a
        second call for a field already indexed answers `200 {"status":"ok",...}`,
        not an error, on both an empty collection and one with 20k points. This
        double mirrors that — a repeat call is a silent no-op, never a raise.

        `payload_index_error`, when set at construction, overrides this and
        raises instead: it stands in for a genuinely different failure (auth
        rejected, a malformed field name, the server unreachable), which real
        Qdrant can still return and which must propagate uncaught.
        """
        if self._payload_index_error is not None:
            raise self._payload_index_error
        if field_name not in self.created_indexes:
            self.created_indexes.append(field_name)

    async def scroll(
        self,
        *,
        collection_name: str,
        scroll_filter: object = None,
        limit: int = 100,
        offset: int | None = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> tuple[list[FakePoint], int | None]:
        matched = [p for p in self.points if self._matches(p, scroll_filter)]
        start = offset or 0
        page = matched[start : start + limit]
        next_offset = start + limit if start + limit < len(matched) else None
        return page, next_offset

    async def count(
        self,
        *,
        collection_name: str,
        count_filter: object = None,
        exact: bool = True,
    ) -> "FakeCountResult":
        matched = [p for p in self.points if self._matches(p, count_filter)]
        return FakeCountResult(count=len(matched))

    async def retrieve(
        self,
        *,
        collection_name: str,
        ids: list[str],
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[FakePoint]:
        wanted = {str(i) for i in ids}
        return [p for p in self.points if str(p.id) in wanted]


@dataclass
class FakeCountResult:
    """What `qdrant-client`'s `.count()` returns — only `.count` is read."""

    count: int
