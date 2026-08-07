# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase
- In progress: Phase 3 - API & Routing (Phase 1 & 2 complete).

## Current Goal
- Build project CRUD (create/read/update/delete, version history) and wire the catalog matcher into a stateful `/calculate`-and-save flow.

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
- **Feature 08 (Backend API):** Created `backend/projects/router.py` — stateless `POST /api/projects/calculate` wiring the full 5-stage pipeline with per-stage hard-error early-exit. **Field alignment verified against `backend/projects/models.py`:** `system_dc_voltage`, `days_of_autonomy`, and `target_inverter_efficiency` all confirmed present on `ProjectParameters` with matching types; `LoadItem`, `BatteryCatalog`, and `InverterCatalog` field references used in `router.py` (`nominal_watts`, `nominal_voltage`, `max_continuous_discharge_amps`, `surge_va`, `nominal_dc_voltage`, etc.) also cross-checked and confirmed. No mismatches found.
- **Feature 09 (Backend API):** Created `backend/main.py` — FastAPI entrypoint, environment-driven CORS, standard `{ success, error, data }` error envelope, `GET /health`. Fully verified.
- **Feature 10 (Database):** Created `backend/db/client.py` — async MongoDB connection layer (`AsyncMongoClient`), wired into `main.py`'s `lifespan`. Fully verified: successful ping on startup, clean close on shutdown, `/health` unaffected.
- **Feature 11 (Catalog):** 
  - Created `backend/catalog/seed_data.py` with placeholder entries for `battery_catalog` (4), `inverter_catalog` (4), `equipment_catalog` (7), shaped exactly to the real `models.py` (`extra="forbid"`).
  - Created `backend/catalog/seed.py` — idempotent upsert seeding script, verified via two clean runs (0 inserted / N refreshed on the second run, confirming no duplication).
  - Created `backend/catalog/matcher.py` — `find_battery_candidates`, `get_battery_by_id`, `find_inverter_candidates`, `get_inverter_by_id`. Performs filtering only — queries MongoDB via `find({})` and applies the sizing spec's hard gates (voltage-divisibility + chemistry for batteries; continuous/surge VA, voltage window, waveform, grid-tie certification, and LVD coordination for inverters) as **Python-side filtering** on the returned documents, not as MongoDB query predicates — an acceptable tradeoff at current catalog size (small, manually curated per Architecture Invariant 6); `continuous_va`/`surge_va` would be the first candidates to push into the query filter if the catalog grows large enough for it to matter. It never computes N_series/N_parallel, VA sizing, or any other formula owned by `backend/calculation/` (no formula duplication).
  - **LVD hard gate fixed to fail closed:** `find_inverter_candidates` previously passed a candidate through when `lvd_threshold_v` was `None` (unknown/undeclared), instead of rejecting it — a fail-open bug on a spec-mandated hard gate (Part E2: "all must pass — hard gate, not scoring"). Fixed so a missing/unknown LVD threshold is now treated as a failed gate, not a pass.
  - **`InverterCatalog.lvd_threshold_v` fixed to reject non-finite values:** `gt=0` alone does not exclude `+inf` (Pydantic allows non-finite floats by default), so a `+inf` LVD threshold would have passed model validation and then trivially satisfied the LVD hard gate in `matcher.py` for any finite battery voltage — silently defeating the fail-closed fix above. Fixed by adding `allow_inf_nan=False` to the field. (`input_voltage_window`'s manual validator already rejected non-finite values explicitly, so it was unaffected.)
  - **Extended `backend/catalog/models.py`:** added `input_voltage_window`, `lvd_threshold_v`, `certifications`, `grid_tie_capable` to `InverterCatalog` (all optional/default-safe) — see Architecture Decisions for the reasoning.
  - **Fully verified via smoke test** (`_smoke_test.py`, since deleted): battery candidate search (voltage-divisibility + chemistry filter), single battery lookup, inverter candidate search (VA + voltage-window + waveform), single inverter lookup, grid-tie-required filtering (certifications + capability), and grid-tie-not-required filtering — all returned exactly the expected candidates against real seeded data.

## In Progress
- **Feature 12 (Projects CRUD + stateful calculate):** Not yet started. Will build `backend/projects/repository.py` (create/read/update/delete, version history) and extend `backend/projects/router.py` to (a) wire `backend/catalog/matcher.py` into Recommend/Validate mode selection, and (b) save `last_calculation_result` after a successful (zero-hard-error) calculation.

## Next Up
- **Feature 13 (CSV):** `backend/csv/` — template generation, Pandas parsing, row-level validation.
- **Feature 14 (Dashboard Queries):** `backend/projects/queries.py` — All/Recent/Favorites/Edited tab queries + date-range/search filtering.

## Open Questions
- **Feature 09 CORS:** Production origin(s) resolved via `ALLOWED_ORIGINS` env var. Not blocking.
- **`BatteryCatalog` / other `InverterCatalog` numeric fields (`capacity_ah`, `nominal_voltage`, `continuous_va`, `surge_va`, etc.) share the same bare `gt=0` pattern** as the pre-fix `lvd_threshold_v` and are equally exposed to `+inf` passing validation in principle (e.g. a `+inf` VA rating would trivially pass every sizing gate in `router.py`/`matcher.py`). Not yet swept — flagged for a deliberate batch pass (`allow_inf_nan=False` across all numeric fields in `catalog/models.py`) rather than fixing them one review comment at a time. Not blocking Feature 12.

## Resolved Issues (debugging log — keeping so mistakes aren't repeated)
1. **`ModuleNotFoundError: No module named 'backend'`** — caused by running commands (`uvicorn`, `python -m backend...`) from *inside* `backend/` instead of the project root. **Rule going forward: always run Python module commands from the project root** (`D:\Sangam AI\My work\battery_inverter_size\`), never from inside `backend/`.
2. **`DatabaseConfigError: Missing required environment variable 'MONGODB_URI'`** — bare `load_dotenv()` looks in the current working directory; `.env` lives in `backend/`. Fixed via `load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")` anchored to the file's own location.
3. **`AssertionError: Path parameters cannot have a default value`** — `fastapi.Path` import shadowed `pathlib.Path` in the same file. Fixed by only importing `Path` from `pathlib`.
4. **Mongo connection logs silently missing** — root logger defaults to `WARNING`. Fixed via `logging.basicConfig(level=logging.INFO)`.
5. **`ModuleNotFoundError: No module named 'dotenv'`** — venv wasn't activated in the shell (prompt showed no `(venv)` prefix). Fixed via `backend\venv\Scripts\Activate.ps1` (or `activate` once inside `backend/`), with an execution-policy note (`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`) if PowerShell blocks the script.
6. **`ModuleNotFoundError: No module named 'backend'` (seed script)** — same root cause as #1, seed script run from inside `backend/` instead of project root.
7. **`seed.py` `.env` path resolved to `backend/.env` instead of project root** — `load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")` only walked up two levels (`backend/catalog/seed.py` → `backend/`), but `.env` lives at the project root, one level above `backend/`. Fixed via `Path(__file__).resolve().parents[2] / ".env"`.
8. **`find_inverter_candidates` LVD gate failed open on missing threshold** — see Feature 11 note above. Fixed to fail closed.
9. **`InverterCatalog.lvd_threshold_v` accepted `+inf`, silently defeating fix #8** — see Feature 11 note above. Fixed via `allow_inf_nan=False`.

## Security Notes
- **Credential rotation (resolved):** MongoDB Atlas password was exposed in chat and has since been rotated. `.env` confirmed excluded from version control.

## Architecture Decisions
- **Frontend Typing:** Plain JavaScript with JSDoc, no TypeScript, per `code-standards.md`.
- **CSS Framework:** Tailwind v4, no `tailwind.config.js`, theme mapping via `src/index.css`.
- **Git Strategy:** Feature branch workflow; PRs into `main` trigger CodeRabbit review.
- **Backend Architecture:** Strict folder separation (`calculation/`, `projects/`, `catalog/`, `db/`, etc.) per `code-standards.md`.
- **Database Driver:** `pymongo`'s `AsyncMongoClient`, fully async.
- **Calculation Engine (03-07):** Pure, IEEE/NEC-formula-based, hard-error blocking.
- **API Layer (08):** `/calculate` intentionally stateless; no DB access inside `backend/calculation/`.
- **Entrypoint (09):** Must run from project root; env-driven config via `os.environ` + `python-dotenv` with an explicit anchored path.
- **DB Layer (10):** Single reused `AsyncMongoClient` via FastAPI `lifespan`; collection accessors only, no query logic (deferred to 11/12/14 per one-boundary-per-unit scoping).
- **Catalog Layer (11):** `backend/catalog/matcher.py` performs filtering only — it queries MongoDB and applies the hard-gate conditions already defined in the sizing spec as Python-side filtering on returned documents, but never computes N_series/N_parallel, VA sizing, or any other formula owned by `backend/calculation/` (respects Architecture Invariant 1 and `code-standards.md`'s no-duplication rule). **`InverterCatalog` was deliberately extended** (not left as-is) to add `input_voltage_window`, `lvd_threshold_v`, `certifications`, `grid_tie_capable` — reasoning: the sizing spec treats grid-tie/anti-islanding certification as a legal safety requirement, not optional, and `project-overview.md`'s data model already anticipates a `"hybrid"` system mode; retrofitting a safety-relevant field later under time pressure was judged riskier than adding optional, default-safe fields now. All new fields default to safe/inert values (`None`, `False`, `[]`) so no existing document or code path breaks. `matcher.py` falls back to exact `nominal_dc_voltage` matching when `input_voltage_window` is unset, preserving backward compatibility with any future minimal catalog entries. The LVD coordination gate fails closed: a candidate with no declared `lvd_threshold_v` cannot be verified safe against the battery's end-of-discharge voltage, so it is excluded rather than passed by default. **Numeric safety fields must reject non-finite values, not just enforce `gt=0`** — `lvd_threshold_v` now sets `allow_inf_nan=False` for this reason; other numeric fields in the catalog models share the same latent gap and are tracked as an open question rather than fixed ad hoc.

## Session Notes
- Features 01 through 11 complete and fully verified, including live smoke-testing against real seeded Atlas data for catalog matching (battery candidates, inverter candidates, grid-tie gating).
- Several PowerShell/venv/path debugging rounds during Features 09-11 (see Resolved Issues) — all resolved, pattern now well understood (always run from project root, always confirm `(venv)` in prompt before running Python commands).
- `backend/catalog/_smoke_test.py` was a throwaway verification script and has been deleted post-verification — not part of the permanent codebase.
- A follow-up review pass on Features 08 and 11 closed out three findings: Feature 08's `router.py`-to-`models.py` field alignment was checked and confirmed correct (no code change needed); Feature 11's matcher description was corrected to accurately state Python-side filtering instead of MongoDB-query-side filtering; and a real fail-open bug in the LVD hard gate was found and fixed.
- A further review pass caught that the LVD fail-closed fix could be silently bypassed via a `+inf` `lvd_threshold_v` value, since `gt=0` alone doesn't exclude non-finite floats in Pydantic. Fixed via `allow_inf_nan=False`. Same latent gap flagged (not yet fixed) on other numeric catalog fields — logged as an open question for a deliberate batch pass rather than reactive one-off fixes.
- Moving into Feature 12: this is the first unit where `backend/projects/router.py` gets touched again since Feature 08, and the first time `backend/catalog/matcher.py` actually gets consumed by the API layer instead of just tested standalone.