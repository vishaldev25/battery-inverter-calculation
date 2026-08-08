# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase
- Phase 3 - API & Routing. Feature 14 complete and verified (including a post-verification datetime deprecation fix).

## Current Goal
- Feature 15: `POST /projects/{id}/loads/csv-upload` — wiring Feature 13's parser/validator into `backend/projects/router.py`.

## Completed
- **Infrastructure:** Initialized frontend with React + Vite (Plain JavaScript, no TypeScript).
- **Infrastructure:** Installed and configured Tailwind CSS v4 using the `@tailwindcss/vite` plugin.
- **Infrastructure:** Initialized shadcn/ui and installed base components (`card`, `button`, `input`, `label`, `select`).
- **Infrastructure:** Injected custom CSS variables (dark/light mode tokens) into `src/index.css`.
- **Infrastructure:** Configured Vite path aliases (`@/`) in `jsconfig.json` and `vite.config.js`.
- **Infrastructure:** Initialized Git repository and pushed initial code for CodeRabbit PR integration.
- **Infrastructure:** Created `/backend` directory and Python virtual environment (`venv`).
- **Infrastructure:** Installed backend dependencies (`fastapi[standard]`, `pydantic`, `pymongo`, `pandas`, `reportlab`, `python-dotenv`) and generated `requirements.txt`.
- **Infrastructure:** Scaffolded standard backend module folders (`calculation`, `catalog`, `csv`, `projects`, `report`, `db`) and `__init__.py` files.
- **Feature 01 (Backend Constants):** Created `backend/calculation/constants.py` with strict IEEE/NEC standard engineering defaults.
- **Feature 02 (Backend Data Models):** Created Pydantic models in `backend/projects/models.py` and `backend/catalog/models.py`.
- **Feature 03-07 (Backend Calculation):** Full pure calculation pipeline — load aggregation, battery sizing (Peukert, temp correction, string solver), inverter sizing, cabling/protection sizing, and cross-module validation. All IEEE 485/1013/NEC-based.
- **Feature 08 (Backend API):** Created `backend/projects/router.py` — stateless `POST /api/projects/calculate` wiring the full 5-stage pipeline with per-stage hard-error early-exit. Field alignment verified against `backend/projects/models.py`.
- **Feature 09 (Backend API):** Created `backend/main.py` — FastAPI entrypoint, environment-driven CORS, standard `{ success, error, data }` error envelope, `GET /health`. Fully verified.
- **Feature 10 (Database):** Created `backend/db/client.py` — async MongoDB connection layer (`AsyncMongoClient`), wired into `main.py`'s `lifespan`. Fully verified: successful ping on startup, clean close on shutdown, `/health` unaffected.
- **Feature 11 (Catalog):**
  - Created `backend/catalog/seed_data.py`, `backend/catalog/seed.py` (idempotent upsert seeding, verified via two clean runs), and `backend/catalog/matcher.py` (`find_battery_candidates`, `get_battery_by_id`, `find_inverter_candidates`, `get_inverter_by_id`) — Python-side filtering only, no formula duplication.
  - **LVD hard gate fixed to fail closed** (was fail-open on missing `lvd_threshold_v`).
  - **`InverterCatalog.lvd_threshold_v` fixed to reject non-finite values** (`allow_inf_nan=False`), since `gt=0` alone doesn't exclude `+inf`.
  - **Extended `backend/catalog/models.py`:** added `input_voltage_window`, `lvd_threshold_v`, `certifications`, `grid_tie_capable` to `InverterCatalog`.
  - Fully verified via smoke test (deleted after confirmation).
