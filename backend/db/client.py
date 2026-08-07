"""
MongoDB Connection Layer
Establishes a single, reused AsyncMongoClient instance and exposes named
collection accessors per architecture.md's Storage Model.

This module ONLY handles connection lifecycle and collection access.
No query, CRUD, or matching logic belongs here (see Feature 11/12/14).
"""

import logging
import os
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger("backend.db")

# ---------------------------------------------------------------------------
# Module-level client/database handles.
# Created once via connect_to_mongo() during FastAPI's lifespan startup,
# reused for the lifetime of the process — never re-created per-request.
# ---------------------------------------------------------------------------
_client: Optional[AsyncMongoClient] = None
_database: Optional[Database] = None


class DatabaseConfigError(RuntimeError):
    """Raised when required database environment variables are missing."""


def _get_required_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise DatabaseConfigError(
            f"Missing required environment variable '{var_name}'. "
            f"Check your .env file (see .env.example) or your deployment's "
            f"environment configuration."
        )
    return value


async def connect_to_mongo() -> None:
    """
    Initializes the AsyncMongoClient and verifies connectivity with a ping.
    Called once during FastAPI's lifespan startup. Raises loudly on any
    failure — a bad URI or unreachable cluster must fail fast at boot,
    not silently on the first request that happens to touch the DB.
    """
    global _client, _database

    mongodb_uri = _get_required_env("MONGODB_URI")
    database_name = _get_required_env("DATABASE_NAME")

    logger.info("Connecting to MongoDB Atlas (database='%s')...", database_name)

    _client = AsyncMongoClient(mongodb_uri)
    _database = _client[database_name]

    try:
        await _client.admin.command("ping")
    except PyMongoError as exc:
        logger.error("MongoDB connection failed: %s", exc)
        # Reset state so a partially-initialized client isn't left dangling.
        _client = None
        _database = None
        raise

    logger.info("MongoDB connection established successfully.")


async def close_mongo_connection() -> None:
    """Closes the MongoDB client cleanly. Called on FastAPI shutdown."""
    global _client, _database

    if _client is not None:
        await _client.close()
        logger.info("MongoDB connection closed.")

    _client = None
    _database = None


def get_database() -> Database:
    """
    Returns the active database handle. Raises if called before
    connect_to_mongo() has run (e.g., outside the app's lifespan) —
    callers should never receive a silent None.
    """
    if _database is None:
        raise RuntimeError(
            "Database has not been initialized. "
            "Ensure connect_to_mongo() has run (via FastAPI's lifespan) "
            "before accessing collections."
        )
    return _database


# ---------------------------------------------------------------------------
# Named collection accessors — per architecture.md's Storage Model.
# These only return a handle to the collection; no query/CRUD logic here.
# ---------------------------------------------------------------------------

def get_projects_collection():
    return get_database()["projects"]


def get_equipment_catalog_collection():
    return get_database()["equipment_catalog"]


def get_battery_catalog_collection():
    return get_database()["battery_catalog"]


def get_inverter_catalog_collection():
    return get_database()["inverter_catalog"]