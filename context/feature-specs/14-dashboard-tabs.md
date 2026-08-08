```markdown
# Feature 14 — Dashboard Tab & Filter Queries

**Status:** Spec for review — no code yet, per workflow rules.
**Boundary:** `backend/projects/` only (`queries.py` — new file, plus one new route added to the existing `backend/projects/router.py`). Does not touch `backend/calculation/`, `backend/catalog/`, `backend/csv/`, or any frontend directory.
**Depends on:** Feature 12 (`backend/projects/models.py` — `Project` fields `status`, `is_favorite`, `created_at`, `updated_at`, `last_opened_at`, `name`, all confirmed present), Feature 12 (`backend/projects/repository.py` — this unit follows its pure-data-access, function-per-operation pattern).

---

## 1. What this unit delivers

Per `project-overview.md`'s Dashboard feature and `ui-context.md`'s Dashboard layout spec:
> Dashboard organizes projects into four tabs: All, Recent (by last opened/edited), Favorites (user-starred), and Edited (modified after creation, with last-edited timestamp). Filter bar above the project list: date-range filter and project-name search, both working within whichever tab is active.

And `architecture.md`'s boundary for this module:
> `backend/projects/` — Owns all project CRUD ..., version history, and the tab/filter query logic (All, Recent, Favorites, Edited, date-range, search) against MongoDB.

One new file, `backend/projects/queries.py`, plus two new routes on the existing `backend/projects/router.py`:

1. **Tab logic** — `All`, `Recent`, `Favorites`, `Edited` as four distinct MongoDB query/sort strategies.
2. **Date-range filter** — applied on top of whichever tab is active, against the timestamp field that's actually meaningful for that tab (see §5).
3. **Search** — case-insensitive project-name substring match, applied on top of whichever tab is active.
4. **Pagination** — standard `limit`/`offset`, since an unbounded list endpoint behind a card-grid dashboard is not real-world practice (see §6).
5. **A small write endpoint** — `PATCH /api/projects/{id}/opened`, setting `last_opened_at`, without which the Recent tab has nothing to sort by (see §6 — Feature 12 deferred this, this unit is where it becomes necessary).

**Explicitly NOT in this unit** (per your answers):
- Drawer filters (Application Type, System Type, Battery Technology, Status, Location) — these fields don't exist on `Project`/`ProjectParameters` yet. Confirmed out of scope; not silently built against fields that don't exist, and not silently skipped-forever either — this will be logged as a real, named future feature in `progress-tracker.md` (adding those fields is itself a `backend/projects/models.py` change, a different unit) rather than left implicit.
- Any frontend rendering of tabs/filters/drawer — backend-only.

---

## 2. Verified field mapping

Checked directly against the `Project` model as extended in Feature 12:

| Field | Type | Used for |
|---|---|---|
| `id` | `str` (alias `_id`) | Route path param for the new `opened` endpoint |
| `name` | `str` | Search (`q` param) |
| `is_favorite` | `bool` | Favorites tab |
| `created_at` | `datetime` | Edited-tab comparison baseline; `all` tab default sort |
| `updated_at` | `datetime` | Edited tab filter (`updated_at != created_at`, per `calculation-engine-and-data-model.md` Part 3 step 6 — already specified there, not invented); date-range target for `all`/`favorites`/`edited` tabs |
| `last_opened_at` | `Optional[datetime]` | Recent tab sort key AND date-range target for the `recent` tab specifically |

No other `Project` field is needed for the four tabs as scoped.

---

## 3. Endpoints

Added to the existing `backend/projects/router.py` (same file Feature 12 already extended — no new module).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects` | List projects for a given tab, with date-range, search, and pagination |
| `PATCH` | `/api/projects/{project_id}/opened` | Sets `last_opened_at = now()`. Does **not** touch `updated_at`/`version_history` — viewing a project isn't editing it, same reasoning `repository.py`'s `set_favorite` already established in Feature 12 for a non-edit mutation. |

### 3.1 Query parameters for `GET /api/projects`

```
tab       : "all" | "recent" | "favorites" | "edited"   (required)
date_from : ISO date string, optional
date_to   : ISO date string, optional
q         : string, optional — case-insensitive substring match on name
limit     : int, optional, default 20, max 100
offset    : int, optional, default 0
```

### 3.2 Response shape

Matches Feature 09's existing `{ success, error, data }` envelope. `data` is:
```json
{
  "items": [ /* Project objects */ ],
  "total_count": 0,
  "limit": 20,
  "offset": 0
}
```
`total_count` is a separate count query (pre-pagination), so the frontend can render "Page X of Y" or a "Load more" control without a second round trip.

