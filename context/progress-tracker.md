# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase
- In progress: Phase 3 - API & Routing (Phase 1 & 2 complete).

## Current Goal
- Seed the battery/inverter/equipment catalogs and implement catalog-matching logic so `/calculate` can move from "bring your own battery/inverter" to Recommend + Validate modes.

## Completed
- **Infrastructure:** Initialized frontend with React + Vite (Plain JavaScript, no TypeScript).
- **Infrastructure:** Installed and configured Tailwind CSS v4 using the `@tailwindcss/vite` plugin (legacy PostCSS configs removed).
- **Infrastructure:** Initialized shadcn/ui and installed base components (`card`, `button`, `input`, `label`, `select`).
- **Infrastructure:** Injected custom CSS variables (dark/light mode tokens like `--bg-surface`, `--accent-primary`, etc.) into `src/index.css`.
- **Infrastructure:** Configured Vite path aliases (`@/`) in `jsconfig.json` and `vite.config.js`.
- **Infrastructure:** Initialized Git repository and pushed initial code for CodeRabbit PR integration.
- **Infrastructure:** Created `/backend` directory and Python virtual environment (`venv`).
- **Infrastructure:** Installed required backend dependencies (`fastapi[standard]`, `pydantic`, `pymongo`, `pandas`, `reportlab`, `python-dotenv`) and generated `requirements.txt`.
- **Infrastructure:** Scaffolded standard backend module folders (`calculation`, `catalog`, `csv`, `projects`, `report`, `db`) and `__init__.py` files.
- **Feature 01 (Backend Constants):** Created `backend/calculation/constants.py` with strict IEEE/NEC standard engineering defaults (Power Factors, Surge Multipliers, Battery Chemistry limits, Temp correction).
- **Feature 02 (Backend Data Models):** Created Pydantic models in `backend/projects/models.py` and `backend/catalog/models.py` to define the exact shapes of MongoDB collections (`projects`, `equipment_catalog`, `battery_catalog`, `inverter_catalog`).
- **Feature 03 (Backend Calculation):** Created `backend/calculation/load.py` to aggregate `LoadItem` data, apply constants, and calculate Peak VA, Surge VA, and Daily Energy.
- **Feature 04 (Backend Calculation):** Created `backend/calculation/battery.py` to calculate Ah requirements, apply Peukert's law, temperature corrections (IEEE 485), and solve for series/parallel string configurations.
- **Feature 05 (Backend Calculation):** Created `backend/calculation/inverter.py` to match continuous and surge apparent power requirements, apply future expansion factors, and validate waveform and input voltage windows.
- **Feature 06 (Backend Calculation):** Created `backend/calculation/cabling.py` to calculate $I_{design}$, voltage drop, and overcurrent protection based on NEC 210.19/215.2 standard rules.
- **Feature 07 (Backend Calculation):** Created `backend/calculation/validation.py` to perform system-level cross-checks (voltage consistency, surge current limits, recharge feasibility) and aggregate all module warnings and errors.
- **Feature 08 (Backend API):** Created `backend/projects/router.py` — a stateless `POST /api/projects/calculate` endpoint wiring Features 03–07 into the full 5-stage pipeline (Load → Battery → Inverter → Cabling → Cross-Validation), with per-stage early-exit on `hard_errors` and a deduplicated final `MasterCalculationResponse`.
- **Feature 09 (Backend API):** Created `backend/main.py` — FastAPI app entrypoint. Mounts the calculation router, configures environment-driven CORS, adds a standard `{ success, error, data }` envelope for `HTTPException` / `RequestValidationError` / unhandled `Exception`, and exposes `GET /health`. Verified: `/health` returns `200 {"status":"ok"}`; malformed `/calculate` correctly returns the standard envelope with clear per-field messages.
- **Feature 10 (Database):** Created `backend/db/client.py` — async MongoDB connection layer using `AsyncMongoClient`, reading `MONGODB_URI`/`DATABASE_NAME` from environment with loud failure on missing config. Wired into `backend/main.py` via FastAPI's `lifespan` context manager (connect + ping on startup, clean close on shutdown). Exposes `get_projects_collection()`, `get_equipment_catalog_collection()`, `get_battery_catalog_collection()`, `get_inverter_catalog_collection()` — connection/accessors only, no query logic. **Fully verified end-to-end:** startup log shows successful ping (`MongoDB connection established successfully.`), `/health` unaffected (`200 OK`), and clean shutdown log (`MongoDB connection closed.`) confirmed via `Ctrl+C`.

## In Progress
- **Feature 11 (Catalog):** Seeding `battery_catalog`/`inverter_catalog`/`equipment_catalog` placeholder entries and implementing `backend/catalog/` matching logic (Recommend mode: query candidates against a calculated requirement; Validate mode: fetch a specific catalog entry by ID).

## Next Up
- **Feature 12 (Projects CRUD):** `backend/projects/repository.py` — full project CRUD, version history, and a stateful `/calculate`-and-save route.
- **Feature 13 (CSV):** `backend/csv/` — template generation, Pandas parsing, row-level validation.
- **Feature 14 (Dashboard Queries):** `backend/projects/queries.py` — All/Recent/Favorites/Edited tab queries + date-range/search filtering.

