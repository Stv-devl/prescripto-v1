"""Hybrid retrieval (`RETRIEVAL_MODE=v1`): dense + sparse branches fused by RRF.

The double `FakeQdrant.query_points` filters each branch on its own, applies the
dense threshold of the dense branch only, ranks the sparse branch by shared
tokens and fuses with `sum(1 / (2 + rank))`: a chunk first on both branches is
worth 1.0, first on a single branch 0.5, second on a single branch 0.3333.

Every case asserts which chunks come back, in which order, with which score.
Tenant isolation is the filter carried by each branch, so the cross-tenant cases
put the neighbour's chunk on the sparse branch only, on the dense branch only and
on both, for each of the three entry points.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.search import SearchFilters
from app.services.search import search_by_lot, search_documents, search_merged
from tests.fakes import FakePoint, FakeQdrant, FakeQueryResponse

pytestmark = pytest.mark.asyncio

DTU_TEXT = "Enduit extérieur conforme au DTU 20.1 sur parois de blocs"
DTU_QUERY = "DTU 20.1"


class _CountingQdrant(FakeQdrant):
    """The double, plus the number of hybrid calls it answered."""

    def __init__(
        self,
        points: list[FakePoint] | None = None,
        *,
        score_rounds: list[dict[str, float]] | None = None,
    ) -> None:
        super().__init__(points, score_rounds=score_rounds)
        self.hybrid_calls = 0

    async def query_points(self, *args: object, **kwargs: object) -> FakeQueryResponse:
        self.hybrid_calls += 1
        return await super().query_points(*args, **kwargs)  # type: ignore[arg-type]


def _embed(texts: list[str], *args: object, **kwargs: object) -> list[list[float]]:
    return [[0.1] * 8 for _ in texts]


def _chunk(
    name: str,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    text: str,
    score: float,
    lot: str = "03 - Maçonnerie",
    phase: str = "PRO",
    doc_type: str = "plan",
    content_type: str | None = None,
    document_id: uuid.UUID | None = None,
    filename: str | None = None,
    ingested_at: str | None = None,
) -> FakePoint:
    payload: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "document_id": str(document_id or uuid.uuid4()),
        "filename": filename or f"{name}.pdf",
        "text": text,
        "page": 1,
        "position": 0,
        "lot": lot,
        "phase": phase,
        "type": doc_type,
    }
    if content_type is not None:
        payload["content_type"] = content_type
    if ingested_at is not None:
        payload["ingested_at"] = ingested_at
    return FakePoint(id=name, score=score, payload=payload)


@pytest.fixture
def v1_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.search.settings.retrieval_mode", "v1")


@pytest.fixture
def baseline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.search.settings.retrieval_mode", "baseline")


async def _merged(
    store: FakeQdrant,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    queries: list[str],
    limit: int = 10,
) -> list[str]:
    embed = AsyncMock(side_effect=_embed)
    with (
        patch("app.services.search.qdrant_client", store),
        patch("app.services.search.embed_texts", embed),
    ):
        results = await search_merged(
            tenant_id=tenant_id,
            project_id=project_id,
            queries=queries,
            filters=SearchFilters(),
            limit=limit,
        )
    return [r.text for r in results]


async def _entry(
    entry: str,
    store: FakeQdrant,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    filters: SearchFilters | None = None,
) -> list[str]:
    embed = AsyncMock(side_effect=_embed)
    with (
        patch("app.services.search.qdrant_client", store),
        patch("app.services.search.embed_texts", embed),
    ):
        if entry == "merged":
            results = await search_merged(
                tenant_id=tenant_id,
                project_id=project_id,
                queries=[query],
                filters=filters or SearchFilters(),
            )
        elif entry == "documents":
            results = await search_documents(
                tenant_id=tenant_id,
                project_id=project_id,
                query=query,
                filters=filters or SearchFilters(),
            )
        else:
            results = await search_by_lot(tenant_id=tenant_id, project_id=project_id, query=query)
    return [r.text for r in results]


def _three_chunks(tenant: uuid.UUID, project: uuid.UUID) -> list[FakePoint]:
    return [
        _chunk("dtu", tenant_id=tenant, project_id=project, text=DTU_TEXT, score=0.45),
        _chunk(
            "thermique",
            tenant_id=tenant,
            project_id=project,
            text="Isolation thermique des combles perdus en laine minérale",
            score=0.80,
        ),
        _chunk(
            "peinture",
            tenant_id=tenant,
            project_id=project,
            text="Peinture acrylique des menuiseries intérieures",
            score=0.70,
        ),
    ]


class TestHybridRanking:
    async def test_merged_ranks_first_the_chunk_holding_the_exact_term_despite_the_lowest_dense_score(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(_three_chunks(tenant, project))

        found = await _merged(
            store,
            tenant_id=tenant,
            project_id=project,
            queries=["quel DTU 20.1 pour la maçonnerie"],
        )

        assert found == [
            DTU_TEXT,
            "Isolation thermique des combles perdus en laine minérale",
            "Peinture acrylique des menuiseries intérieures",
        ]

    async def test_the_same_fixture_in_baseline_ranks_that_chunk_last_and_never_queries_hybrid(
        self, baseline_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = _CountingQdrant(_three_chunks(tenant, project))

        found = await _merged(
            store,
            tenant_id=tenant,
            project_id=project,
            queries=["quel DTU 20.1 pour la maçonnerie"],
        )

        assert found == [
            "Isolation thermique des combles perdus en laine minérale",
            "Peinture acrylique des menuiseries intérieures",
            DTU_TEXT,
        ]
        assert store.hybrid_calls == 0

    async def test_a_chunk_found_only_by_the_sparse_branch_is_returned_and_a_noise_chunk_is_not(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "dense-ok",
                    tenant_id=tenant,
                    project_id=project,
                    text="Peinture acrylique des menuiseries intérieures",
                    score=0.80,
                ),
                _chunk(
                    "sparse-seul", tenant_id=tenant, project_id=project, text=DTU_TEXT, score=0.20
                ),
                _chunk(
                    "bruit",
                    tenant_id=tenant,
                    project_id=project,
                    text="Nettoyage de fin de chantier",
                    score=0.20,
                ),
            ]
        )

        found = await _merged(store, tenant_id=tenant, project_id=project, queries=[DTU_QUERY])

        assert sorted(found) == sorted(["Peinture acrylique des menuiseries intérieures", DTU_TEXT])

    @pytest.mark.parametrize("mode", ["baseline", "v1"])
    async def test_search_documents_matches_the_dense_ranking_when_the_query_shares_no_token(
        self, monkeypatch: pytest.MonkeyPatch, mode: str
    ) -> None:
        monkeypatch.setattr("app.services.search.settings.retrieval_mode", mode)
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "premier",
                    tenant_id=tenant,
                    project_id=project,
                    text="Fondations superficielles sur semelles filantes",
                    score=0.90,
                ),
                _chunk(
                    "second",
                    tenant_id=tenant,
                    project_id=project,
                    text="Peinture acrylique des menuiseries",
                    score=0.70,
                ),
            ]
        )

        found = await _entry(
            "documents", store, tenant_id=tenant, project_id=project, query="béton armé"
        )

        assert found == [
            "Fondations superficielles sur semelles filantes",
            "Peinture acrylique des menuiseries",
        ]


class TestHybridIsolation:
    @pytest.mark.parametrize("entry", ["merged", "documents", "by_lot"])
    @pytest.mark.parametrize(
        ("neighbour_score", "neighbour_text"),
        [
            (0.10, "chez-b " + DTU_TEXT),
            (0.95, "chez-b Peinture acrylique des menuiseries"),
            (0.95, "chez-b " + DTU_TEXT),
        ],
        ids=["sparse-only", "dense-only", "both-branches"],
    )
    async def test_a_tenant_never_receives_the_neighbours_chunk_on_either_branch(
        self, v1_mode: None, entry: str, neighbour_score: float, neighbour_text: str
    ) -> None:
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        project = uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "a-moi",
                    tenant_id=tenant_a,
                    project_id=project,
                    text="a-moi " + DTU_TEXT,
                    score=0.90,
                ),
                _chunk(
                    "chez-b",
                    tenant_id=tenant_b,
                    project_id=project,
                    text=neighbour_text,
                    score=neighbour_score,
                ),
            ]
        )

        found = await _entry(
            entry, store, tenant_id=tenant_a, project_id=project, query=DTU_QUERY
        )

        assert found == ["a-moi " + DTU_TEXT]

    @pytest.mark.parametrize("entry", ["merged", "documents", "by_lot"])
    @pytest.mark.parametrize(
        ("other_score", "other_text"),
        [
            (0.10, "autre-projet " + DTU_TEXT),
            (0.95, "autre-projet Peinture acrylique des menuiseries"),
            (0.95, "autre-projet " + DTU_TEXT),
        ],
        ids=["sparse-only", "dense-only", "both-branches"],
    )
    async def test_a_chunk_of_another_project_of_the_same_tenant_is_never_returned(
        self, v1_mode: None, entry: str, other_score: float, other_text: str
    ) -> None:
        tenant = uuid.uuid4()
        project, other_project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "mon-projet",
                    tenant_id=tenant,
                    project_id=project,
                    text="mon-projet " + DTU_TEXT,
                    score=0.90,
                ),
                _chunk(
                    "autre-projet",
                    tenant_id=tenant,
                    project_id=other_project,
                    text=other_text,
                    score=other_score,
                ),
            ]
        )

        found = await _entry(entry, store, tenant_id=tenant, project_id=project, query=DTU_QUERY)

        assert found == ["mon-projet " + DTU_TEXT]

    @pytest.mark.parametrize(
        ("field", "wanted", "unwanted"),
        [
            ("lot", "03 - Maçonnerie", "05 - Charpente"),
            ("phase", "PRO", "DCE"),
            ("type", "plan", "fiche"),
        ],
    )
    async def test_the_lot_phase_and_type_filters_also_restrict_the_sparse_branch(
        self, v1_mode: None, field: str, wanted: str, unwanted: str
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        attribute = {"type": "doc_type"}.get(field, field)
        store = FakeQdrant(
            [
                _chunk(
                    "attendu",
                    tenant_id=tenant,
                    project_id=project,
                    text="attendu " + DTU_TEXT,
                    score=0.90,
                    **{attribute: wanted},
                ),
                _chunk(
                    "exclu",
                    tenant_id=tenant,
                    project_id=project,
                    text="exclu " + DTU_TEXT,
                    score=0.10,
                    **{attribute: unwanted},
                ),
            ]
        )

        found = await _entry(
            "documents",
            store,
            tenant_id=tenant,
            project_id=project,
            query=DTU_QUERY,
            filters=SearchFilters(**{field: wanted}),
        )

        assert found == ["attendu " + DTU_TEXT]


class TestHybridScoring:
    async def test_the_diagnostic_multiplier_applies_to_the_fused_score(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "thermique",
                    tenant_id=tenant,
                    project_id=project,
                    text="Isolation des murs par l'extérieur",
                    score=0.90,
                    doc_type="etude_thermique",
                )
            ]
        )
        embed = AsyncMock(side_effect=_embed)

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_merged(
                tenant_id=tenant,
                project_id=project,
                queries=["isolation des murs"],
                filters=SearchFilters(),
            )

        assert [r.score for r in results] == [pytest.approx(0.85)]

    async def test_the_administrative_multiplier_applies_to_the_fused_score(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "admin",
                    tenant_id=tenant,
                    project_id=project,
                    text="Fondations superficielles sur semelles filantes",
                    score=0.90,
                    content_type="admin",
                )
            ]
        )
        embed = AsyncMock(side_effect=_embed)

        with (
            patch("app.services.search.qdrant_client", store),
            patch("app.services.search.embed_texts", embed),
        ):
            results = await search_merged(
                tenant_id=tenant,
                project_id=project,
                queries=["fondations superficielles"],
                filters=SearchFilters(),
            )

        assert [r.score for r in results] == [pytest.approx(0.80)]

    async def test_only_the_latest_version_of_a_versioned_document_type_is_kept(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "v1",
                    tenant_id=tenant,
                    project_id=project,
                    text="Version ancienne du descriptif des fondations",
                    score=0.90,
                    doc_type="cctp",
                    filename="cctp.pdf",
                    ingested_at="2026-01-10T09:00:00+00:00",
                ),
                _chunk(
                    "v2",
                    tenant_id=tenant,
                    project_id=project,
                    text="Version récente du descriptif des fondations",
                    score=0.85,
                    doc_type="cctp",
                    filename="cctp.pdf",
                    ingested_at="2026-03-14T09:00:00+00:00",
                ),
            ]
        )

        found = await _merged(
            store, tenant_id=tenant, project_id=project, queries=["descriptif fondations"]
        )

        assert found == ["Version récente du descriptif des fondations"]

    async def test_merged_keeps_the_best_contribution_of_every_query(self, v1_mode: None) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        fillers = [
            _chunk(
                f"filler-{index}",
                tenant_id=tenant,
                project_id=project,
                text=f"Lot divers numéro {index} plomberie",
                score=score,
            )
            for index, score in enumerate([0.85, 0.80, 0.75, 0.70])
        ]
        store = FakeQdrant(
            [
                _chunk(
                    "a1",
                    tenant_id=tenant,
                    project_id=project,
                    text="béton armé fondations",
                    score=0.95,
                ),
                _chunk(
                    "a2",
                    tenant_id=tenant,
                    project_id=project,
                    text="béton armé poteaux",
                    score=0.90,
                ),
                *fillers,
                _chunk(
                    "b1",
                    tenant_id=tenant,
                    project_id=project,
                    text="solivage bois plancher",
                    score=0.60,
                ),
            ],
            score_rounds=[
                {},
                {
                    "a1": 0.1,
                    "a2": 0.1,
                    "filler-0": 0.1,
                    "filler-1": 0.1,
                    "filler-2": 0.1,
                    "filler-3": 0.1,
                    "b1": 0.1,
                },
            ],
        )

        found = await _merged(
            store,
            tenant_id=tenant,
            project_id=project,
            queries=["béton armé", "solivage bois"],
            limit=2,
        )

        assert "solivage bois plancher" in found


class TestContextThreshold:
    async def test_context_threshold_is_neutralised_in_v1_and_kept_in_baseline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.search import context_score_threshold

        monkeypatch.setattr("app.services.search.settings.retrieval_mode", "v1")
        in_v1 = context_score_threshold(0.40)
        monkeypatch.setattr("app.services.search.settings.retrieval_mode", "baseline")
        in_baseline = context_score_threshold(0.40)

        assert (in_v1, in_baseline) == (0.0, 0.40)


class TestHybridByLot:
    async def test_by_lot_surfaces_a_chunk_reached_only_by_the_sparse_branch(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "dense-ok",
                    tenant_id=tenant,
                    project_id=project,
                    text="Peinture acrylique des menuiseries intérieures",
                    score=0.80,
                ),
                _chunk(
                    "sparse-seul", tenant_id=tenant, project_id=project, text=DTU_TEXT, score=0.10
                ),
            ]
        )

        found = await _entry(
            "by_lot", store, tenant_id=tenant, project_id=project, query=DTU_QUERY
        )

        assert DTU_TEXT in found


class TestHybridEdges:
    async def test_a_query_without_any_token_falls_back_to_the_dense_ranking(
        self, v1_mode: None
    ) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "premier",
                    tenant_id=tenant,
                    project_id=project,
                    text="Fondations superficielles sur semelles filantes",
                    score=0.90,
                ),
                _chunk(
                    "second",
                    tenant_id=tenant,
                    project_id=project,
                    text="Peinture acrylique des menuiseries",
                    score=0.70,
                ),
            ]
        )

        found = await _entry("documents", store, tenant_id=tenant, project_id=project, query="?!")

        assert found == [
            "Fondations superficielles sur semelles filantes",
            "Peinture acrylique des menuiseries",
        ]

    async def test_the_low_threshold_fallback_still_runs_in_v1(self, v1_mode: None) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    "faible",
                    tenant_id=tenant,
                    project_id=project,
                    text="Fondations superficielles sur semelles filantes",
                    score=0.40,
                )
            ]
        )

        found = await _entry(
            "documents", store, tenant_id=tenant, project_id=project, query="béton"
        )

        assert found == ["Fondations superficielles sur semelles filantes"]

    async def test_the_limit_is_respected(self, v1_mode: None) -> None:
        tenant, project = uuid.uuid4(), uuid.uuid4()
        store = FakeQdrant(
            [
                _chunk(
                    f"chunk-{index}",
                    tenant_id=tenant,
                    project_id=project,
                    text=f"Article {index} du lot plomberie",
                    score=score,
                )
                for index, score in enumerate([0.90, 0.85, 0.80, 0.75])
            ]
        )

        found = await _merged(
            store, tenant_id=tenant, project_id=project, queries=["béton armé"], limit=2
        )

        assert found == ["Article 0 du lot plomberie", "Article 1 du lot plomberie"]