---

## 4. Tab logic

| Tab | Filter | Sort | Date-range applies to |
|---|---|---|---|
| `all` | none | `created_at` descending (newest first) | `created_at` |
| `recent` | none | `last_opened_at` descending, **nulls last** (never-opened projects rank behind opened ones) | `last_opened_at` |
| `favorites` | `is_favorite == true` | `updated_at` descending | `updated_at` |
| `edited` | `updated_at != created_at` | `updated_at` descending | `updated_at` |

`backend/projects/queries.py` exposes one function per tab (`get_all_projects`, `get_recent_projects`, `get_favorite_projects`, `get_edited_projects`), each accepting `date_from`/`date_to`/`q`/`limit`/`offset` — mirroring `repository.py`'s function-per-operation style rather than one large parameterized query function, per `code-standards.md`'s "keep modules small and single-purpose."

---

## 5. Date-range — per-tab field, not a single hardcoded field (your answer to Q3)

Industry-standard dashboards (Notion, Linear, Google Drive) filter a date-range control against whichever timestamp is the tab's own primary sort signal, not a single fixed field across every view — otherwise "Recent, filtered to last 7 days" would silently mean "created in the last 7 days," which contradicts what "Recent" is showing the user. So:

- `all` / `favorites` / `edited` → date range filters `created_at` / `updated_at` / `updated_at` respectively (matching each tab's own sort field from §4).
- `recent` → date range filters `last_opened_at`.

This is implemented as a small `_DATE_FIELD_BY_TAB` mapping inside `queries.py`, not duplicated logic per function.

---

## 6. Pagination and the `opened` endpoint (your answers to Q2 and Q4)

- **Pagination:** standard `limit`/`offset`, default `limit=20` (matches `ui-context.md`'s dashboard grid — "4–5 cards per row (desktop)... equal card height" strongly implies a bounded, paged grid, not an unbounded scroll-everything list), `offset=0`, `max limit=100` to prevent an accidental full-collection dump. `total_count` returned alongside so the frontend can build page controls.
- **`PATCH /api/projects/{id}/opened`:** added in this unit, industry standard being "recently viewed" lists are only ever meaningful if something actually writes the "last viewed" timestamp — every real product with a Recent tab (Google Drive, Figma, Notion) fires this on open, not on edit. Without it, `recent` is permanently sorted as all-nulls and the tab is dead on arrival. This is a one-field, no-version-history write (matches `set_favorite`'s precedent from Feature 12 for non-substantive mutations), so it stays inside this unit's boundary rather than being deferred again.

---

## 7. Decisions (resolved, from your answers)

1. Drawer filters (Application Type, System Type, Battery Technology, Status, Location) — **confirmed out of scope**, logged as a genuinely future feature (needs model fields that don't exist yet) rather than silently dropped.
2. `last_opened_at` write support — **added in this unit** via `PATCH .../opened`, industry-standard pattern.
3. Date-range field — **per-tab**, matching each tab's own primary timestamp (§5), not a single hardcoded field.
4. Pagination — **added**, standard `limit`/`offset` with `total_count`, per §6.
5. Default sort for `all` — `created_at` descending, confirmed.

---

## 8. Verification plan (per `ai-workflow-rules.md`'s "Before Moving to the Next Unit")

- Seed a handful of test projects via a throwaway smoke-test script (same pattern as Features 11/13) with varying `is_favorite`, `created_at`/`updated_at` (some equal, some not), and `last_opened_at` (some null, some set).
- Confirm `all` returns everything sorted newest-`created_at`-first; `favorites` returns only `is_favorite == true`; `edited` returns only rows where `updated_at != created_at`; `recent` sorts nulls last.
- Confirm date-range filtering uses the correct field per tab (e.g. a `recent` query with a narrow `date_from`/`date_to` excludes a project whose `last_opened_at` falls outside the range, even if its `created_at` would have matched).
- Confirm search (`q`) narrows correctly within a tab (test at least `tab=favorites&q=...`).
- Confirm pagination: `limit=2&offset=0` then `limit=2&offset=2` on a 5-project seed returns non-overlapping pages that together account for all 5, and `total_count` reports `5` on both calls.
- Confirm `PATCH .../opened` updates `last_opened_at` only — `updated_at` and `version_history` must be provably unchanged before/after the call.
- Confirm no calculation or catalog logic was touched — this unit only reads/queries `projects` (plus the one narrow `opened` write), never calculates, never touches catalogs.
```
