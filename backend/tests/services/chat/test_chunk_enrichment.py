"""Tenant isolation of the two Qdrant scrolls of `enrich_with_dpgf_quantities`.

Nothing but this code enforces isolation: Qdrant accepts an unfiltered scroll
without a word and returns the neighbour's chunks (`06-database.md`). The filter
sent to the store is therefore the only observable trace of the barrier, which is
the exception `05-testing.md` allows to assert on the call itself.

The function is called directly, never through the endpoint: `chat_stream`
rejects a foreign tenant in its first statement, so an endpoint test would be
green before and after the fix and would prove nothing.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from qdrant_client.models import FieldCondition

from app.models.tenant import Tenant
from app.services.chat.chunk_enrichment import enrich_with_dpgf_quantities

QUESTION = "carrelage grès cérame"
DPGF_FILENAME = "DPGF_carrelage.xlsx"


def _record(payload: dict[str, str]) -> SimpleNamespace:
    """A Qdrant record exposing `.payload`, as the client returns it."""
    return SimpleNamespace(id=str(uuid.uuid4()), payload=payload)


def _discovery_records() -> list[SimpleNamespace]:
    """First scroll: DPGF file discovery, which reads `filename` and `lot`."""
    return [_record({"filename": DPGF_FILENAME, "lot": "07"})]


def _chunk_records(project_id: uuid.UUID) -> list[SimpleNamespace]:
    """Second scroll: the DPGF chunks read back for that filename."""
    return [
        _record(
            {
                "text": "Lot 07 carrelage grès cérame 60x60 collé : 120 m2",
                "document_id": str(uuid.uuid4()),
                "project_id": str(project_id),
            }
        )
    ]


def _qdrant_double(project_id: uuid.UUID) -> MagicMock:
    """A Qdrant double whose two scrolls return two different payload sets."""
    client = MagicMock()
    client.scroll = AsyncMock(
        side_effect=[
            (_discovery_records(), None),
            (_chunk_records(project_id), None),
        ]
    )
    return client


def _field_conditions(scroll: AsyncMock, index: int) -> list[FieldCondition]:
    """The field conditions of the `must` clause of the index-th scroll."""
    assert scroll.call_count > index, (
        f"scroll was called {scroll.call_count} time(s), so scroll #{index} never happened "
        "— fixture problem, not an isolation failure"
    )
    must = scroll.call_args_list[index].kwargs["scroll_filter"].must
    return [c for c in must if isinstance(c, FieldCondition)]


async def test_dpgf_discovery_scopes_the_scroll_to_the_calling_tenant(
    tenant_a: Tenant, tenant_b: Tenant
) -> None:
    """Called as B, the discovery scroll must ask Qdrant for B's chunks only.

    The double answers whatever the filter says, so what is asserted is the
    filter itself — the only observable trace of the barrier. tenant_a is here
    to make the assertion mean something: carrying the key is not enough, the
    value has to be the caller's.
    """
    project_id = uuid.uuid4()
    qdrant = _qdrant_double(project_id)

    with patch("app.services.chat.chunk_enrichment.qdrant_client", qdrant):
        await enrich_with_dpgf_quantities(
            tenant_id=tenant_b.id,
            project_id=project_id,
            search_query="carrelage",
            question=QUESTION,
            search_results=[],
        )

    conditions = _field_conditions(qdrant.scroll, 0)
    scoped = [c for c in conditions if c.key == "tenant_id"]
    assert len(scoped) == 1, f"discovery scroll carries no tenant_id condition: {conditions}"
    assert scoped[0].match.value == str(tenant_b.id)
    assert scoped[0].match.value != str(tenant_a.id)


async def test_dpgf_chunk_read_scopes_the_scroll_to_the_calling_tenant(
    tenant_a: Tenant, tenant_b: Tenant
) -> None:
    """Reading the chunks back by filename must carry the caller's tenant too."""
    project_id = uuid.uuid4()
    qdrant = _qdrant_double(project_id)

    with patch("app.services.chat.chunk_enrichment.qdrant_client", qdrant):
        await enrich_with_dpgf_quantities(
            tenant_id=tenant_b.id,
            project_id=project_id,
            search_query="carrelage",
            question=QUESTION,
            search_results=[],
        )

    conditions = _field_conditions(qdrant.scroll, 1)
    scoped = [c for c in conditions if c.key == "tenant_id"]
    assert len(scoped) == 1, f"chunk-read scroll carries no tenant_id condition: {conditions}"
    assert scoped[0].match.value == str(tenant_b.id)
    assert scoped[0].match.value != str(tenant_a.id)


async def test_both_scrolls_keep_their_existing_conditions(tenant_a: Tenant) -> None:
    """The tenant filter is added to each scroll, it does not replace anything."""
    project_id = uuid.uuid4()
    qdrant = _qdrant_double(project_id)

    with patch("app.services.chat.chunk_enrichment.qdrant_client", qdrant):
        await enrich_with_dpgf_quantities(
            tenant_id=tenant_a.id,
            project_id=project_id,
            search_query="carrelage",
            question=QUESTION,
            search_results=[],
        )

    discovery = {c.key: c.match.value for c in _field_conditions(qdrant.scroll, 0)}
    assert str(discovery["project_id"]) == str(project_id)
    assert discovery["type"] == "DPGF"

    chunk_read = {c.key: c.match.value for c in _field_conditions(qdrant.scroll, 1)}
    assert str(chunk_read["project_id"]) == str(project_id)
    assert chunk_read["filename"] == DPGF_FILENAME


async def test_enrichment_returns_the_dpgf_chunks_of_the_calling_tenant(
    tenant_a: Tenant,
) -> None:
    """Nominal path: the caller owns the chunks, so their text comes back."""
    project_id = uuid.uuid4()
    chunk_text = "Carrelage grès cérame 60x60 collé au sol : 120 m2"
    chunks = [
        _record(
            {
                "text": chunk_text,
                "document_id": str(uuid.uuid4()),
                "project_id": str(project_id),
            }
        )
    ]
    qdrant = MagicMock()
    qdrant.scroll = AsyncMock(side_effect=[(_discovery_records(), None), (chunks, None)])

    with patch("app.services.chat.chunk_enrichment.qdrant_client", qdrant):
        results = await enrich_with_dpgf_quantities(
            tenant_id=tenant_a.id,
            project_id=project_id,
            search_query="carrelage",
            question=QUESTION,
            search_results=[],
        )

    assert [result.text for result in results] == [chunk_text]
