"""Unit tests for _search_compat (backend/app/core/qdrant.py).

`AsyncQdrantClient.search()` was removed in qdrant-client 1.10+; this shim is
the only thing standing between the nine `.search(query_vector=...)` call
sites in `services/` and the real `query_points(query=...)` API. None of the
existing `services/` tests exercise it — they patch `qdrant_client` wholesale
with `tests/fakes.py`'s own hand-written `.search()`.
"""

from unittest.mock import AsyncMock

import pytest
from qdrant_client.models import Filter

from app.core.qdrant import _search_compat


class _FakeResponse:
    def __init__(self, points: list[object]) -> None:
        self.points = points


class TestSearchCompat:
    async def test_translates_query_vector_to_query(self) -> None:
        client = AsyncMock()
        client.query_points.return_value = _FakeResponse([])

        await _search_compat(
            client,
            collection_name="documents",
            query_vector=[0.1, 0.2],
            limit=5,
        )

        client.query_points.assert_awaited_once_with(
            collection_name="documents",
            query=[0.1, 0.2],
            query_filter=None,
            limit=5,
            score_threshold=None,
        )

    async def test_forwards_query_filter_and_score_threshold(self) -> None:
        client = AsyncMock()
        client.query_points.return_value = _FakeResponse([])
        query_filter = Filter(must=[])

        await _search_compat(
            client,
            collection_name="documents",
            query_vector=[0.1],
            query_filter=query_filter,
            limit=3,
            score_threshold=0.5,
        )

        client.query_points.assert_awaited_once_with(
            collection_name="documents",
            query=[0.1],
            query_filter=query_filter,
            limit=3,
            score_threshold=0.5,
        )

    async def test_returns_the_unwrapped_points_list(self) -> None:
        client = AsyncMock()
        hits = [object(), object()]
        client.query_points.return_value = _FakeResponse(hits)

        result = await _search_compat(client, collection_name="documents", query_vector=[0.1])

        assert result is hits

    async def test_an_unknown_keyword_raises_instead_of_being_swallowed(self) -> None:
        client = AsyncMock()

        try:
            await _search_compat(
                client,
                collection_name="documents",
                query_vector=[0.1],
                offset=10,  # not a parameter _search_compat declares
            )
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError for an unrecognized keyword")


class TestSearchCompatNamedVectors:
    """`documents_v1` holds named vectors, so the dense search must say which one."""

    async def test_targets_the_dense_vector_in_v1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.qdrant.settings.retrieval_mode", "v1")
        client = AsyncMock()
        client.query_points.return_value = _FakeResponse([])

        await _search_compat(client, collection_name="documents_v1", query_vector=[0.1], limit=5)

        client.query_points.assert_awaited_once_with(
            collection_name="documents_v1",
            query=[0.1],
            query_filter=None,
            limit=5,
            score_threshold=None,
            using="dense",
        )

    async def test_names_no_vector_in_baseline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.qdrant.settings.retrieval_mode", "baseline")
        client = AsyncMock()
        client.query_points.return_value = _FakeResponse([])

        await _search_compat(client, collection_name="documents", query_vector=[0.1], limit=5)

        client.query_points.assert_awaited_once_with(
            collection_name="documents",
            query=[0.1],
            query_filter=None,
            limit=5,
            score_threshold=None,
        )
