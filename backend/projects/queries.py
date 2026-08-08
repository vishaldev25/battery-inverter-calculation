"""
Dashboard Tab & Filter Queries
Boundary: backend/projects/ — pure read-only query layer against the
`projects` collection. Mirrors repository.py's data-access discipline:
no calculation logic, no side effects beyond MongoDB reads.

Per architecture.md: "Owns ... the tab/filter query logic (All, Recent,
Favorites, Edited, date-range, search) against MongoDB."

Reuses repository.py's _doc_to_project (same module/package, same
document-shaping responsibility) rather than duplicating that conversion
logic here — code-standards.md's no-duplication rule applies to trivial
helpers too, not just formulas.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.db.client import get_projects_collection
from backend.projects.models import Project
from backend.projects.repository import _doc_to_project

logger = logging.getLogger("backend.projects.queries")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Per-tab date-range target field (Feature 14 spec §5): a date range on
# "Recent" filters last_opened_at, not created_at — matches what each tab
# is actually showing the user, not a single hardcoded field.
_DATE_FIELD_BY_TAB: Dict[str, str] = {
    "all": "created_at",
    "recent": "last_opened_at",
    "favorites": "updated_at",
    "edited": "updated_at",
}

_SORT_FIELD_BY_TAB: Dict[str, str] = {
    "all": "created_at",
    "recent": "last_opened_at",
    "favorites": "updated_at",
    "edited": "updated_at",
}


def _clamp_limit(limit: int) -> int:
    if limit < 1:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def _build_date_range_filter(
    tab: str, date_from: Optional[datetime], date_to: Optional[datetime]
) -> Dict[str, Any]:
    if date_from is None and date_to is None:
        return {}
    field = _DATE_FIELD_BY_TAB[tab]
    range_query: Dict[str, Any] = {}
    if date_from is not None:
        range_query["$gte"] = date_from
    if date_to is not None:
        range_query["$lte"] = date_to
    return {field: range_query}


def _build_search_filter(q: Optional[str]) -> Dict[str, Any]:
    if not q or not q.strip():
        return {}
    # Case-insensitive substring match on name only, per ui-context.md's
    # toolbar search being project-name search (distinct from the Filters
    # drawer, which is out of scope per Feature 14 decisions).
    # re.escape() prevents a user's search text from being interpreted as
    # regex syntax (metacharacters like . * ( ) [ ] would otherwise either
    # throw a $regex compile error or match unintended documents) — this
    # is a substring search, not a regex search, from the user's perspective.
    escaped = re.escape(q.strip())
    return {"name": {"$regex": escaped, "$options": "i"}}


def _build_tab_base_filter(tab: str) -> Dict[str, Any]:
    if tab == "favorites":
        return {"is_favorite": True}
    if tab == "edited":
        # $expr lets us compare two fields on the same document — this is
        # the exact rule already specified in
        # calculation-engine-and-data-model.md Part 3 step 6
        # ("filter updated_at != created_at for Edited"), not invented here.
        return {"$expr": {"$ne": ["$updated_at", "$created_at"]}}
    return {}  # "all" and "recent" have no base filter


async def _run_tab_query(
    tab: str,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    q: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Project], int]:
    """
    Shared execution path for all four tabs. Each public tab function below
    only supplies `tab` — the actual query/sort/paginate logic is defined
    exactly once here, per code-standards.md's single-purpose rule.
    """
    base_filter = _build_tab_base_filter(tab)
    date_filter = _build_date_range_filter(tab, date_from, date_to)
    search_filter = _build_search_filter(q)

    combined_filter: Dict[str, Any] = {}
    for fragment in (base_filter, date_filter, search_filter):
        combined_filter.update(fragment)

    collection = get_projects_collection()
    sort_field = _SORT_FIELD_BY_TAB[tab]
    clamped_limit = _clamp_limit(limit)
    safe_offset = max(offset, 0)

    total_count = await collection.count_documents(combined_filter)

    # Descending sort on a nullable/non-unique datetime field alone does not
    # guarantee stable ordering across separate queries when values tie
    # (e.g. multiple projects with last_opened_at=None, or the same
    # created_at timestamp) — with skip/offset pagination that can cause a
    # document to appear on two pages or be skipped entirely. Adding _id as
    # a secondary sort key (unique, monotonically increasing) makes the
    # full sort order deterministic without changing the primary tab sort.
    cursor = (
        collection.find(combined_filter)
        .sort([(sort_field, -1), ("_id", -1)])
        .skip(safe_offset)
        .limit(clamped_limit)
    )
    docs = await cursor.to_list(length=clamped_limit)
    projects = [_doc_to_project(doc) for doc in docs]

    logger.info(
        "Dashboard query: tab=%s filter=%s total=%d returned=%d",
        tab, combined_filter, total_count, len(projects),
    )
    return projects, total_count


async def get_all_projects(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Project], int]:
    return await _run_tab_query("all", date_from, date_to, q, limit, offset)


async def get_recent_projects(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Project], int]:
    return await _run_tab_query("recent", date_from, date_to, q, limit, offset)


async def get_favorite_projects(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Project], int]:
    return await _run_tab_query("favorites", date_from, date_to, q, limit, offset)


async def get_edited_projects(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Project], int]:
    return await _run_tab_query("edited", date_from, date_to, q, limit, offset)


# Dispatch table so router.py can resolve `tab` -> the right function
# without an if/elif chain duplicating the tab-name strings.
TAB_DISPATCH = {
    "all": get_all_projects,
    "recent": get_recent_projects,
    "favorites": get_favorite_projects,
    "edited": get_edited_projects,
}