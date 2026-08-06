# Code Standards

## General

- Keep modules small and single-purpose — one component, one hook, or one backend function should do one clear thing.
- Fix root causes, do not layer workarounds on top of a bug. If the sizing math or a validation rule is wrong, fix it in `backend/calculation/` or `backend/csv/` directly — never patch the wrong number in the frontend display layer.
- Do not mix unrelated concerns in one component, route, or function (e.g., do not mix CSV parsing logic with PDF generation logic, even if they happen to run in the same request).
- Every engineering formula or constraint implemented must trace back to the sizing specification document (`battery_inverter_sizing_full_spec.md`) — do not invent or approximate a formula that isn't defined there without flagging it as an open question first.

## JavaScript (Frontend)

- This project uses **plain JavaScript, not TypeScript**. Do not introduce `.ts`/`.tsx` files or TypeScript syntax.
- Use **JSDoc comments** for function signatures and complex objects (props, API response shapes) where type clarity is genuinely needed — this gives editor type-hints without requiring TypeScript.
- Validate all data coming back from the backend API before using it in the UI (e.g., check a result object has the expected fields before rendering) — the frontend should never assume a shape blindly, since it is the boundary where backend responses meet the UI.
- Avoid deeply nested prop-drilling — use React Context only for genuinely cross-cutting state (e.g., theme/dark-mode, current project ID), not as a default for everything.
- Keep components function-based with hooks; no class components.

## React + Vite

- Keep components focused: a component that renders a form, fetches data, *and* handles PDF export in one file is doing too much — split it.
- Data-fetching logic (API calls to FastAPI) lives in a dedicated `api/` or `services/` layer, not inline inside components — components call these functions, they don't build fetch requests directly.
- Loading and error states must be handled explicitly for every API call — never leave a request unhandled with a silent failure, especially for calculation results and CSV upload validation, where the user needs to know exactly what went wrong.
- Route structure should mirror the system boundaries in `architecture.md`: dashboard routes separate from project-workspace routes.

## Styling

- Use Tailwind utility classes with the CSS custom property tokens defined in `ui-context.md` — no hardcoded hex values anywhere in the codebase.
- Follow the border radius scale and spacing conventions defined in `ui-context.md`; do not introduce one-off values.
- Dark mode and light mode must both be implemented for every new component using the token system — never ship a component that only works in one mode.

## Backend (FastAPI / Python)

- All request and response bodies are defined as **Pydantic models** — no raw/unvalidated dicts crossing an API boundary.
- Validate and parse all input (manual form data, CSV rows, query parameters) before any calculation or database logic runs.
- The calculation engine (`backend/calculation/`) must be pure functions wherever possible — same input always produces the same output, no hidden dependency on request state or database calls buried inside the math itself.
- Every calculation function must clearly separate `hard_errors` from `warnings` in its return value, per the sizing spec's output schema — never merge the two into one generic error list.
- Return consistent, predictable response shapes across all endpoints (a standard success/error envelope), so the frontend can handle responses uniformly.
- No calculation logic, formula, or constraint is ever duplicated between backend modules — a formula defined in `backend/calculation/battery.py` is never re-implemented (even partially) in `backend/report/` or anywhere else; other modules call the calculation engine's output, they don't recompute.

## API Routes

- Validate and parse request input before any logic runs (Pydantic handles most of this automatically — do not bypass it with manual dict access).
- Every mutation route (create/edit/delete project) must perform the delete-confirmation check (project name match) server-side for delete operations — never trust a frontend-only confirmation.
- Return errors with clear, specific messages (especially for CSV row validation) — never a generic "something went wrong."

## Data and Storage

- Project metadata, load lists, calculation results, and version history belong in the `projects` collection in MongoDB.
- Catalog data (equipment ratings, battery models, inverter models) belongs in separate collections (`equipment_catalog`, `battery_catalog`, `inverter_catalog`) — never embedded inside project documents, per Architecture Invariant 4.
- Do not store generated PDF files in the database or file storage — generate on-demand from stored project data and stream the response, per the storage model in `architecture.md`.
- Every write to a project that changes previously-saved data must update its "edited" timestamp and append to its version history — this is a backend responsibility, never inferred by the frontend.

## File Organization

- `frontend/dashboard/` — Project list, tabs, filters, search, project creation
- `frontend/project-workspace/` — Load entry, parameter selection, results display
- `frontend/report/` — PDF export trigger/download handling (client side only)
- `frontend/components/ui/` — shadcn/ui components (do not hand-edit; use the CLI to add new ones)
- `frontend/api/` — All calls to the FastAPI backend, isolated from UI components
- `backend/calculation/` — Battery, inverter, and cable sizing engine (pure Python, no side effects)
- `backend/catalog/` — Equipment/battery/inverter catalog matching logic
- `backend/csv/` — CSV template generation, parsing, and row-level validation
- `backend/projects/` — Project CRUD, version history, tab/filter queries
- `backend/report/` — PDF generation (ReportLab)