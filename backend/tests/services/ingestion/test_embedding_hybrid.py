"""`ensure_collection` creates the collection matching the retrieval mode.

In `v1` the collection carries a named dense vector and a sparse IDF vector;
in `baseline` it is created exactly as before. The recorded creation arguments
are the only observable trace of what was created.
"""

from unittest.mock import patch

from qdrant_client.models import Distance, Modifier, SparseVectorParams, VectorParams

from app.services.ingestion.embedding import ensure_collection
from tests.fakes import FakeCollection, FakeCollections, FakeQdrant

EXPECTED_INDEXES = [
    "tenant_id",
    "project_id",
    "type",
    "lot",
    "phase",
    "content_type",
    "document_id",
    "filename",
]


class RecordingQdrant(FakeQdrant):
    """FakeQdrant reporting chosen collections and recording each creation."""

    def __init__(self, existing: list[str] | None = None) -> None:
        super().__init__()
        self.existing = list(existing or [])
        self.created: list[tuple[str, object, object]] = []

    async def get_collections(self) -> FakeCollections:
        return FakeCollections(collections=[FakeCollection(name=n) for n in self.existing])

    async def create_collection(
        self,
        *,
        collection_name: str,
        vectors_config: object,
        sparse_vectors_config: object = None,
    ) -> None:
        self.created.append((collection_name, vectors_config, sparse_vectors_config))


class TestEnsureCollectionHybrid:
    async def test_v1_creates_documents_v1_with_named_dense_and_sparse_idf_vectors(self) -> None:
        store = RecordingQdrant()

        with (
            patch("app.services.ingestion.embedding.qdrant_client", store),
            patch("app.services.ingestion.embedding.settings.retrieval_mode", "v1"),
            patch("app.services.ingestion.embedding.COLLECTION_NAME", "documents_v1"),
        ):
            await ensure_collection()

        assert len(store.created) == 1
        name, vectors, sparse = store.created[0]
        assert name == "documents_v1"
        assert isinstance(vectors, dict)
        assert list(vectors) == ["dense"]
        dense = vectors["dense"]
        assert isinstance(dense, VectorParams)
        assert dense.size == 1024
        assert dense.distance == Distance.COSINE
        assert isinstance(sparse, dict)
        assert list(sparse) == ["sparse"]
        sparse_params = sparse["sparse"]
        assert isinstance(sparse_params, SparseVectorParams)
        assert sparse_params.modifier == Modifier.IDF

    async def test_v1_creates_the_same_eight_payload_indexes(self) -> None:
        store = RecordingQdrant()

        with (
            patch("app.services.ingestion.embedding.qdrant_client", store),
            patch("app.services.ingestion.embedding.settings.retrieval_mode", "v1"),
            patch("app.services.ingestion.embedding.COLLECTION_NAME", "documents_v1"),
        ):
            await ensure_collection()

        assert store.created_indexes == EXPECTED_INDEXES

    async def test_baseline_creates_the_collection_with_an_unnamed_vector_and_no_sparse(
        self,
    ) -> None:
        store = RecordingQdrant()

        with (
            patch("app.services.ingestion.embedding.qdrant_client", store),
            patch("app.services.ingestion.embedding.settings.retrieval_mode", "baseline"),
            patch("app.services.ingestion.embedding.COLLECTION_NAME", "documents"),
        ):
            await ensure_collection()

        assert len(store.created) == 1
        name, vectors, sparse = store.created[0]
        assert name == "documents"
        assert isinstance(vectors, VectorParams)
        assert vectors.size == 1024
        assert vectors.distance == Distance.COSINE
        assert sparse is None

    async def test_an_existing_collection_is_not_recreated_but_indexes_are_still_ensured(
        self,
    ) -> None:
        store = RecordingQdrant(existing=["documents_v1"])

        with (
            patch("app.services.ingestion.embedding.qdrant_client", store),
            patch("app.services.ingestion.embedding.settings.retrieval_mode", "v1"),
            patch("app.services.ingestion.embedding.COLLECTION_NAME", "documents_v1"),
        ):
            await ensure_collection()

        assert store.created == []
        assert store.created_indexes == EXPECTED_INDEXES
