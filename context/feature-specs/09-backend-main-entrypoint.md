# Feature Spec: 09-backend-main-entrypoint

## Objective
Create the FastAPI application entrypoint that mounts the calculation router (Feature 08), configures CORS for the Vite dev server, and establishes the standard success/error response envelope required by `code-standards.md`. This is the first point the backend becomes an actually-runnable server.

## Context to Read Before Starting
1. `context/architecture.md` (Stack table — FastAPI, Vercel single-project hosting).
2. `context/code-standards.md` (**API Routes** — "Return consistent, predictable response shapes across all endpoints").
3. `context/ai-workflow-rules.md` (Scoping Rules — this unit touches only the app entrypoint/wiring, not calculation or DB logic).

## Scope of Work
Create `backend/main.py`.

1. **App Instance**
   - Instantiate `FastAPI()` with title, version, and description reflecting the project (from `project-overview.md`).
   - Mount `backend/projects/router.py`'s `router` via `app.include_router(...)`.

2. **CORS Configuration**
   - Add `CORSMiddleware` allowing the local Vite dev server origin (`http://localhost:5173` and `http://127.0.0.1:5173`).
   - Keep this permissive only for local dev — flag as an open question whether prod origin(s) are known yet (Vercel single-project deploy per `architecture.md` may make this moot, but don't assume).

3. **Standard Response Envelope**
   - Per `code-standards.md`'s "Return consistent, predictable response shapes across all endpoints" rule: add a global exception handler (`@app.exception_handler(HTTPException)` and a catch-all `Exception` handler) that wraps errors into a consistent JSON shape, e.g.:
```json
     { "success": false, "error": { "code": ..., "message": ... }, "data": null }
```
   - This does **not** change `/calculate`'s existing `MasterCalculationResponse` shape (that's already a defined, deliberate schema per the sizing spec) — it only standardizes *unhandled* error responses (validation errors, 500s, etc.), so the frontend has one predictable shape to check for anything outside the calculation pipeline's own error handling.

4. **Health Check**
   - Add a minimal `GET /health` route returning `{ "status": "ok" }` — useful for confirming the Vercel serverless deployment is alive later, and for local smoke-testing right now.

5. **Run Instructions**
   - No code change, but document (in this spec or a comment) the local run command: `fastapi dev backend/main.py` or `uvicorn backend.main:app --reload`.

## Out of Scope
- **NO new calculation logic** — this unit only wires together what Features 03–08 already built.
- **NO database connection** — that's Feature 10. `main.py` should run and serve `/calculate` correctly with zero MongoDB dependency at this stage.
- **NO frontend code.**
- **NO auth/session middleware** — explicitly out of scope per `architecture.md` Invariant 7.

## Acceptance Criteria
- `backend/main.py` exists, imports and mounts `backend/projects/router.py`.
- Running `uvicorn backend.main:app --reload` starts the server with no errors.
- `GET /health` returns `200 { "status": "ok" }`.
- `POST /api/projects/calculate` (from Feature 08) is reachable and returns the `MasterCalculationResponse` shape unchanged.
- CORS allows requests from the local Vite dev origin without browser console errors.
- Any request that fails validation or throws an unhandled exception returns the standard `{ success, error, data }` envelope — verified with at least one deliberately malformed request (e.g., missing required field in payload).