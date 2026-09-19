"""Copy a Qdrant collection into its hybrid twin (dense reused, sparse added).

A whole-collection copy: it deliberately does not filter by `tenant_id`, it
preserves each point's own payload. It never writes to or deletes from the
source, and replaying it upserts the same ids, so nothing is duplicated.
"""

from app.core.qdrant import qdrant_client
from app.services.sparse import to_hybrid_point


async def copy_points_to_hybrid(*, source: str, target: str, batch_size: int = 100) -> int:
    """Copy every point of `source` into `target`, returning how many were copied."""
    copied = 0
    offset = None
    while True:
        records, offset = await qdrant_client.scroll(
            collection_name=source,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        points = [
            to_hybrid_point(record.id, record.vector, record.payload or {}) for record in records
        ]
        if points:
            await qdrant_client.upsert(collection_name=target, points=points)
            copied += len(points)
        if offset is None:
            return copied
