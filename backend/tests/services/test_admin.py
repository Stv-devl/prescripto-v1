"""Cross-tenant isolation tests for the chunk admin service.

`admin.py` is the one module where a tenant's data is not just read but
mutated (`update_chunk`, `split_chunk`, `merge_chunks`, `delete_chunk`), so a
missing `tenant_id` check there is not a read leak but a write into — or a
deletion of — another tenant's corpus. `_get_chunk_with_tenant_check` is the
single choke point for the four mutations; the read-only functions each carry
their own filter, silent (empty result) or raising, depending on whether the
identifier they take is scoped by `project_id` alone or points at one row.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.project import Project
from app.models.tenant import Tenant
from app.services import admin as admin_service
from app.services import project as project_service
from tests.fakes import FakePoint, FakeQdrant

pytestmark = pytest.mark.asyncio


async def _project_of(db: AsyncSession, tenant: Tenant, name: str = "Chantier") -> Project:
    return await project_service.create_project(db, tenant.id, name=name, phase="PRO")


async def _document_of(
    db: AsyncSession, project: Project, filename: str = "doc.pdf", **kw: object
) -> Document:
    document = Document(project_id=project.id, filename=filename, status="ready", **kw)
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def _chunk_of(
    db: AsyncSession,
    document: Document,
    text: str,
    *,
    position: int = 0,
    qdrant_point_id: str = "",
    **kw: object,
) -> Chunk:
    chunk = Chunk(
        document_id=document.id,
        text=text,
        position=position,
        qdrant_point_id=qdrant_point_id,
        **kw,
    )
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def _chunk_exists(db: AsyncSession, chunk_id: uuid.UUID) -> bool:
    """A fresh query, never the session's identity map — a raw `update()`/`delete()`
    statement does not refresh objects already loaded in this session."""
    result = await db.execute(select(Chunk.id).where(Chunk.id == chunk_id))
    return result.scalar_one_or_none() is not None


async def _chunk_text(db: AsyncSession, chunk_id: uuid.UUID) -> str:
    result = await db.execute(select(Chunk.text).where(Chunk.id == chunk_id))
    return result.scalar_one()


async def _chunk_keywords(db: AsyncSession, chunk_id: uuid.UUID) -> list[str] | None:
    result = await db.execute(select(Chunk.keywords).where(Chunk.id == chunk_id))
    return result.scalar_one()


async def _chunk_count(db: AsyncSession, document_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    )
    return result.scalar_one()


class TestChunkMutationIsolation:
    """The scenario measured by the 2026-09-03 review: `_get_chunk_with_tenant_check`
    is the single choke point for every mutation on a chunk."""

    async def test_update_chunk_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "texte original")

        with pytest.raises(NotFoundError):
            await admin_service.update_chunk(
                db, tenant_a.id, project.id, chunk.id, "texte falsifié"
            )

        assert await _chunk_text(db, chunk.id) == "texte original"

    async def test_split_chunk_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "texte assez long pour être scindé")

        with pytest.raises(NotFoundError):
            await admin_service.split_chunk(db, tenant_a.id, project.id, chunk.id, 5)

        assert await _chunk_count(db, document.id) == 1

    async def test_merge_chunks_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        first = await _chunk_of(db, document, "premier morceau", position=0)
        second = await _chunk_of(db, document, "second morceau", position=1)

        with pytest.raises(NotFoundError):
            await admin_service.merge_chunks(db, tenant_a.id, project.id, first.id, second.id)

        assert await _chunk_exists(db, first.id)
        assert await _chunk_exists(db, second.id)
        assert await _chunk_count(db, document.id) == 2

    async def test_delete_chunk_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "à préserver")

        with pytest.raises(NotFoundError):
            await admin_service.delete_chunk(db, tenant_a.id, project.id, chunk.id)

        assert await _chunk_exists(db, chunk.id)


class TestAdminReadIsolation:
    """One function at a time: some raise on a scoped identifier, others filter
    a `project_id` silently and return an empty result — never an exception."""

    async def test_get_chunk_detail_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "détail confidentiel")

        with pytest.raises(NotFoundError):
            await admin_service.get_chunk_detail(db, tenant_a.id, project.id, chunk.id)

    async def test_list_document_chunks_of_another_tenants_document_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        with pytest.raises(NotFoundError):
            await admin_service.list_document_chunks(db, tenant_a.id, project.id, document.id)

    async def test_find_similar_chunks_of_another_tenants_chunk_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "chunk source confidentiel")

        with pytest.raises(NotFoundError):
            await admin_service.find_similar_chunks(db, tenant_a.id, project.id, chunk.id)

    async def test_detect_duplicates_of_another_tenants_document_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        with pytest.raises(NotFoundError):
            await admin_service.detect_duplicates(db, tenant_a.id, project.id, document.id)

    async def test_find_similar_chunks_meta_lookup_is_scoped_to_tenant(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Qdrant's own search is already scoped to `tenant_id` + `project_id`
        (2026-09-06 review), so a hit can only ever carry tenant A's payload.
        But the SQL step that turns a hit's point id into chunk metadata
        matched on `qdrant_point_id` alone, with no `Project` join and no
        `tenant_id` filter — and `qdrant_point_id` carries no uniqueness
        constraint in Postgres (`app/models/chunk.py`). A hit id that
        collides with another tenant's stored `qdrant_point_id` must not
        surface that tenant's chunk metadata.
        """
        project_a = await _project_of(db, tenant_a, "Chantier A")
        document_a = await _document_of(db, project_a, "a.pdf")
        source = await _chunk_of(db, document_a, "chunk source", qdrant_point_id="point-a")

        project_b = await _project_of(db, tenant_b, "Secret de B")
        document_b = await _document_of(db, project_b, "b.pdf")
        theirs = await _chunk_of(
            db, document_b, "secret de tenant B", qdrant_point_id="colliding-id"
        )

        qdrant = AsyncMock()
        qdrant.retrieve.return_value = [AsyncMock(id="point-a", vector=[0.1, 0.2])]
        qdrant.search.return_value = [AsyncMock(id="colliding-id", score=0.9)]

        with patch("app.services.admin.qdrant_client", qdrant):
            results = await admin_service.find_similar_chunks(
                db, tenant_a.id, project_a.id, source.id
            )

        assert results == []
        assert theirs.id not in [r.chunk_id for r in results]

    async def test_rechunk_document_of_another_tenant_is_refused(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        with pytest.raises(NotFoundError):
            await admin_service.rechunk_document(db, tenant_a.id, project.id, document.id)

        assert await _chunk_count(db, document.id) == 1

    async def test_list_chunks_of_another_tenants_project_returns_empty(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        result = await admin_service.list_chunks(db, tenant_a.id, project.id)

        assert result.items == []
        assert result.total == 0

    async def test_get_chunk_stats_of_another_tenants_project_returns_zero(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        result = await admin_service.get_chunk_stats(db, tenant_a.id, project.id)

        assert result.total_chunks == 0
        assert result.by_document == []

    async def test_sync_check_of_another_tenants_project_returns_empty(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(db, document, "chunk confidentiel")

        result = await admin_service.sync_check(db, tenant_a.id, project.id)

        assert result.documents.items == []
        assert result.total_sql == 0

    async def test_get_section_tree_of_another_tenants_project_returns_empty(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        await _chunk_of(
            db,
            document,
            "chunk confidentiel",
            parent_sections=["Lot 01", "Gros oeuvre"],
        )

        result = await admin_service.get_section_tree(db, tenant_a.id, project.id)

        assert result == []

    async def test_batch_enrich_keywords_of_another_tenants_project_updates_nothing(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_b, "Secret de B")
        document = await _document_of(db, project)
        chunk = await _chunk_of(db, document, "chunk sans mots-clés")

        result = await admin_service.batch_enrich_keywords(db, tenant_a.id, project.id)

        assert result.updated_count == 0
        assert await _chunk_keywords(db, chunk.id) is None

    async def test_playground_search_never_returns_another_tenants_chunk(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """`point-b` has a real SQL `Chunk` row under `tenant_b`'s own project —
        unlike a phantom Qdrant hit with no SQL counterpart, this cannot be
        excluded by construction, so the case actually exercises the isolation
        the function is meant to enforce (removing `Project.tenant_id ==
        tenant_id` from the SQL re-check at `admin.py` would let it through).
        """
        project_b = await _project_of(db, tenant_b, "Secret de B")
        document_b = await _document_of(db, project_b)
        theirs = await _chunk_of(db, document_b, "secret de tenant B", qdrant_point_id="point-b")
        store = FakeQdrant(
            [
                FakePoint(
                    id="point-b",
                    payload={"tenant_id": str(tenant_b.id), "project_id": str(project_b.id)},
                ),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            result = await admin_service.playground_search(
                db, tenant_a.id, project_b.id, query="béton"
            )

        assert result.results == []
        assert theirs.id not in [r.chunk_id for r in result.results]

    async def test_semantic_search_chunks_never_returns_another_tenants_chunk(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """Same reasoning as `playground_search` above: `point-b` needs a real
        SQL `Chunk` row under `tenant_b`'s own project so the case actually
        exercises the SQL re-check, not the absence of a matching row.
        """
        project_b = await _project_of(db, tenant_b, "Secret de B")
        document_b = await _document_of(db, project_b)
        theirs = await _chunk_of(db, document_b, "secret de tenant B", qdrant_point_id="point-b")
        store = FakeQdrant(
            [
                FakePoint(
                    id="point-b",
                    payload={"tenant_id": str(tenant_b.id), "project_id": str(project_b.id)},
                ),
            ]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            result = await admin_service.semantic_search_chunks(
                db, tenant_a.id, project_b.id, query="béton"
            )

        assert result.items == []
        assert theirs.id not in [item.id for item in result.items]


class TestMutationPayload:
    """What a mutation that SUCCEEDS writes to the index.

    The cross-tenant cases above all raise before reaching the payload builder,
    which is exactly why the two constructions were free to drift.
    """

    async def test_update_chunk_writes_the_keys_search_reads(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        chunk = await _chunk_of(db, document, "texte d'origine", qdrant_point_id="p-1")
        store = FakeQdrant()
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.update_chunk(
                db, tenant_a.id, project.id, chunk.id, "texte revise"
            )

        written = store.points[0].payload
        assert written["type"] == "CCTP"
        assert "doc_type" not in written
        assert written["heading_prefix"] == ""
        assert written["char_count"] == len("texte revise")
        assert written["tenant_id"] == str(tenant_a.id)

    async def test_a_split_keeps_the_chunks_own_lot_over_the_documents(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The divergence a shared builder alone cannot close.

        `split_chunk` creates its two rows without `lot`, so the payload falls
        back to the document's however good the builder is.
        """
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        chunk = await _chunk_of(
            db, document, "premiere partie et seconde partie", qdrant_point_id="p-1",
            lot="LOT 02 - Cloisons", heading_prefix="2.3",
        )
        store = FakeQdrant()
        embed = AsyncMock(return_value=[[0.1] * 8, [0.2] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.split_chunk(db, tenant_a.id, project.id, chunk.id, 17)

        assert [p.payload["lot"] for p in store.points] == [
            "LOT 02 - Cloisons",
            "LOT 02 - Cloisons",
        ]
        assert [p.payload["heading_prefix"] for p in store.points] == ["2.3", "2.3"]

    async def test_a_merge_keeps_the_chunks_own_lot_over_the_documents(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        first = await _chunk_of(
            db, document, "premiere partie", position=0, qdrant_point_id="p-1",
            lot="LOT 02 - Cloisons", heading_prefix="2.3",
        )
        second = await _chunk_of(
            db, document, "seconde partie", position=1, qdrant_point_id="p-2",
            lot="LOT 02 - Cloisons", heading_prefix="2.3",
        )
        store = FakeQdrant()
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.merge_chunks(db, tenant_a.id, project.id, first.id, second.id)

        assert store.points[0].payload["lot"] == "LOT 02 - Cloisons"
        assert store.points[0].payload["heading_prefix"] == "2.3"

    async def test_a_successful_mutation_leaves_another_tenants_point_alone(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """The isolation case the refusals above cannot reach: a write that runs."""
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP")
        chunk = await _chunk_of(db, document, "texte d'origine", qdrant_point_id="p-1")
        store = FakeQdrant(
            [FakePoint(id="chez-b", payload={"tenant_id": str(tenant_b.id)})]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.update_chunk(
                db, tenant_a.id, project.id, chunk.id, "texte revise"
            )

        assert "chez-b" in [p.id for p in store.points]
        assert all(
            p.payload["tenant_id"] == str(tenant_b.id)
            for p in store.points
            if p.id == "chez-b"
        )

    async def test_a_split_writes_the_callers_tenant_and_spares_another_tenants_point(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        """The isolation case on a mutation that DELETES before it writes.

        `update_chunk` never calls `qdrant_client.delete`, so an isolation case
        written on it cannot see a deletion that removes too much. `split_chunk`
        deletes the old point first, which is where over-deletion would show.
        """
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        chunk = await _chunk_of(
            db, document, "premiere partie et seconde partie", qdrant_point_id="p-1"
        )
        store = FakeQdrant(
            [FakePoint(id="chez-b", payload={"tenant_id": str(tenant_b.id)})]
        )
        embed = AsyncMock(return_value=[[0.1] * 8, [0.2] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.split_chunk(db, tenant_a.id, project.id, chunk.id, 17)

        assert "chez-b" in [p.id for p in store.points]
        written = [p for p in store.points if p.id != "chez-b"]
        assert len(written) == 2
        assert all(p.payload["tenant_id"] == str(tenant_a.id) for p in written)

    async def test_a_merge_writes_the_callers_tenant(
        self, db: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        first = await _chunk_of(db, document, "premiere", position=0, qdrant_point_id="p-1")
        second = await _chunk_of(db, document, "seconde", position=1, qdrant_point_id="p-2")
        store = FakeQdrant(
            [FakePoint(id="chez-b", payload={"tenant_id": str(tenant_b.id)})]
        )
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.merge_chunks(db, tenant_a.id, project.id, first.id, second.id)

        assert "chez-b" in [p.id for p in store.points]
        written = [p for p in store.points if p.id != "chez-b"]
        assert len(written) == 1
        assert written[0].payload["tenant_id"] == str(tenant_a.id)

    async def test_a_split_carries_the_type_and_phase_onto_the_rows_it_creates(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The two inherited columns no payload assertion can see.

        `phase` and `type` reach the payload from the Document, so dropping them
        from the `Chunk` constructors leaves every payload case green — while
        `search.py` filters a re-edited chunk on exactly those two columns.
        """
        project = await _project_of(db, tenant_a)
        document = await _document_of(db, project, "cctp.pdf", type="CCTP", lot="LOT 01")
        chunk = await _chunk_of(
            db, document, "premiere partie et seconde partie", qdrant_point_id="p-1",
            type="CCTP", phase="PRO", lot="LOT 02 - Cloisons",
        )
        store = FakeQdrant()
        embed = AsyncMock(return_value=[[0.1] * 8, [0.2] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.split_chunk(db, tenant_a.id, project.id, chunk.id, 17)

        rows = (
            (await db.execute(select(Chunk).where(Chunk.document_id == document.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert all(r.type == "CCTP" for r in rows)
        assert all(r.phase == "PRO" for r in rows)
        assert all(r.lot == "LOT 02 - Cloisons" for r in rows)

    async def test_a_re_edited_chunk_carries_the_documents_ingestion_time(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """Not `now()`: the value its untouched siblings already carry.

        `_dedup_by_latest_version` keeps the document with the highest
        `ingested_at` per versioned type. A fresh stamp here would lift a
        superseded document above the newer one and suppress the newer one's
        chunks — the opposite of what the dedup is for.
        """
        from datetime import UTC, datetime

        ingested = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)
        project = await _project_of(db, tenant_a)
        document = await _document_of(
            db, project, "cctp.pdf", type="etude_sol", ingested_at=ingested
        )
        chunk = await _chunk_of(db, document, "texte d'origine", qdrant_point_id="p-1")
        store = FakeQdrant()
        embed = AsyncMock(return_value=[[0.1] * 8])

        with (
            patch("app.services.admin.qdrant_client", store),
            patch("app.services.admin.embed_texts", embed),
        ):
            await admin_service.update_chunk(
                db, tenant_a.id, project.id, chunk.id, "texte revise"
            )

        await db.refresh(document)
        assert store.points[0].payload["ingested_at"] == document.ingested_at.isoformat()


class TestBatchEnrichGroupsItsVectorWrites:
    async def test_the_chunks_of_one_batch_travel_in_a_single_round_trip(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """One request per chunk is what made this exceed the 120 s client
        deadline on a large project. Both shapes leave the same payloads in
        store, so the number of round trips is the only observable difference —
        sending them one at a time gives [1, 1, 1] instead of [3]."""
        project = await _project_of(db, tenant_a, "Projet de A")
        document = await _document_of(db, project)
        text = "Isolation thermique laine de roche 200 mm au niveau R+1"
        for index in range(3):
            await _chunk_of(
                db, document, text, position=index, qdrant_point_id=f"p-{index}"
            )
        store = FakeQdrant()

        with patch("app.services.admin.qdrant_client", store):
            result = await admin_service.batch_enrich_keywords(
                db, tenant_a.id, project.id
            )

        assert result.updated_count == 3
        assert store.payload_batches == [3]


class TestRechunkRefusesASecondRunWhileOneIsInFlight:
    async def test_the_second_call_is_refused_rather_than_racing_the_first(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """The panel stays open past the client deadline and the refetch shows
        the old list, because the first run has only flushed — so it reads as if
        nothing happened and the operator clicks again. Nothing else stops the
        second run: the chunk delete and the vector purge are not one
        transaction, so it wipes what the first has written and both pipelines
        then upsert the same document.
        """
        import asyncio

        from app.core.exceptions import ConflictError

        project = await _project_of(db, tenant_a, "Projet de A")
        document = await _document_of(db, project)
        released = asyncio.Event()

        async def _hold(*_args: object, **_kwargs: object) -> None:
            await released.wait()

        with patch("app.services.admin.delete_document_vectors", _hold):
            first = asyncio.create_task(
                admin_service.rechunk_document(db, tenant_a.id, project.id, document.id)
            )
            await asyncio.sleep(0)

            with pytest.raises(ConflictError):
                await admin_service.rechunk_document(
                    db, tenant_a.id, project.id, document.id
                )

            released.set()
            with pytest.raises(NotFoundError):
                await first


class TestRepairingPayloadsWrittenBeforeTheUnifiedBuilder:
    async def test_a_legacy_point_is_rebuilt_and_stops_looking_legacy(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """Legacy points carry `doc_type` and no `type`, so search reads no type
        on them and they fall out of every type-filtered query. The rebuild has
        to overwrite rather than merge: a merge leaves `doc_type` behind and the
        point stays legacy for ever, which also breaks running the repair twice.
        """
        from tests.fakes import FakePoint, FakeQdrant

        project = await _project_of(db, tenant_a, "Projet de A")
        document = await _document_of(db, project, type="CCTP")
        await _chunk_of(db, document, "texte du chunk", qdrant_point_id="p-legacy")
        store = FakeQdrant(
            [
                FakePoint(
                    id="p-legacy",
                    payload={
                        "tenant_id": str(tenant_a.id),
                        "project_id": str(project.id),
                        "doc_type": "CCTP",
                    },
                )
            ]
        )

        with patch("app.services.admin.qdrant_client", store):
            result = await admin_service.repair_legacy_payloads(
                db, tenant_a.id, project.id
            )

        assert result.repaired_count == 1
        assert store.points[0].payload["type"] == "CCTP"
        assert "doc_type" not in store.points[0].payload

    async def test_a_point_whose_chunk_is_gone_is_counted_and_left_alone(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """Deleting it would be a second destructive act inside a repair."""
        from tests.fakes import FakePoint, FakeQdrant

        project = await _project_of(db, tenant_a, "Projet de A")
        store = FakeQdrant(
            [
                FakePoint(
                    id="p-orpheline",
                    payload={
                        "tenant_id": str(tenant_a.id),
                        "project_id": str(project.id),
                        "doc_type": "CCTP",
                    },
                )
            ]
        )

        with patch("app.services.admin.qdrant_client", store):
            result = await admin_service.repair_legacy_payloads(
                db, tenant_a.id, project.id
            )

        assert (result.repaired_count, result.orphan_count) == (0, 1)
        assert store.points[0].payload["doc_type"] == "CCTP"

    async def test_a_payload_already_unified_is_not_touched(
        self, db: AsyncSession, tenant_a: Tenant
    ) -> None:
        """Which is also what makes a second run of the repair do nothing."""
        from tests.fakes import FakePoint, FakeQdrant

        project = await _project_of(db, tenant_a, "Projet de A")
        document = await _document_of(db, project, type="CCTP")
        await _chunk_of(db, document, "texte", qdrant_point_id="p-moderne")
        store = FakeQdrant(
            [
                FakePoint(
                    id="p-moderne",
                    payload={
                        "tenant_id": str(tenant_a.id),
                        "project_id": str(project.id),
                        "type": "CCTP",
                        "text": "tel quel",
                    },
                )
            ]
        )

        with patch("app.services.admin.qdrant_client", store):
            result = await admin_service.repair_legacy_payloads(
                db, tenant_a.id, project.id
            )

        assert result.repaired_count == 0
        assert store.points[0].payload["text"] == "tel quel"
