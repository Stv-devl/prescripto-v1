"""Mark existing suspicious passages: uv run python -m scripts.backfill_injection_flags COLLECTION."""

import argparse
import asyncio

from app.services.ingestion.injection_marking import backfill_injection_flags


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark suspicious passages in one collection.")
    parser.add_argument("collection")
    args = parser.parse_args()
    print(asyncio.run(backfill_injection_flags(collection=args.collection)))


if __name__ == "__main__":
    main()
