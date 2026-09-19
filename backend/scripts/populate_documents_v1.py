"""One-shot: build `documents_v1` (dense + BM25 sparse) from the `documents` collection.

Run from backend/ with RETRIEVAL_MODE=v1 so `ensure_collection` creates the
hybrid schema:

    RETRIEVAL_MODE=v1 PYTHONPATH=. uv run python scripts/populate_documents_v1.py

The dense vectors and payloads are copied as they are — no Mistral call, no
re-parsing — and `documents` is only read. Replaying it upserts the same ids.
"""

import asyncio
import logging
from urllib.parse import urlparse

from app.core.config import settings
from app.core.qdrant import qdrant_client
from app.services.ingestion.embedding import (
    COLLECTION_NAME,
    collection_name_for,
    ensure_collection,
)
from app.services.ingestion.hybrid_copy import copy_points_to_hybrid

logger = logging.getLogger(__name__)

SOURCE_COLLECTION = collection_name_for("baseline")


async def populate() -> None:
    if settings.retrieval_mode != "v1":
        raise SystemExit("Run with RETRIEVAL_MODE=v1 so the hybrid schema is created.")
    print(f"target qdrant host={urlparse(settings.qdrant_url).hostname}")
    await ensure_collection()
    copied = await copy_points_to_hybrid(source=SOURCE_COLLECTION, target=COLLECTION_NAME)
    source_count = (await qdrant_client.count(collection_name=SOURCE_COLLECTION)).count
    target_count = (await qdrant_client.count(collection_name=COLLECTION_NAME)).count
    logger.info(
        "Copied %d points: %s=%d, %s=%d",
        copied,
        SOURCE_COLLECTION,
        source_count,
        COLLECTION_NAME,
        target_count,
    )
    print(f"copied={copied} {SOURCE_COLLECTION}={source_count} {COLLECTION_NAME}={target_count}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(populate())
