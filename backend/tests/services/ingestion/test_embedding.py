"""Vector deletion, scoped to its tenant.

`delete_document_vectors` carries a comment saying the tenant condition is not
redundant — "a delete without it would remove points on a document_id collision
or a mistaken id, across tenants, with no error". Nothing proved it until now.

The double really applies the filter, so these cases assert **which points
survive** rather than which arguments a mock received. On a store that has no
row-level security, that difference is the whole test: a double that ignores
filters would stay green with the condition deleted.
"""

import uuid
from unittest.mock import patch

import pytest

from app.services.ingestion.embedding import delete_document_vectors
from tests.fakes import FakePoint, FakeQdrant

pytestmark = pytest.mark.asyncio


def _point(name: str, tenant_id: uuid.UUID, document_id: uuid.UUID) -> FakePoint:
    return FakePoint(
        id=name,
        payload={
            "tenant_id": str(tenant_id),
            "document_id": str(document_id),
            "text": name,
        },
    )


class TestDeleteDocumentVectors:
    async def test_removes_the_points_of_the_given_document(self) -> None:
        tenant = uuid.uuid4()
        target = uuid.uuid4()
        other = uuid.uuid4()
        store = FakeQdrant(
            [
                _point("cible-1", tenant, target),
                _point("cible-2", tenant, target),
                _point("voisin", tenant, other),
            ]
        )

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await delete_document_vectors(target, tenant)

        assert [p.id for p in store.points] == ["voisin"]

    async def test_another_tenants_points_survive_the_same_document_id(self) -> None:
        """The scenario the module's own comment describes, and nothing proved."""
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        shared_document_id = uuid.uuid4()
        store = FakeQdrant(
            [
                _point("chez-a", tenant_a, shared_document_id),
                _point("chez-b", tenant_b, shared_document_id),
            ]
        )

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await delete_document_vectors(shared_document_id, tenant_a)

        assert [p.id for p in store.points] == ["chez-b"]

    async def test_a_document_with_no_points_deletes_without_raising(self) -> None:
        tenant = uuid.uuid4()
        store = FakeQdrant([_point("sans-rapport", tenant, uuid.uuid4())])

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await delete_document_vectors(uuid.uuid4(), tenant)

        assert [p.id for p in store.points] == ["sans-rapport"]


class TestIndexChunksPayload:
    """The shape `index_chunks` writes, pinned before it was extracted.

    Written before the payload construction moved to `qdrant_payload.py`, and
    unchanged after: that is what tells an extraction apart from a rewrite. If
    the shared builder receives one wrong argument, this case is what says so.
    """

    async def test_writes_the_payload_shape_the_search_layer_reads(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.ingestion import embedding as embedding_module
        from app.services.ingestion.chunking import TextChunk

        tenant = uuid.UUID("11111111-1111-1111-1111-111111111111")
        project = uuid.UUID("22222222-2222-2222-2222-222222222222")
        document = uuid.UUID("33333333-3333-3333-3333-333333333333")
        chunk = TextChunk(
            text="Doublage en plaque de platre.",
            page=3,
            position=7,
            parent_sections=["2. Second oeuvre"],
            section_title="2.3 Cloisons",
            heading_prefix="2.3",
            chunk_lot="LOT 02 - Cloisons",
            content_type="prescription",
            keywords=["doublage"],
            localisation=["R+1"],
            char_count=29,
        )
        store = FakeQdrant()

        async def _vectors(texts: list[str]) -> list[list[float]]:
            return [[0.1] * 8 for _ in texts]

        monkeypatch.setattr(embedding_module, "embed_texts", _vectors)

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await embedding_module.index_chunks(
                [chunk],
                tenant_id=tenant,
                project_id=project,
                document_id=document,
                doc_type="CCTP",
                lot="LOT 01 - Gros oeuvre",
                phase="PRO",
                filename="cctp.pdf",
                ingested_at=None,
            )

        assert store.points[0].payload == {
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "project_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "type": "CCTP",
            "lot": "LOT 02 - Cloisons",
            "phase": "PRO",
            "filename": "cctp.pdf",
            "page": 3,
            "position": 7,
            "text": "Doublage en plaque de platre.",
            "heading_prefix": "2.3",
            "section_title": "2.3 Cloisons",
            "parent_sections": ["2. Second oeuvre"],
            "content_type": "prescription",
            "keywords": ["doublage"],
            "char_count": 29,
            "localisation": ["R+1"],
        }


class TestEnsureCollectionPayloadIndexes:
    """`tenant_id` is the isolation filter on every Qdrant query (`06-database.md`);
    `project_id` rides alongside it in most of them (`search.py`, `admin.py`).
    Neither was indexed, so that filter paid a linear scan of the collection's
    payload. This is what proves `ensure_collection` fixes that, and does so
    without turning a routine app restart into a crash.
    """

    async def test_indexes_tenant_id_and_project_id(self) -> None:
        from app.services.ingestion.embedding import ensure_collection

        store = FakeQdrant()

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await ensure_collection()

        assert store.created_indexes == ["tenant_id", "project_id"]

    async def test_a_second_call_does_not_raise(self) -> None:
        """`ensure_collection` runs on every app startup: an index already
        created on a previous run must not make the next startup crash."""
        from app.services.ingestion.embedding import ensure_collection

        store = FakeQdrant()

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            await ensure_collection()
            await ensure_collection()

        assert store.created_indexes == ["tenant_id", "project_id"]

    async def test_a_genuinely_different_failure_propagates(self) -> None:
        """"Already exists" is not the only `UnexpectedResponse` Qdrant can
        answer here — an auth rejection, a malformed field name, the server
        unreachable are real failure modes with a different status and body.
        A startup that cannot build its indexes must fail loud, not silently
        continue serving an unindexed collection, so this must propagate."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        from app.services.ingestion.embedding import ensure_collection

        auth_failure = UnexpectedResponse(
            status_code=403,
            reason_phrase="Forbidden",
            content=b'{"status":{"error":"Invalid API key"}}',
            headers={},
        )
        store = FakeQdrant(payload_index_error=auth_failure)

        with patch("app.services.ingestion.embedding.qdrant_client", store):
            with pytest.raises(UnexpectedResponse):
                await ensure_collection()


class TestCollectionNameFor:
    """The sprint A/B switch (sprint/PLAN-SPRINT.md § 2): both modes stay runnable."""

    def test_baseline_maps_to_the_original_collection(self) -> None:
        from app.services.ingestion.embedding import collection_name_for

        assert collection_name_for("baseline") == "documents"

    def test_a_non_baseline_mode_gets_its_own_collection(self) -> None:
        from app.services.ingestion.embedding import collection_name_for

        assert collection_name_for("v1") == "documents_v1"
