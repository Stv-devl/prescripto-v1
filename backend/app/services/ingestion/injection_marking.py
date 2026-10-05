"""Mark Qdrant points whose text looks like a prompt injection.

The flag is a payload key set only on suspect points (absence means clean), written
with a set-payload operation: vectors and every other key stay untouched. The backfill
scrolls a whole collection — a declared maintenance exception to per-tenant filtering:
it reads text and writes this one key on points addressed by id, nothing crosses tenants.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from qdrant_client.models import SetPayload, SetPayloadOperation

from app.core.qdrant import qdrant_client
from app.services.injection_guard import INJECTION_FLAG as INJECTION_FLAG
from app.services.injection_guard import looks_like_injection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReport:
    scanned: int
    flagged: int


async def _flag(point_ids: list[str], collection: str) -> None:
    if not point_ids:
        return
    await qdrant_client.batch_update_points(
        collection_name=collection,
        update_operations=[
            SetPayloadOperation(
                set_payload=SetPayload(payload={INJECTION_FLAG: True}, points=point_ids)
            )
        ],
    )
    for point_id in point_ids:
        logger.warning("[INJECTION] Point %s flagged as a suspect prompt injection", point_id)


async def mark_suspect_points(
    texts: Sequence[str], point_ids: Sequence[str], *, collection: str
) -> list[str]:
    """Flag the points whose text is suspect; returns their ids."""
    if len(texts) != len(point_ids):
        raise ValueError(f"{len(texts)} texts for {len(point_ids)} point ids")
    suspects = [
        point_id
        for text, point_id in zip(texts, point_ids, strict=True)
        if looks_like_injection(text)
    ]
    await _flag(suspects, collection)
    return suspects


async def backfill_injection_flags(*, collection: str, batch_size: int = 256) -> BackfillReport:
    """Flag every existing suspect point of `collection`, without re-embedding anything."""
    scanned = 0
    flagged = 0
    offset: int | str | None = None
    while True:
        points, offset = await qdrant_client.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        scanned += len(points)
        suspects = [
            str(point.id)
            for point in points
            if looks_like_injection(str((point.payload or {}).get("text", "")))
        ]
        await _flag(suspects, collection)
        flagged += len(suspects)
        if offset is None:
            break
    return BackfillReport(scanned=scanned, flagged=flagged)
