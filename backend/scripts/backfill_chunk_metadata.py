"""One-shot script to re-extract chunk metadata from text and sync to SQL + Qdrant.

Re-runs keyword and localisation extraction with the latest regex patterns,
then updates both PostgreSQL and Qdrant payloads.

Usage:
    cd backend && .venv/bin/python -m scripts.backfill_chunk_metadata
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend root to sys.path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.core.database import async_session
from app.core.qdrant import qdrant_client
from app.models.chunk import Chunk
from app.services.ingestion.chunking import _extract_keywords, _extract_localisation
from app.services.ingestion.embedding import COLLECTION_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SQL_BATCH_SIZE = 200
SQL_COMMIT_EVERY = 500


async def backfill() -> None:
    """Re-extract keywords + localisation from chunk text and update SQL + Qdrant."""
    updated = 0
    total = 0
    offset = 0

    async with async_session() as db:
        # Count total chunks
        count_result = await db.execute(select(Chunk.id))
        all_ids = count_result.scalars().all()
        total_chunks = len(all_ids)
        logger.info("Total chunks to process: %d", total_chunks)

        while True:
            stmt = (
                select(Chunk.id, Chunk.text, Chunk.qdrant_point_id)
                .order_by(Chunk.id)
                .offset(offset)
                .limit(SQL_BATCH_SIZE)
            )
            result = await db.execute(stmt)
            rows = result.all()

            if not rows:
                break

            for chunk_id, text, qdrant_point_id in rows:
                total += 1
                keywords = _extract_keywords(text)
                localisation = _extract_localisation(text)

                # Update SQL
                await db.execute(
                    update(Chunk)
                    .where(Chunk.id == chunk_id)
                    .values(
                        keywords=keywords or None,
                        localisation=localisation or None,
                    )
                )

                # Update Qdrant payload
                if qdrant_point_id:
                    try:
                        await qdrant_client.set_payload(
                            collection_name=COLLECTION_NAME,
                            payload={
                                "keywords": keywords,
                                "localisation": localisation,
                            },
                            points=[qdrant_point_id],
                        )
                    except Exception:
                        logger.warning("Failed to update Qdrant for point %s", qdrant_point_id)

                updated += 1

                if updated % SQL_COMMIT_EVERY == 0:
                    await db.commit()
                    logger.info("Progress: %d/%d chunks updated", updated, total_chunks)

            offset += SQL_BATCH_SIZE

        # Final commit
        await db.commit()

    logger.info(
        "Backfill complete: %d chunks updated out of %d total",
        updated,
        total,
    )


if __name__ == "__main__":
    asyncio.run(backfill())
