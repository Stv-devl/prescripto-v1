"""Pins `FakeQdrant.query_points` to what the real Qdrant 1.19.1 answered.

The hybrid search tests run against this double, so its fusion arithmetic has to
be the server's. The expected values below were recorded on 2026-09-19 from a
scratch collection on the local server: with two tenants and three points, the
tenant A query returned point 1 at 1.0 (first on both branches, 1/2 + 1/2) and
point 3 at 0.3333 (second on the dense branch only, 1/3). A max-normalised
fusion would have given 0.375, which is what this test would catch.
"""

import pytest
from qdrant_client.models import FieldCondition, Filter, Fusion, FusionQuery, MatchValue, Prefetch

from app.services.sparse import query_sparse_vector
from tests.fakes import FakePoint, FakeQdrant

pytestmark = pytest.mark.asyncio


def _tenant(tenant_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))])


async def test_fused_scores_match_the_recorded_server_result() -> None:
    store = FakeQdrant(
        [
            FakePoint(id="1", score=1.0, payload={"tenant_id": "A", "text": "dtu"}),
            FakePoint(id="2", score=0.9, payload={"tenant_id": "B", "text": "dtu"}),
            FakePoint(id="3", score=0.0, payload={"tenant_id": "A", "text": "zzz"}),
        ]
    )
    sparse_query = query_sparse_vector("dtu")
    assert sparse_query is not None
    branches = [
        Prefetch(query=[1.0], using="dense", filter=_tenant("A"), limit=10),
        Prefetch(query=sparse_query, using="sparse", filter=_tenant("A"), limit=10),
    ]

    response = await store.query_points(
        collection_name="documents_v1",
        prefetch=branches,
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=_tenant("A"),
        limit=10,
    )

    assert [(p.id, round(p.score, 4)) for p in response.points] == [("1", 1.0), ("3", 0.3333)]