- **Feature 12 (Projects CRUD + stateful calculate):**
  - `backend/projects/models.py` extended: `is_favorite`, `version_history` (`VersionHistoryEntry`), `last_opened_at` added to `Project`.
  - `backend/projects/repository.py` created: `create_project`, `get_project`, `replace_project`, `set_favorite` (no `updated_at`/`version_history` touch — starring isn't editing), `set_status` (does bump both), `delete_project` (server-side exact-name-match re-check), `save_calculation_result`.
  - `backend/projects/router.py` extended: Feature 08's pipeline body extracted into `_execute_pipeline()` — stateless and stateful paths share identical code. Full CRUD routes added, plus stateful `POST /{id}/calculate` (Validate mode: single pair; Recommend mode: cartesian product of catalog candidates, only zero-hard-error pairs returned, sorted smallest-adequate-first) and `POST /{id}/calculate/commit`.
  - Recommend-mode sort key verified against real `battery.py`/`inverter.py` output shapes, not guessed.
- **Feature 13 (CSV template, parsing, row-level validation):**
  - `backend/csv/models.py`, `parser.py`, `validator.py`, `template.py` created. Every row validated against the **real** `LoadItem` model (Architecture Invariant 8) — no parallel schema. Blank optional cells stripped before construction so `LoadItem`'s own Pydantic defaults apply, matching manual-entry behavior exactly. `is_concurrent` explicitly coerced from CSV string to bool to avoid Python's `bool("False") == True` footgun.
  - Two confirmed (not fixed — different boundary) naming divergences from the spec doc logged: `is_concurrent` (bool) vs. spec's `simultaneity_factor` (float); `nominal_watts` vs. spec's `power_watts`.
  - Fully verified via smoke test run by the user directly (all 4 test groups PASS: template self-validates, empty file rejected, bad headers rejected, 5-row mixed file split 2 valid / 3 invalid with correct per-row reasons). Smoke test script deleted post-verification.
- **Feature 14 (Dashboard tab & filter queries):**
  - `backend/projects/queries.py` created: `get_all_projects`, `get_recent_projects`, `get_favorite_projects`, `get_edited_projects` — each a thin wrapper around a shared `_run_tab_query()` (single source of truth for query/sort/paginate logic, per code-standards.md). Reuses `repository.py`'s `_doc_to_project` rather than duplicating document-shaping logic.
  - **Tab logic:** `all` (no filter, sort `created_at` desc), `recent` (no filter, sort `last_opened_at` desc — nulls sort last under MongoDB's BSON ordering with descending sort, confirmed rather than assumed), `favorites` (`is_favorite == true`, sort `updated_at` desc), `edited` (`$expr: {"$ne": ["$updated_at", "$created_at"]}`, sort `updated_at` desc — the exact rule already specified in `calculation-engine-and-data-model.md` Part 3 step 6, not invented here).
  - **Date-range filter is per-tab**, not a single hardcoded field: `all`→`created_at`, `recent`→`last_opened_at`, `favorites`/`edited`→`updated_at` — matches each tab's own primary timestamp signal (industry-standard pattern per user decision).
  - **Search** is case-insensitive substring match on `name` only, via `$regex`/`$options: "i"` — matches `ui-context.md`'s toolbar search scope (distinct from the out-of-scope Filters drawer).
  - **Pagination added:** standard `limit` (default 20, max 100) / `offset`, with a separate `count_documents` call returning `total_count` alongside paginated `items` — industry-standard pattern per user decision, supports the fixed-grid dashboard layout in `ui-context.md`.
  - **`PATCH /api/projects/{id}/opened` added** (`repository.mark_project_opened`) — sets `last_opened_at` only, does not touch `updated_at`/`version_history` (mirrors `set_favorite`'s precedent). This was the missing write-side Feature 12 explicitly deferred; without it the Recent tab would have nothing to sort by. Added in this unit per user decision (industry-standard: Drive/Figma/Notion-style "recently viewed" always fires on open, not edit).
  - **Drawer filters (Application Type, System Type, Battery Technology, Status, Location) confirmed out of scope** — the underlying `Project`/`ProjectParameters` fields don't exist yet; logged as a genuinely future feature (needs a `models.py` change, a different unit) rather than silently built or silently dropped.
  - `GET /api/projects` and `PATCH /api/projects/{id}/opened` added to `router.py`; new `ProjectListResponse` model (`items`, `total_count`, `limit`, `offset`).
  - Fully verified via smoke test (`_smoke_test_14.py`, throwaway, deleted after confirmation): seeded 4 projects covering plain/favorite/edited/recently-opened states; confirmed each tab's filter/sort correctness, per-tab date-range field targeting, search narrowing, pagination (2+2 pages covering all 4, no overlap), and the `opened` endpoint updating only `last_opened_at`.
  - **Post-verification fix — `datetime.utcnow()` deprecation:** `backend/projects/models.py` and `backend/projects/repository.py` both switched from the deprecated `datetime.utcnow()` to a shared local `_utc_now()` helper (`datetime.now(timezone.utc)`) in each file. **Storage remains UTC, timezone-aware** — deliberately not switched to IST storage, since `project-overview.md` scopes non-India regions as in-scope (not hypothetical), so region/timezone-correct storage must stay UTC with local (e.g. IST) conversion happening only at the display layer (`frontend/`, not yet built). Re-verified via the same Feature 14 smoke test with the deprecation warning confirmed gone and all prior assertions still passing.

## In Progress
- None — Feature 14 fully implemented, verified, and the datetime deprecation across `models.py`/`repository.py` fixed and re-verified.

## Next Up
- **Feature 15 (CSV route wiring):** `POST /projects/{id}/loads/csv-upload` in `backend/projects/router.py`, consuming Feature 13's `parser.py`/`validator.py` — deliberately deferred out of Feature 13 since it touches a second backend module (split rule).
- **Feature 16 (Report):** `backend/report/` — PDF generation (ReportLab), reading `last_calculation_result` only, no recalculation, fixed light-mode styling per `ui-context.md`.
- **Future, unscoped feature:** Dashboard Filters drawer (Application Type, System Type, Battery Technology, Status, Location) — requires new fields on `Project`/`ProjectParameters` first (a `backend/projects/models.py` change), then the corresponding query logic in `queries.py`. Not yet a numbered feature.
- **Future, unscoped, low-priority:** IST (or general locale) timestamp display formatting — belongs in `frontend/` once the dashboard/project-workspace UI is being built; backend intentionally stores UTC only (see Feature 14's datetime fix note above).

## Open Questions
- **[Carried, unresolved] LVD/end-of-discharge-voltage coordination (sizing spec Part E2) is not implemented anywhere in the pipeline.** `validate_system_design` (Stage 5) has no LVD check; `matcher.find_inverter_candidates` supports the gate but Feature 12/14's recommend-mode pre-filter can't supply `battery_end_of_discharge_voltage` (no battery chosen yet at that stage). Net effect: unenforced end-to-end. `backend/calculation/validation.py` boundary issue, not patched in Features 12/14.
- **[Carried, unresolved] `validate_system_design`'s recharge-feasibility check is dead code** — reads a `battery_result["ah_discharged"]` key that `battery.py` never sets. `backend/calculation/` boundary issue.
- **No `price` field on `BatteryCatalog`/`InverterCatalog`** — Recommend-mode sorts by smallest-adequate-capacity instead of cost. Confirmed by reading both models, not assumed.
- **Feature 09 CORS:** Production origin(s) resolved via `ALLOWED_ORIGINS` env var. Not blocking.
- **Numeric catalog fields beyond `lvd_threshold_v` still lack `allow_inf_nan=False`** — flagged for a deliberate batch pass, not fixed ad hoc. Not blocking Features 12–14.
- **[Carried] `LoadItem` field naming diverges from `battery_inverter_sizing_full_spec.md`** (`is_concurrent`/`nominal_watts` vs. spec's `simultaneity_factor`/`power_watts`) — informational only, real model is authoritative per `ai-workflow-rules.md`.
- **[Carried] Dashboard Filters drawer fields don't exist on the data model yet** — see "Next Up." Not a bug, just confirmed not-yet-built.
- **[NEW, Feature 14 follow-up] `mark_project_opened` and other single-field PATCH writes in `repository.py` now use timezone-aware `_utc_now()`, but older documents in MongoDB (if any exist from before this fix) may still hold naive-UTC timestamps from `datetime.utcnow()`.** Not currently a problem (MongoDB/BSON stores datetimes as UTC instants regardless of Python-side awareness, and the driver reads them back consistently), but worth knowing if a future unit ever does direct Python-side datetime comparison/arithmetic on timestamps mixed from before/after this fix — flagged, not currently blocking anything.

## Resolved Issues (debugging log — keeping so mistakes aren't repeated)
1. **`ModuleNotFoundError: No module named 'backend'`** — caused by running commands from inside `backend/` instead of the project root. Always run Python module commands from the project root.
2. **`DatabaseConfigError: Missing required environment variable 'MONGODB_URI'`** — fixed via `load_dotenv(dotenv_path=...)` anchored to the file's own location. **Recurred for `_smoke_test_14.py`** (a script one folder deeper than `main.py`) — fixed by anchoring with `Path(__file__).resolve().parents[1] / ".env"` instead of `.parent`, since the script lives in `backend/projects/`, not `backend/` directly.
3. **`AssertionError: Path parameters cannot have a default value`** — `fastapi.Path` import shadowed `pathlib.Path`. Fixed by only importing `Path` from `pathlib`.
4. **Mongo connection logs silently missing** — root logger defaults to `WARNING`. Fixed via `logging.basicConfig(level=logging.INFO)`.
5. **`ModuleNotFoundError: No module named 'dotenv'`** — venv wasn't activated. Fixed via `backend\venv\Scripts\Activate.ps1`.
6. **`ModuleNotFoundError: No module named 'backend'` (seed script)** — same root cause as #1.
7. **`seed.py` `.env` path resolved incorrectly** — fixed via `Path(__file__).resolve().parents[2] / ".env"`.
8. **`find_inverter_candidates` LVD gate failed open on missing threshold** — fixed to fail closed.
9. **`InverterCatalog.lvd_threshold_v` accepted `+inf`, silently defeating fix #8** — fixed via `allow_inf_nan=False`.
10. **`datetime.utcnow()` deprecation warning** — appeared first in `repository.py`/`models.py` usage (fixed via `_utc_now()` helper), then recurred in the smoke test script itself (`_smoke_test_14.py` had its own separate `datetime.utcnow()` call in the test-seeding code, unrelated to the application fix) — fixed the same way in the script before final verification.

## Security Notes
- **Credential rotation (resolved):** MongoDB Atlas password was exposed in chat and has since been rotated. `.env` confirmed excluded from version control.

## Architecture Decisions
- **Frontend Typing:** Plain JavaScript with JSDoc, no TypeScript, per `code-standards.md`.
- **CSS Framework:** Tailwind v4, no `tailwind.config.js`, theme mapping via `src/index.css`.
- **Git Strategy:** Feature branch workflow; PRs into `main` trigger CodeRabbit review.
- **Backend Architecture:** Strict folder separation (`calculation/`, `projects/`, `catalog/`, `db/`, `csv/`, etc.) per `code-standards.md`.
- **Database Driver:** `pymongo`'s `AsyncMongoClient`, fully async.
- **Calculation Engine (03-07):** Pure, IEEE/NEC-formula-based, hard-error blocking.
- **API Layer (08):** `/calculate` intentionally stateless; no DB access inside `backend/calculation/`.
- **Entrypoint (09):** Must run from project root; env-driven config.
- **DB Layer (10):** Single reused `AsyncMongoClient` via FastAPI `lifespan`; collection accessors only, no query logic.
- **Catalog Layer (11):** `matcher.py` performs Python-side filtering only, never computes sizing formulas. `InverterCatalog` deliberately extended with safety-relevant fields, all default-safe. LVD gate fails closed on unknown thresholds; numeric safety fields must reject non-finite values, not just enforce `gt=0`.
- **Projects Layer (12):** `repository.py` is pure data access, never raises on not-found. `_execute_pipeline()` extraction keeps stateless/stateful calculate paths provably identical. Recommend mode returns every zero-hard-error pair; user picks — no silent "best" decision. `PUT` = full replace; single-field mutations get dedicated `PATCH` routes.
- **CSV Layer (13):** Validates strictly against the real `LoadItem` — no parallel schema. Structural checks (`parser.py`) and field-level checks (`validator.py`) kept in separate files as distinct failure classes, per `code-standards.md`, regardless of file size. Blank optional CSV cells stripped before construction so `LoadItem`'s own defaulting is the single source of truth.
- **Queries Layer (14):** `queries.py` is read-only, mirrors `matcher.py`/`repository.py`'s data-access-only discipline — never computes anything, only filters/sorts/paginates. Date-range target field is per-tab by design (industry-standard: a range control filters whatever timestamp that view is actually sorted by, not one fixed field everywhere). `PATCH .../opened` was added in this unit (not deferred again) because Recent tab is meaningless without a write-side for `last_opened_at`, and every comparable real product (Drive, Figma, Notion) fires this on view, not edit — consistent with `set_favorite`'s existing "non-edit mutation" pattern from Feature 12, so no new mutation category was invented. Pagination (`limit`/`offset` + `total_count`) added as a standard expectation for any list endpoint feeding a fixed-size card grid (`ui-context.md`), not held back for a later unit, since an unbounded dashboard list has no real-world precedent for this class of app.
- **Timestamp storage policy (established during Feature 14's datetime fix):** all backend-generated timestamps are stored as timezone-aware UTC (`datetime.now(timezone.utc)`, via a small local `_utc_now()` helper in each file that needs it — deliberately not centralized into a shared utils module for a two-line helper). Locale-specific display (e.g. IST) is explicitly a `frontend/` formatting concern, never a backend storage concern — this keeps the backend correct for `project-overview.md`'s stated multi-region support rather than hardcoding an India-only assumption into stored data.

## Session Notes
- Features 01 through 13 complete and fully verified — see prior entries for detail on debugging rounds (Features 09–11) and verification methodology (throwaway smoke-test scripts, deleted post-confirmation, used consistently since Feature 11).
- Feature 14 spec went through one clarification round before implementation: user confirmed (1) drawer filters are correctly out of scope pending model changes, (2) `last_opened_at` write support should be added now rather than deferred again, (3) date-range should filter per-tab rather than one hardcoded field, and (4) pagination should be added — all resolved against industry-standard dashboard patterns (Drive/Figma/Notion-style) rather than invented from scratch.
- Feature 14 fully implemented and code-verified against the real `repository.py`/`client.py`/`router.py`/`main.py` sources the user pasted — no field names, driver methods, or envelope patterns were guessed. A throwaway `_smoke_test_14.py` (same pattern as Features 11/13) exercised all four tabs, per-tab date-range targeting, search, pagination, and the new `opened` endpoint's selective-field-write behavior, all without any frontend.
- Post-verification, the user raised the `datetime.utcnow()` deprecation warning visible in the smoke test output. Resolved as a small, immediate fix (not deferred to a future unit, since it touched already-shipped Feature 12/14 files directly) — `_utc_now()` helper added locally to both `models.py` and `repository.py`. This also prompted an explicit timestamp-storage-policy decision (UTC storage, IST/locale display deferred to frontend) rather than silently guessing which the user wanted — user's IST request was clarified as a frontend display concern, not a backend storage change, and the reasoning was confirmed against `project-overview.md`'s existing multi-region scope before proceeding. The fix initially appeared incomplete because the smoke test script itself had a separate, unrelated `datetime.utcnow()` call in its own test-seeding code — this was fixed in the throwaway script as well, and the final verification run confirmed both the warning gone and all functional assertions still passing.