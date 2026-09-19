"""Copy of a collection into its hybrid twin.

The copy is the one operation of the hybrid plan that does not filter by
`tenant_id`: it moves a whole collection and must preserve each point's own
tenant. The double therefore owns two stores keyed by collection name, and the
cases assert the resulting contents of each store, never how it was called.
"""

import uuid
from unittest.mock import patch

from app.services.ingestion.hybrid_copy import copy_points_to_hybrid
from tests.fakes import FakePoint, FakeQdrant

TENANT_A = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))
PROJECT = str(uuid.UUID("33333333-3333-3333-3333-333333333333"))
DOCUMENT = str(uuid.UUID("44444444-4444-4444-4444-444444444444"))

DTU_INDEX = 149479884
BETON_INDEX = 3775319405
ARME_INDEX = 2498914479


class _TwoCollections:
    def __init__(self, source: FakeQdrant, target: FakeQdrant) -> None:
        self.source = source
        self.target = target
        self.upserted_batch_sizes: list[int] = []

    def _store(self, collection_name: str) -> FakeQdrant:
        return self.source if collection_name == "documents" else self.target

    async def scroll(
        self,
        *,
        collection_name: str,
        limit: int = 100,
        offset: int | None = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> tuple[list[FakePoint], int | None]:
        return await self._store(collection_name).scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )

    async def upsert(self, *, collection_name: str, points: list[object]) -> None:
        self.upserted_batch_sizes.append(len(points))
        await self._store(collection_name).upsert(collection_name=collection_name, points=points)


def _point(
    point_id: str,
    dense: list[float],
    *,
    tenant_id: str = TENANT_A,
    text: str | None = "DTU béton armé",
) -> FakePoint:
    payload: dict[str, object] = {
        "tenant_id": tenant_id,
        "project_id": PROJECT,
        "document_id": DOCUMENT,
        "filename": "cctp_lot02.pdf",
        "page": 4,
        "lot": "02",
        "type": "cctp",
    }
    if text is not None:
        payload["text"] = text
    return FakePoint(id=point_id, payload=payload, vector=dense)


def _stores(points: list[FakePoint]) -> _TwoCollections:
    return _TwoCollections(FakeQdrant(points), FakeQdrant())


def _sparse_indices(point: FakePoint) -> list[int]:
    assert isinstance(point.vector, dict)
    return list(point.vector["sparse"].indices)


async def _copy(stores: _TwoCollections, batch_size: int = 100) -> int:
    with patch("app.services.ingestion.hybrid_copy.qdrant_client", stores):
        return await copy_points_to_hybrid(
            source="documents", target="documents_v1", batch_size=batch_size
        )


async def test_copies_each_point_with_same_id_payload_dense_and_text_sparse_and_returns_count():
    source_point = _point("chunk-1", [0.1, 0.2, 0.3])
    stores = _stores([source_point])

    copied = await _copy(stores)

    assert copied == 1
    assert len(stores.target.points) == 1
    target_point = stores.target.points[0]
    assert target_point.id == "chunk-1"
    assert target_point.payload == {
        "tenant_id": TENANT_A,
        "project_id": PROJECT,
        "document_id": DOCUMENT,
        "filename": "cctp_lot02.pdf",
        "page": 4,
        "lot": "02",
        "type": "cctp",
        "text": "DTU béton armé",
    }
    assert isinstance(target_point.vector, dict)
    assert target_point.vector["dense"] == [0.1, 0.2, 0.3]
    assert _sparse_indices(target_point) == sorted([DTU_INDEX, BETON_INDEX, ARME_INDEX])


async def test_source_is_left_untouched_after_the_copy():
    stores = _stores([_point("a", [0.1, 0.2]), _point("b", [0.3, 0.4], text="béton")])

    await _copy(stores)

    assert [p.id for p in stores.source.points] == ["a", "b"]
    assert [p.vector for p in stores.source.points] == [[0.1, 0.2], [0.3, 0.4]]
    assert [p.payload["text"] for p in stores.source.points] == ["DTU béton armé", "béton"]
    assert stores.source.points[0].payload["tenant_id"] == TENANT_A


async def test_replaying_the_copy_does_not_duplicate_any_point():
    stores = _stores([_point("a", [0.1, 0.2]), _point("b", [0.3, 0.4])])

    await _copy(stores)
    await _copy(stores)

    assert sorted(p.id for p in stores.target.points) == ["a", "b"]


async def test_two_tenants_keep_their_own_tenant_id_in_the_target():
    stores = _stores(
        [
            _point("a", [0.1, 0.2], tenant_id=TENANT_A),
            _point("b", [0.3, 0.4], tenant_id=TENANT_B),
        ]
    )

    await _copy(stores)

    tenants = {str(p.id): p.payload["tenant_id"] for p in stores.target.points}
    assert tenants == {"a": TENANT_A, "b": TENANT_B}


async def test_250_points_with_batch_size_100_are_all_copied_including_the_partial_last_batch():
    stores = _stores([_point(f"p{i}", [float(i), 0.5]) for i in range(250)])

    copied = await _copy(stores, batch_size=100)

    assert copied == 250
    assert sorted(str(p.id) for p in stores.target.points) == sorted(f"p{i}" for i in range(250))


async def test_point_without_text_is_copied_with_an_empty_sparse_vector():
    stores = _stores([_point("a", [0.1, 0.2], text=None)])

    copied = await _copy(stores)

    assert copied == 1
    assert _sparse_indices(stores.target.points[0]) == []
    assert stores.target.points[0].vector["dense"] == [0.1, 0.2]  # type: ignore[index]


async def test_empty_source_returns_zero_and_never_writes_to_the_target():
    stores = _stores([])

    copied = await _copy(stores)

    assert copied == 0
    assert stores.target.points == []
    assert stores.upserted_batch_sizes == []
