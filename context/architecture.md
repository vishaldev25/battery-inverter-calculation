# Architecture Context

## Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend Framework | React + Vite | Client-side app — dashboard, project workspace, forms, results display |
| Styling | Tailwind CSS | Utility-first styling, token-driven (see `ui-context.md`) |
| UI Components | shadcn/ui | Base component library (buttons, forms, dialogs, tabs, etc.) |
| Backend Framework | FastAPI (Python) | API layer, calculation engine, CSV parsing, PDF generation |
| Validation | Pydantic | Request/response schemas, CSV row-level validation, hard-error vs. warning separation |
| Database | MongoDB Atlas | Stores projects, catalogs (equipment ratings, battery models, inverter models) |
| CSV Parsing | Pandas | Parses uploaded CSV files before Pydantic validation |
| PDF Generation | ReportLab | Generates the exportable PDF report (pure Python, no system dependencies — required for Vercel serverless) |
| Hosting | Vercel (single project) | Frontend + FastAPI backend deployed together as one Vercel project |

## System Boundaries

- `frontend/dashboard/` — Landing page. Owns the project list, tabs (All/Recent/Favorites/Edited), date-range filter, search, and project creation entry point. Does not own any calculation logic.
- `frontend/project-workspace/` — Owns the per-project experience: firm/load-type selection, load entry (manual + CSV upload), parameter selection (voltage, series/parallel, reserve days, region, temperature unit), and results display. Sends raw inputs to the backend and only displays what the backend returns — never recomputes sizing values itself.
- `frontend/report/` — Owns PDF export trigger and download handling on the client side. The PDF file itself is generated entirely in the backend.
- `backend/calculation/` — Owns the full sizing engine: load aggregation, power factor lookup, battery bank sizing (Ah, temperature/aging/DOD/Peukert corrections, string solver), inverter sizing (continuous/surge VA), and cable/fuse sizing. This is the single source of truth for all engineering math — pure Python functions, no side effects, fully unit-testable in isolation.
- `backend/catalog/` — Owns the equipment ratings library, battery model catalog, and inverter model catalog (all manually curated, admin-editable). Owns matching a calculated requirement against available catalog entries. Does not perform sizing math itself — only matches against results the calculation module produces.
- `backend/csv/` — Owns CSV template generation, parsing (Pandas), and row-level validation (valid / invalid / missing), producing a clear per-row report before any data reaches the calculation module.
- `backend/projects/` — Owns all project CRUD (create, read, update, delete), version history, and the tab/filter query logic (All, Recent, Favorites, Edited, date-range, search) against MongoDB.
- `backend/report/` — Owns PDF generation (ReportLab), assembling the load breakdown, totals, recommendation, cable/fuse sizing, and warnings into the final document.

## Storage Model

- **MongoDB Atlas — `projects` collection**: One document per project. Contains project metadata (name, firm/load type, created/edited timestamps, favorite flag), the full load list as entered, selected parameters (voltage, region, temperature unit, etc.), the last calculation result (battery + inverter recommendation, cable sizing, warnings), and version history entries.
- **MongoDB Atlas — `equipment_catalog` collection**: Curated equipment ratings library (name, category, typical wattage, typical power factor), separate from project documents so admin edits don't require touching every project.
- **MongoDB Atlas — `battery_catalog` collection**: Curated battery models (voltage, Ah rating, chemistry, max continuous/surge discharge current, etc.), sourced manually for now (see Invariant 6).
- **MongoDB Atlas — `inverter_catalog` collection**: Curated inverter models (continuous VA, surge VA, waveform, input voltage window, efficiency curve, certifications), sourced manually for now.
- **No file/blob storage required for v1** — PDF reports are generated on-demand from stored project data and streamed to the user, not stored as files.

## Auth and Access Model

- No login/authentication in this version. This is a deliberate, temporary decision — see Invariant 7.
- Every project is openly accessible and editable by anyone with its link (view and edit are not separated in v1).
- Deleting a project requires an explicit confirmation step (typing the project name) before the delete request is sent, since there is no account-based recovery if it's a misclick.
- Ownership/ACL logic does not exist in v1 — do not build partial or assumed access-control logic; treat every request to a project endpoint as authorized.

## Invariants

1. **The calculation engine lives entirely in the backend (`backend/calculation/`), never in the frontend.** The frontend only ever sends raw inputs and displays results returned by the API — it must never reimplement or duplicate any sizing formula client-side.
2. **The calculation engine never silently returns an unsafe or incomplete result.** Every response distinguishes `hard_errors` (which block a final result from being returned) from `warnings` (which are informational and shown alongside a valid result) — per the sizing spec's Part I schema. A result is never returned while a `hard_errors` entry is present.
3. **Power factor is never a free-text field controlled purely by guesswork.** It is either the standards-based category default (server-side lookup table) or an explicit user override that has been validated against a sane range — never an unvalidated arbitrary number.
4. **Catalog data (`backend/catalog/`) and project data (`backend/projects/`) are stored in separate MongoDB collections and never embedded into each other.** Admin updates to a battery/inverter/equipment catalog entry must never require touching existing project documents.
5. **Region and temperature-unit selection changes which formulas/values are used, not just the displayed labels.** Celsius vs. Fahrenheit and India vs. other regions must map to real differences in the correction tables/constants applied by the calculation engine, not just a cosmetic unit conversion after the fact.
6. **Manually curated catalog data is treated as a known-limited seed set, not as guaranteed-current market data.** The system must never present catalog battery/inverter/equipment entries as live, real-time, or guaranteed-current pricing or availability — that capability is explicitly deferred (see `project-overview.md` Out of Scope). This boundary must remain clearly visible in the code and, where relevant, in the UI.
7. **No user login exists in this version, and no partial/half-built auth logic should be introduced.** Do not add session tokens, ownership checks, or access-control code "just in case" — build for the open-access model as specified, and treat future authentication as a distinct, separately-scoped unit of work when it is actually taken up.
8. **CSV validation always separates valid rows from invalid/missing ones — it never guesses or silently drops data.** Every rejected row must be returned with a clear, specific reason; every accepted row must have passed the same Pydantic validation as manually entered data.
9. **A project's "Edited" status and version history are updated by the backend on every save that changes previously-saved data — never inferred or reconstructed by the frontend.**