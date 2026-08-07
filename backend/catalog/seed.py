"""
One-off catalog seeding script.
Run manually from the project root:
    python -m backend.catalog.seed

Upserts placeholder battery/inverter/equipment catalog data into MongoDB.
Idempotent — re-running updates existing seed entries in place (matched
on _id) rather than duplicating them.

Uses model_dump(by_alias=True) so Pydantic's `id` field (aliased to `_id`)
is written correctly as MongoDB's native _id key.
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from backend.catalog.seed_data import (
    BATTERY_CATALOG_SEED,
    EQUIPMENT_CATALOG_SEED,
    INVERTER_CATALOG_SEED,
)
from backend.db.client import (
    close_mongo_connection,
    connect_to_mongo,
    get_battery_catalog_collection,
    get_equipment_catalog_collection,
    get_inverter_catalog_collection,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend.catalog.seed")


async def _upsert_all(collection, models: list, label: str) -> None:
    upserted, refreshed = 0, 0
    for model in models:
        doc = model.model_dump(by_alias=True, exclude_none=True)
        result = await collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        if result.upserted_id is not None:
            upserted += 1
        else:
            refreshed += 1
    logger.info("%s: %d inserted, %d already existed and were refreshed.", label, upserted, refreshed)


async def run_seed() -> None:
    await connect_to_mongo()
    try:
        await _upsert_all(get_battery_catalog_collection(), BATTERY_CATALOG_SEED, "battery_catalog")
        await _upsert_all(get_inverter_catalog_collection(), INVERTER_CATALOG_SEED, "inverter_catalog")
        await _upsert_all(get_equipment_catalog_collection(), EQUIPMENT_CATALOG_SEED, "equipment_catalog")
        logger.info("Catalog seeding complete.")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
    asyncio.run(run_seed())