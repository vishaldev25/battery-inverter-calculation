"""
Project Repository — CRUD + Version History
Pure data-access layer against the `projects` MongoDB collection.
Per architecture.md Invariant 1 / code-standards.md: no calculation logic,
no formula evaluation — this module only reads/writes documents.

Mirrors the boundary discipline of backend/catalog/matcher.py:
- never raises on "not found" — returns None, caller decides HTTP status.
- no side effects beyond MongoDB reads/writes.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId

from backend.db.client import get_projects_collection
from backend.projects.models import Project, VersionHistoryEntry

logger = logging.getLogger("backend.projects.repository")


def _to_object_id(project_id: str) -> Optional[ObjectId]:
    """
    Safely converts a string project_id to an ObjectId.
    Returns None on malformed input rather than raising — callers treat
    this the same as "not found" (a malformed id can never match a
    document), keeping the not-found contract consistent.
    """
    try:
        return ObjectId(project_id)
    except (InvalidId, TypeError):
        return None


def _doc_to_project(doc: Dict[str, Any]) -> Project:
    """Converts a raw MongoDB document (with ObjectId _id) into a Project model."""
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return Project(**doc)


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

async def create_project(project: Project) -> Project:
    """
    Inserts a new project. Ignores any client-supplied `id` — Mongo always
    generates the identity on create; a client-supplied id here would be a
    spoofing/collision risk with no legitimate use case in this unit.
    """
    now = datetime.utcnow()
    payload = project.model_dump(by_alias=True, exclude={"id"})
    payload["created_at"] = now
    payload["updated_at"] = now

    collection = get_projects_collection()
    result = await collection.insert_one(payload)

    created_doc = await collection.find_one({"_id": result.inserted_id})
    logger.info("Project created: id=%s name=%s", result.inserted_id, project.name)
    return _doc_to_project(created_doc)


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

async def get_project(project_id: str) -> Optional[Project]:
    """Fetch by id. Returns None if not found or id is malformed."""
    oid = _to_object_id(project_id)
    if oid is None:
        return None

    doc = await get_projects_collection().find_one({"_id": oid})
    if doc is None:
        logger.info("Project lookup: '%s' not found.", project_id)
        return None
    return _doc_to_project(doc)


# ---------------------------------------------------------------------------
# UPDATE — full replace (PUT)
# ---------------------------------------------------------------------------

async def replace_project(project_id: str, updated: Project) -> Optional[Project]:
    """
    Full-object replace of editable fields (name, description, loads,
    parameters). ALWAYS sets updated_at and appends a version_history
    entry — unconditional per Invariant 9, never skippable via a request flag.

    Does NOT allow the caller to overwrite last_calculation_result,
    is_favorite, or version_history directly through this path — those
    have their own dedicated write paths (save_calculation_result,
    set_favorite) so a PUT can never accidentally clobber them with stale
    frontend state.
    """
    oid = _to_object_id(project_id)
    if oid is None:
        return None

    collection = get_projects_collection()
    existing_doc = await collection.find_one({"_id": oid})
    if existing_doc is None:
        return None

    now = datetime.utcnow()
    version_entry = VersionHistoryEntry(
        edited_at=now,
        summary=_summarize_replace(existing_doc, updated),
    )

    update_fields = {
        "name": updated.name,
        "description": updated.description,
        "loads": [load.model_dump() for load in updated.loads],
        "parameters": updated.parameters.model_dump(),
        "updated_at": now,
    }

    result = await collection.find_one_and_update(
        {"_id": oid},
        {"$set": update_fields, "$push": {"version_history": version_entry.model_dump()}},
        return_document=True,
    )
    if result is None:
        return None
    logger.info("Project replaced: id=%s", project_id)
    return _doc_to_project(result)


def _summarize_replace(existing_doc: Dict[str, Any], updated: Project) -> str:
    """
    Best-effort human-readable diff summary for the version history entry.
    Kept intentionally simple (load count delta + autonomy/voltage change)
    rather than a full field-by-field diff — a full diff engine isn't
    scoped for this unit, and the spec doc explicitly leaves snapshot
    granularity as a deferred implementation choice.
    """
    old_load_count = len(existing_doc.get("loads", []))
    new_load_count = len(updated.loads)
    load_delta = new_load_count - old_load_count

    parts = []
    if load_delta != 0:
        sign = "+" if load_delta > 0 else ""
        parts.append(f"{sign}{load_delta} load(s) (now {new_load_count})")

    old_params = existing_doc.get("parameters", {})
    old_autonomy = old_params.get("days_of_autonomy")
    new_autonomy = updated.parameters.days_of_autonomy
    if old_autonomy is not None and old_autonomy != new_autonomy:
        parts.append(f"autonomy {old_autonomy} → {new_autonomy} days")

    old_voltage = old_params.get("system_dc_voltage")
    new_voltage = updated.parameters.system_dc_voltage
    if old_voltage is not None and old_voltage != new_voltage:
        parts.append(f"bank voltage {old_voltage}V → {new_voltage}V")

    if not parts:
        return "Project details updated"
    return "Updated: " + ", ".join(parts)


# ---------------------------------------------------------------------------
# UPDATE — single-field mutations (PATCH)
# ---------------------------------------------------------------------------

async def set_favorite(project_id: str, is_favorite: bool) -> Optional[Project]:
    """
    Single-field write. Deliberately does NOT touch updated_at or
    version_history — starring is a personal-organization action, not an
    edit to engineering content (see Feature 12 spec §3.3).
    """
    oid = _to_object_id(project_id)
    if oid is None:
        return None

    result = await get_projects_collection().find_one_and_update(
        {"_id": oid},
        {"$set": {"is_favorite": is_favorite}},
        return_document=True,
    )
    if result is None:
        return None
    return _doc_to_project(result)


async def set_status(project_id: str, status: str) -> Optional[Project]:
    """
    Single-field write, but DOES trigger updated_at + version_history —
    unlike favorite, a status change is a substantive state change worth
    capturing (Feature 12 spec §3.3).
    """
    oid = _to_object_id(project_id)
    if oid is None:
        return None

    collection = get_projects_collection()
    existing_doc = await collection.find_one({"_id": oid})
    if existing_doc is None:
        return None

    old_status = existing_doc.get("status")
    now = datetime.utcnow()
    version_entry = VersionHistoryEntry(
        edited_at=now,
        summary=f"Status changed: {old_status} → {status}",
    )

    result = await collection.find_one_and_update(
        {"_id": oid},
        {"$set": {"status": status, "updated_at": now}, "$push": {"version_history": version_entry.model_dump()}},
        return_document=True,
    )
    if result is None:
        return None
    logger.info("Project status changed: id=%s %s -> %s", project_id, old_status, status)
    return _doc_to_project(result)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

async def delete_project(project_id: str, confirm_name: str) -> bool:
    """
    Deletes only if confirm_name matches the stored project's name exactly
    (case-sensitive, no trimming) — server-side re-check even though the
    frontend also confirms, per code-standards.md's "never trust a
    frontend-only confirmation" rule.

    Returns False (never raises) if the project doesn't exist OR the name
    doesn't match — the router layer decides whether that's a 404 or 409.
    """
    oid = _to_object_id(project_id)
    if oid is None:
        return False

    collection = get_projects_collection()
    existing_doc = await collection.find_one({"_id": oid})
    if existing_doc is None:
        logger.info("Delete rejected: project '%s' not found.", project_id)
        return False
    if existing_doc.get("name") != confirm_name:
        logger.info(
            "Delete rejected: name mismatch for project '%s' (confirm_name did not match stored name).",
            project_id,
        )
        return False
    delete_result = await collection.delete_one({"_id": oid, "name": confirm_name})
    success = delete_result.deleted_count == 1
    if success:
        logger.info("Project deleted: id=%s", project_id)
    else:
        logger.info("Delete rejected: project '%s' changed during confirmation.", project_id)
    return success

# ---------------------------------------------------------------------------
# CALCULATION RESULT PERSISTENCE
# ---------------------------------------------------------------------------

async def save_calculation_result(project_id: str, result: Dict[str, Any]) -> Optional[Project]:
    """
    Writes last_calculation_result, updates updated_at, appends a version
    history entry. Per spec §3.1: the hard_errors gate is enforced by the
    ROUTER, not re-checked here — callers must never call this with a
    result that has non-empty hard_errors.
    """
    oid = _to_object_id(project_id)
    if oid is None:
        return None

    now = datetime.utcnow()
    hard_error_count = len(result.get("hard_errors", []))
    warning_count = len(result.get("warnings", []))
    version_entry = VersionHistoryEntry(
        edited_at=now,
        summary=f"Calculation run — {hard_error_count} hard_errors, {warning_count} warnings",
    )

    update_result = await get_projects_collection().find_one_and_update(
        {"_id": oid},
        {"$set": {"last_calculation_result": result, "updated_at": now}, "$push": {"version_history": version_entry.model_dump()}},
        return_document=True,
    )
    if update_result is None:
        return None
    logger.info("Calculation result saved: project_id=%s", project_id)
    return _doc_to_project(update_result)