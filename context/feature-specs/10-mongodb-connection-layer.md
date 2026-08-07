# Feature Spec: 10-mongodb-connection-layer

## Objective
Create the async MongoDB connection layer that later features (catalog seeding/matching, project CRUD, dashboard queries) will depend on. This unit only establishes the connection and exposes collection accessors — it does not implement any read/write/query logic itself, per `ai-workflow-rules.md`'s scoping rules (one system boundary per unit).

## Context to Read Before Starting
1. `context/architecture.md` (**Storage Model** — the four collections: `projects`, `equipment_catalog`, `battery_catalog`, `inverter_catalog`; **Invariant 4** — catalog and project data must stay in separate collections, never embedded).
2. `context/calculation-engine-and-data-model.md` (**Part 2 — MongoDB Collections** — exact document shapes to sanity-check the connection against).
3. `context/code-standards.md` (**Data and Storage** section).
4. Progress tracker's **Architecture Decisions** — `pymongo`'s `AsyncMongoClient` was already chosen as the driver; stay consistent with that.

## Scope of Work
Create `backend/db/` as a new module (`backend/db/__init__.py`, `backend/db/client.py`).

1. **Environment-driven configuration**
   - Read `MONGODB_URI` and `DATABASE_NAME` from `os.environ` (already loaded via `python-dotenv` in `main.py` — Feature 10 does not need to call `load_dotenv()` again, just rely on `os.environ` being populated by the time this module is used).
   - Fail loudly (raise a clear startup error, not a silent `None`) if `MONGODB_URI` or `DATABASE_NAME` is missing — a missing DB config should never surface later as a confusing `NoneType has no attribute...` error deep in a query.

2. **Connection lifecycle**
   - Instantiate a single `AsyncMongoClient` instance, created once and reused (not re-created per-request) — this is a connection pool, not a per-call connection.
   - Wire this into FastAPI's lifespan (startup: connect / verify with a ping; shutdown: close the client cleanly) rather than creating it at import time with no verification.
   - Expose a `get_database()` (or similar) function/dependency that other modules can import to get the active database handle.

3. **Collection accessors**
   - Expose named accessors (functions or constants) for the four collections defined in `architecture.md`: `get_projects_collection()`, `get_equipment_catalog_collection()`, `get_battery_catalog_collection()`, `get_inverter_catalog_collection()`.
   - These just return `database["<collection_name>"]` — no query logic, no CRUD, no indexes yet (indexes can be a later concern once query patterns from Feature 12/14 are known).

4. **Startup verification**
   - On app startup (via the lifespan hook), perform a lightweight connectivity check (e.g., `await client.admin.command("ping")`) and log success/failure clearly — so a bad URI or network/firewall issue fails fast and visibly at boot, not silently on the first request that happens to touch the DB.

5. **Wire into `backend/main.py`**
   - Convert `main.py`'s app instantiation to use FastAPI's `lifespan` context manager (replacing/adding to the existing `@app.on_event` style if any), so the Mongo client connects on startup and disconnects on shutdown.
   - This is the only touchpoint into `main.py` for this unit — no new routes, no CRUD routes yet.

## Out of Scope
- **NO CRUD logic** — that's Feature 12 (`backend/projects/repository.py`).
- **NO catalog seeding or matching logic** — that's Feature 11.
- **NO new API routes** — this unit is purely the connection layer.
- **NO index creation** — defer until query patterns are known (Feature 12/14).
- **NO changes to `backend/calculation/`** — per Architecture Invariant 1, the calculation engine never touches the database directly; this connection layer exists for the route/repository layer to use, not for the pure calculation functions.

## Acceptance Criteria
- `backend/db/client.py` exists, reads `MONGODB_URI`/`DATABASE_NAME` from the environment, and raises a clear error at startup if either is missing.
- Running `uvicorn backend.main:app --reload` connects to MongoDB Atlas on startup and logs a successful ping — verified against your (rotated) Atlas cluster.
- Deliberately setting an invalid `MONGODB_URI` (or blocking network access) produces a clear, loud startup failure — not a silent hang or a cryptic error surfacing later.
- `GET /health` still returns `200 {"status": "ok"}` with the DB layer wired in (no regression from Feature 09).
- No collection read/write/query code exists yet — only connection setup and accessor functions.
- `backend/calculation/` remains untouched — still pure functions with zero DB dependency.