## Open Questions
- **Feature 08 field alignment:** `router.py` references fields like `payload.parameters.system_dc_voltage`, `payload.selected_battery.nominal_voltage`, `payload.selected_inverter.nominal_dc_voltage` on the Feature 02 Pydantic models — not yet re-verified against actual model field names. Still open; should be checked once Feature 11's seed data gives us real catalog documents to test `/calculate` against end-to-end (rather than just the empty-body validation test done so far).
- **Feature 09 CORS:** Production origin(s) resolved via `ALLOWED_ORIGINS` env var. Not blocking.

## Resolved Issues (Feature 09/10 debugging log)
Keeping this so the same mistakes aren't repeated in later units:

1. **`ModuleNotFoundError: No module named 'backend'`** — caused by running `uvicorn backend.main:app` from *inside* `backend/` instead of the project root. Fix: always run uvicorn from the project root (`D:\Sangam AI\My work\battery_inverter_size\`), never from inside `backend/`.
2. **`DatabaseConfigError: Missing required environment variable 'MONGODB_URI'`** — `load_dotenv()` with no path looks in the current working directory, but `.env` lives inside `backend/`, and uvicorn now runs from the project root — so the bare `.env` lookup missed it. Fix: `load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")` to make the lookup independent of the working directory.
3. **`AssertionError: Path parameters cannot have a default value`** — `Path` was imported from `fastapi` (for route path parameters) *and* needed from `pathlib` (for file paths) in the same file, and the `fastapi.Path` import shadowed `pathlib.Path`, so `Path(__file__)` was parsed as a FastAPI route-parameter declaration. Fix: only import `Path` from `pathlib`; never import `fastapi.Path` unless a route actually declares a path parameter, and if both are ever needed, alias one (e.g. `from fastapi import Path as FastAPIPath`).
4. **Mongo connection logs not appearing despite success** — root logger defaults to `WARNING`, so `logger.info(...)` calls were silently suppressed even though `connect_to_mongo()` succeeded. Fix: added `logging.basicConfig(level=logging.INFO)` near the top of `main.py`, right after `import logging`.

## Security Notes
- **Credential rotation (resolved):** MongoDB Atlas password was exposed in chat during `.env` review and has since been rotated by the user. `.env` confirmed excluded from version control going forward.

## Architecture Decisions
- **Frontend Typing:** Strictly adhering to Plain JavaScript with JSDoc comments where needed, explicitly rejecting TypeScript per `code-standards.md`.
- **CSS Framework:** Adopted Tailwind v4 (latest standard) meaning no `tailwind.config.js` is used; all theme mapping is strictly controlled via `src/index.css`.
- **Theme Variables:** Directly mapped the premium engineering-software UI tokens into the CSS root variables. Cards will use the standard `rounded-xl` (12px) per `ui-context.md`.
- **Git Strategy:** Utilizing feature branch workflows; Pull Requests into `main` trigger CodeRabbit automated code reviews.
- **Backend Architecture:** Created strict folder separation (`calculation/`, `projects/`, `db/`, etc.) per `code-standards.md` to ensure pure functions, DB access, and API logic do not mix.
- **Database Driver:** Using `pymongo`'s `AsyncMongoClient` for fully asynchronous non-blocking interactions with MongoDB.
- **Data Layers (Feature 01 & 02):** Generic, immutable IEEE/NEC engineering defaults hardcoded in `constants.py` as a fail-safe baseline; dynamic manufacturer-specific equipment specs and user project configurations are strictly typed with Pydantic and stored in MongoDB.
- **Calculation Engine (Feature 03-07):** Pure mathematical pipeline, fully IEEE/NEC-formula-based. Hard errors act as deterministic blockers for invalid system designs.
- **API Layer (Feature 08):** `/calculate` is intentionally stateless — no MongoDB reads/writes inside the calculation pipeline itself, keeping `backend/calculation/` pure per Architecture Invariant 1.
- **Entrypoint (Feature 09):** `backend/main.py` must be run from the project root. All environment-dependent config read via `os.environ`, `python-dotenv` loads `.env` locally using an explicit path anchored to `backend/`.
- **DB Layer (Feature 10):** Single reused `AsyncMongoClient` instance managed via FastAPI's `lifespan` — connects + pings on startup, closes cleanly on shutdown. Collection accessors are simple named functions with no query logic (kept for Features 11/12/14, per one-boundary-per-unit scoping in `ai-workflow-rules.md`). `get_database()` raises rather than silently returning `None` if called before startup completes.

## Session Notes
- Both `/frontend` and `/backend` foundations are 100% complete and version-controlled.
- Virtual environment `venv` created inside `/backend`. Must be activated before running backend servers or installing new pip packages.
- Features 01 through 10 complete and fully verified, including clean startup and shutdown logging for the MongoDB connection.
- Several small debugging rounds during Feature 09/10 (see Resolved Issues above) — all resolved, none blocking.
- Moving into Feature 11: give the calculation pipeline real catalog data to match against, instead of requiring the caller to supply a full battery/inverter spec by hand every time.