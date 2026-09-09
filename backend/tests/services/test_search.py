"""Search, scoped to its tenant and its project.

`search.py` was the least covered module of the backend at 8 %, and it carries
ten Qdrant call sites. Qdrant has no row-level security: the `must` conditions
written by hand in this module are the only thing separating two customers'
corpora.

The double really applies the filters, so these cases assert **which chunks come
back**. The fixture types are `plan` and `fiche` on purpose: they sit outside
`_VERSIONED_TYPES` and `_DIAGNOSTIC_TYPES`, so no case measures the version
dedup or the diagnostic penalty when it means to measure a filter.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.search import SearchFilters
from app.services.search import search_documents
from tests.fakes import FakePoint, FakeQdrant

pytestmark = pytest.mark.asyncio


def _chunk(
    name: str,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    lot: str = "03 - Maçonnerie",
    phase: str = "PRO",
    doc_type: str = "plan",
    score: float = 0.9,
) -> FakePoint:
    return FakePoint(
        id=name,
        score=score,
        payload={
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
            "document_id": str(uuid.uuid4()),
            "filename": f"{name}.pdf",
            "text": name,
            "page": 1,
            "position": 0,
            "lot": lot,
            "phase": phase,
            "type": doc_type,
        },
    )


async def _search(store: FakeQdrant, **kwargs: object) -> list[str]:
    """Run a search against the double and return the chunk texts it yielded."""
    embed = AsyncMock(return_value=[[0.1] * 8])
    with (
        patch("app.services.search.qdrant_client", store),
        patch("app.services.search.embed_texts", embed),
    ):
        results = await search_documents(**kwargs)
    return [r.text for r in results]


class TestSearchTenantScope:
    async def test_returns_only_chunks_of_the_calling_tenant(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("a-moi", tenant_id=tenant_a, project_id=project),
                _chunk("au-voisin", tenant_id=tenant_b, project_id=project),
            ]
        )

        found = await _search(
            store,
            tenant_id=tenant_a,
            project_id=project,
            query="béton",
            filters=SearchFilters(),
        )

        assert found == ["a-moi"]

    async def test_returns_only_chunks_of_the_requested_project(self) -> None:
        tenant = uuid.uuid4()
        wanted, other = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("bon-projet", tenant_id=tenant, project_id=wanted),
                _chunk("autre-projet", tenant_id=tenant, project_id=other),
            ]
        )

        found = await _search(
            store,
            tenant_id=tenant,
            project_id=wanted,
            query="béton",
            filters=SearchFilters(),
        )

        assert found == ["bon-projet"]

    async def test_an_unfiltered_search_still_carries_both_conditions(self) -> None:
        """No optional filter must not mean no isolation."""
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project, other_project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("le-mien", tenant_id=tenant_a, project_id=project),
                _chunk("autre-tenant", tenant_id=tenant_b, project_id=project),
                _chunk("autre-projet", tenant_id=tenant_a, project_id=other_project),
            ]
        )

        found = await _search(
            store,
            tenant_id=tenant_a,
            project_id=project,
            query="béton",
            filters=SearchFilters(),
        )

        assert found == ["le-mien"]


    async def test_the_low_threshold_fallback_does_not_widen_the_tenant_scope(self) -> None:
        """`search_documents` queries Qdrant a second time at 0.35 when the first
        pass finds nothing — a whole call site of its own, with its own filter.

        Without this case that second call is never executed by the suite, and a
        tenant condition dropped from it alone would go unnoticed.
        """
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("faible", tenant_id=tenant_a, project_id=project, score=0.40),
                _chunk("chez-b", tenant_id=tenant_b, project_id=project, score=0.95),
            ]
        )

        found = await _search(
            store,
            tenant_id=tenant_a,
            project_id=project,
            query="béton",
            filters=SearchFilters(),
        )

        assert found == ["faible"]


class TestSearchOptionalFilters:
    @pytest.mark.parametrize(
        ("field", "wanted", "unwanted"),
        [
            ("lot", "03 - Maçonnerie", "05 - Charpente"),
            ("phase", "PRO", "DCE"),
            ("type", "plan", "fiche"),
        ],
    )
    async def test_an_optional_filter_narrows_and_never_widens_the_tenant_scope(
        self, field: str, wanted: str, unwanted: str
    ) -> None:
        """A key copied from another field would return the wrong chunk and fail.

        The third point is the one that matters: it carries the wanted value but
        belongs to another tenant. A filter that replaced the tenant condition
        rather than adding to it would let it through.
        """
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        attribute = {"type": "doc_type"}.get(field, field)
        store = FakeQdrant(
            [
                _chunk("attendu", tenant_id=tenant_a, project_id=project, **{attribute: wanted}),
                _chunk("exclu", tenant_id=tenant_a, project_id=project, **{attribute: unwanted}),
                _chunk("chez-b", tenant_id=tenant_b, project_id=project, **{attribute: wanted}),
            ]
        )

        found = await _search(
            store,
            tenant_id=tenant_a,
            project_id=project,
            query="béton",
            filters=SearchFilters(**{field: wanted}),
        )

        assert found == ["attendu"]


from app.services.search import (  # noqa: E402 — appended after freeze, see 05-testing.md
    count_document_points,
    retrieve_point_payload,
    scroll_document_point_ids,
    search_by_lot,
    search_diverse,
    search_merged,
)


class TestSearchOtherEntryPointsTenantScope:
    """`search_documents` is not the only Qdrant call site — `search_diverse`,
    `search_by_lot` and `search_merged` build their own filters, and
    `retrieve_point_payload`/`count_document_points`/`scroll_document_point_ids`
    check tenant scope on IDs Qdrant's own API cannot filter by.
    """

    async def test_search_diverse_never_returns_another_tenants_chunk(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("a-moi", tenant_id=tenant_a, project_id=project),
                _chunk("au-voisin", tenant_id=tenant_b, project_id=project),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_diverse(tenant_id=tenant_a, project_id=project, query="béton")

        assert [r.text for r in results] == ["a-moi"]

    async def test_search_by_lot_never_returns_another_tenants_chunk(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("a-moi", tenant_id=tenant_a, project_id=project, lot="03 - Maçonnerie"),
                _chunk("au-voisin", tenant_id=tenant_b, project_id=project, lot="03 - Maçonnerie"),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_by_lot(tenant_id=tenant_a, project_id=project, query="béton")

        assert [r.text for r in results] == ["a-moi"]

    async def test_search_merged_never_returns_another_tenants_chunk(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("a-moi", tenant_id=tenant_a, project_id=project),
                _chunk("au-voisin", tenant_id=tenant_b, project_id=project),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_merged(
                tenant_id=tenant_a,
                project_id=project,
                queries=["béton"],
                filters=SearchFilters(),
            )

        assert [r.text for r in results] == ["a-moi"]

    async def test_retrieve_point_payload_returns_none_for_another_tenants_point(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant([_chunk("au-voisin", tenant_id=tenant_b, project_id=project)])

        with patch("app.services.search.qdrant_client", store):
            payload = await retrieve_point_payload("au-voisin", tenant_id=tenant_a)

        assert payload is None

    async def test_count_document_points_of_another_tenant_returns_zero(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        document_id = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "au-voisin",
                    tenant_id=tenant_b,
                    project_id=project,
                )
            ]
        )
        store.points[0].payload["document_id"] = str(document_id)

        with patch("app.services.search.qdrant_client", store):
            count = await count_document_points(document_id, tenant_id=tenant_a)

        assert count == 0

    async def test_scroll_document_point_ids_of_another_tenant_returns_empty_set(self) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        document_id = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "au-voisin",
                    tenant_id=tenant_b,
                    project_id=project,
                )
            ]
        )
        store.points[0].payload["document_id"] = str(document_id)

        with patch("app.services.search.qdrant_client", store):
            point_ids = await scroll_document_point_ids(document_id, tenant_id=tenant_a)

        assert point_ids == set()


class TestTheDiversityGuaranteeOnTheFallbackPath:
    async def test_each_query_still_contributes_its_best_result(self) -> None:
        """`search_merged` promises every query contributes at least its own best
        unique result. The lowered-threshold retry used to fill only the global
        pool, so on that path the promise quietly became "the top scores win" —
        and one query could take every slot, at the very moment the search was
        hard enough to need a retry.

        Scores stay under the 0.40 default so the first pass finds nothing and
        the retry runs. `b-best` is the second query's best and the third score
        overall: it is in the answer only if the guarantee holds there too.
        """
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk("a-best", tenant_id=tenant, project_id=project),
                _chunk("a-second", tenant_id=tenant, project_id=project),
                _chunk("b-best", tenant_id=tenant, project_id=project),
            ],
            score_rounds=[
                {"a-best": 0.30, "a-second": 0.30, "b-best": 0.30},
                {"a-best": 0.30, "a-second": 0.30, "b-best": 0.30},
                {"a-best": 0.39, "a-second": 0.38, "b-best": 0.30},
                {"b-best": 0.37, "a-best": 0.36, "a-second": 0.30},
            ],
        )
        embed = AsyncMock(return_value=[[0.1] * 8, [0.2] * 8])

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_merged(
                tenant_id=tenant,
                project_id=project,
                queries=["béton armé", "solivage bois"],
                filters=SearchFilters(),
                limit=2,
            )

        assert "b-best" in [r.text for r in results]
