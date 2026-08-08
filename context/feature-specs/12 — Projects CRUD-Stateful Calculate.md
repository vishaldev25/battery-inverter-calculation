# Feature 12 — Projects CRUD + Stateful Calculate

**Status:** Spec for review — no code yet, per workflow rules.
**Boundary:** `backend/projects/` only (`repository.py` new, `router.py` extended). Does not touch `backend/calculation/`, `backend/catalog/`, or any frontend directory — single system boundary per `architecture.md`.
**Depends on:** Feature 08 (`router.py`'s stateless pipeline — unchanged, still called as-is), Feature 11 (`backend/catalog/matcher.py` — consumed for the first time here), Feature 02 (`backend/projects/models.py` — `Project`, `LoadItem`, `ProjectParameters`, already verified in the last review pass).

---

## 1. What this unit delivers

Two things, kept in one unit because they're the same system boundary (`backend/projects/`) and the second can't be tested without the first:

1. **Project CRUD** — create, read, update, delete, with version history — against the `projects` MongoDB collection (`architecture.md` Storage Model, `code-standards.md` Data and Storage rules).
2. **A stateful `/calculate` flow** — takes a `project_id` instead of a full inline payload, loads the project's saved `loads`/`parameters` from MongoDB, runs the *existing* Feature 08 pipeline unchanged, optionally consults `backend/catalog/matcher.py` for Recommend mode, and — only if `hard_errors` is empty — saves the result into `last_calculation_result` and appends a version history entry.

**Explicitly NOT in this unit** (per `ai-workflow-rules.md` splitting rules and `project-overview.md`'s scope):
- Dashboard tab/filter queries (`GET /projects?tab=...`) — that's Feature 14.
- CSV upload/parsing — Feature 13.
- PDF export — separate `backend/report/` boundary, not started.
- Any frontend work — this is backend-only.
- Duplicate/archive/favorite-toggle *UI* — the card actions in `project-overview.md`'s scope, but the underlying data support (status field, `is_favorite` field) is included here since it's the same collection and same CRUD surface; the frontend wiring is a separate unit.

---

## 2. Endpoints

All under `backend/projects/router.py`, prefix `/api/projects` (matches Feature 08's existing router).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects` | Create a new project (name required; loads/parameters optional, default to empty/defaults per `models.py`) |
| `GET` | `/api/projects/{project_id}` | Fetch one project by id |
| `PUT` | `/api/projects/{project_id}` | **Full replace** of a project's editable fields (name, description, loads, parameters) — client sends the complete object, matching the project-workspace's "hold full state, save as one shot" pattern. Triggers version history + `updated_at` per Invariant 9. |
| `PATCH` | `/api/projects/{project_id}/favorite` | Single-field toggle: `{ "is_favorite": true \| false }`. Dashboard star-click only — does **not** require the full project payload, and does **not** count as an "edit" for the Edited tab (see §3.3). |
| `PATCH` | `/api/projects/{project_id}/status` | Single-field update: `{ "status": "draft" \| "active" \| "completed" \| "archived" }`. Same lightweight-mutation reasoning as favorite. |
| `DELETE` | `/api/projects/{project_id}` | Delete a project — **requires server-side name-match confirmation**, per `architecture.md`'s Auth and Access Model and `code-standards.md`'s API Routes rule ("never trust a frontend-only confirmation") |
| `POST` | `/api/projects/{project_id}/calculate` | Stateful calculate: loads project from DB, runs Feature 08 pipeline, optionally matches catalog, saves result if zero hard errors |

**Why `PUT` + two dedicated `PATCH` endpoints instead of one general partial-update route:** standard REST practice — `PUT` means full replace, `PATCH` means partial update, and overloading `PUT` to sometimes mean "just flip this one field" invites exactly the kind of stale-state clobbering that dashboard card actions (star/unstar, archive) are prone to if the frontend's cached copy of a project is out of date. Two dedicated single-field routes are cheap to add and keep each mutation's blast radius obvious.

Note: Feature 08's existing stateless `POST /api/projects/calculate` (no `{project_id}`, full payload) **stays as-is, unchanged** — it's still useful for a "preview before saving" flow in the frontend later, and removing/renaming it isn't in scope for this unit.

---

## 3. `backend/projects/repository.py` — CRUD + version history

Pure data-access layer, mirrors the boundary discipline already established in `backend/catalog/matcher.py` (no calculation logic, no side effects beyond MongoDB reads/writes).

### 3.1 Functions

- `create_project(project: Project) -> Project` — inserts, returns the created document (with generated `_id`).
- `get_project(project_id: str) -> Optional[Project]` — fetch by id, `None` if not found (matches the `get_battery_by_id` pattern from Feature 11 — never raises on "not found," caller decides the HTTP status).
- `replace_project(project_id: str, updated: Project) -> Optional[Project]` — full-object replace (backs the `PUT` endpoint). **Always** sets `updated_at = datetime.utcnow()` and appends a `version_history` entry — this is a backend responsibility per Invariant 9, never inferred by the frontend, and never optional/skippable via a request flag.
- `set_favorite(project_id: str, is_favorite: bool) -> Optional[Project]` — single-field write (backs the `PATCH .../favorite` endpoint). Updates `is_favorite` only. Does **not** touch `updated_at` or `version_history` — see §3.3 for why.
- `set_status(project_id: str, status: str) -> Optional[Project]` — single-field write (backs the `PATCH .../status` endpoint). Updates `status` only, plus `updated_at` + a version history entry (a status change, e.g. draft → active or → archived, is a substantive edit, unlike starring — see §3.3).
- `delete_project(project_id: str, confirm_name: str) -> bool` — deletes only if `confirm_name` matches the stored project's `name` exactly (case-sensitive, no trimming beyond what the frontend already sends) — server-side re-check even though the frontend also confirms, per `code-standards.md`. Returns `False` (not an exception) if the name doesn't match or the project doesn't exist — router layer decides whether that's a 404 or a 409.
- `save_calculation_result(project_id: str, result: dict) -> Optional[Project]` — writes `last_calculation_result`, updates `updated_at`, appends a version history entry with a summary like `"Calculation run — N hard_errors, M warnings"`. **Never called if the result has any `hard_errors`** (enforced in the router, not silently re-checked here — single source of truth for that gate stays in the router where the pipeline output is already in scope).

### 3.2 Version history entry shape

Matches the `version_history` array shape already defined in `calculation-engine-and-data-model.md` Part 2.1:
```json
{ "edited_at": ISODate, "summary": "string", "snapshot_ref": null }
```
`snapshot_ref` stays `null` for this unit — full-snapshot or diff-based history is explicitly left as "implementation choice, not yet decided" per that doc; deferring rather than guessing.

### 3.3 What counts as "changes previously-saved data" (Invariant 9 trigger)

- Any field update via `PUT` (name, description, loads, parameters) — full-replace, always triggers.
- `PATCH .../status` — triggers. Changing a project's status (e.g. active → archived) is a substantive state change a version history entry should capture.
- `PATCH .../favorite` — **does not** trigger. Starring/unstarring is a personal-organization action, not an edit to the engineering content of the project; `project-overview.md` describes Favorites as its own dashboard tab distinct from "Edited," which implies the two are meant to be independently trackable, not the same signal. Treating every star-click as an "edit" would make the Edited tab noisy and useless for its actual purpose (surfacing projects whose numbers/loads changed).
- A saved calculation result (only on zero-hard-error runs) — triggers.
- Does **not** trigger on `last_opened_at` updates (viewing a project isn't "editing" it) — that's a separate, lighter-weight touch that Feature 14's dashboard queries will need for "Recent" sorting, but is out of scope to wire up here since there's no view/open endpoint being built in this unit yet.

---

## 4. Stateful `/calculate` — Recommend vs. Validate mode

Per `project-overview.md` Core User Flow step 7-8 and `calculation-engine-and-data-model.md` Part 3, step 3b.

### 4.1 Request shape

```json
{
  "mode": "recommend" | "validate",
  "chosen_battery_id": "string | null",   // required if mode == "validate"
  "chosen_inverter_id": "string | null",  // required if mode == "validate"
  "cable_length_m": 5.0,
  "charge_current_a": 0.0,
  "charge_window_hours": 0.0,
  "components_colocated": false
}
```

### 4.2 Flow — **Decision: Recommend mode returns every passing candidate pair; the user picks.**

This matches how professional sizing tools actually work (Victron's design tool, Schneider EcoStruxure) — compute the requirement once, list every catalog entry that clears the hard gates with its own final numbers, and let the engineer choose. Nothing gets silently picked "best" on their behalf.

Because Stage 2/3 of the Feature 08 pipeline (`calculate_battery_bank`, `calculate_inverter_sizing`) each take a *single* `battery`/`inverter` object, recommend mode runs in two passes:

1. Load the project via `repository.get_project(project_id)`. 404 if not found.
2. **Stage 1 (load aggregation) runs once, mode-independent** — `E_day`, `P_peak`, `S_peak`, `S_surge` don't depend on which battery/inverter is chosen, so there's no reason to recompute them per candidate.
3. **Validate mode:** fetch `chosen_battery_id`/`chosen_inverter_id` via `matcher.get_battery_by_id`/`get_inverter_by_id`. 400 if either isn't found in the catalog. Run Stages 2-5 once against that single pair. Same response shape as Feature 08 today.
4. **Recommend mode:**
   a. Call `matcher.find_battery_candidates(bank_voltage_nominal=parameters.system_dc_voltage, chemistry=parameters.battery_chemistry)` → candidate battery list.
   b. Call `matcher.find_inverter_candidates(s_continuous_required_va=..., s_surge_required_va=..., v_bank_actual=parameters.system_dc_voltage, active_load_categories=[...], grid_tie_required=...)` → candidate inverter list. (Note: this uses the *pre-battery-sizing* voltage/VA figures from Stage 1 as the initial filter — see Open Question 1 below on cross-pairing.)
   c. For every `(battery, inverter)` pair in the cartesian product of the two candidate lists, run Stages 2-5 once. Each pair produces its own independent result object (its own `hard_errors`/`warnings` — a pair can fail even if both components individually passed the matcher's pre-filter, since Stage 2's string solver and Stage 5's cross-module checks are pair-specific, e.g. LVD coordination depends on the *actual* battery chosen, not just "a battery that could work").
   d. Return the list of **only the pairs with zero `hard_errors`**, each with its full result object, sorted by... see Open Question 1.
5. **Neither mode saves anything to the project yet.** `POST .../calculate` in Recommend mode returns candidates for the user to review — nothing is committed to `last_calculation_result` until the user picks one.
6. **A separate, small action commits the choice:** `POST /api/projects/{project_id}/calculate/commit` with `{ "battery_id": "...", "inverter_id": "..." }` (or, in Validate mode, the single result from step 3 is committed directly since there's only ever one candidate). This re-runs Stages 2-5 once for the chosen pair (cheap — it's not re-querying the catalog) and calls `repository.save_calculation_result(...)`, exactly as originally scoped in step 5 of the old flow.

This does mean recommend mode can run the pipeline N×M times for N battery candidates and M inverter candidates. Given catalog data is "manually curated seed data" per Invariant 6 (small, curated sets — 4 batteries / 4 inverters in the current seed), this is cheap in practice; if the catalog grows large enough for this to matter, that's a future optimization (e.g. capping candidates before cross-pairing), not a concern for this unit.

---

## 5. Decisions (resolved)

1. **Recommend mode returns all passing candidate pairs; user picks.** See §4.2 for the two-pass, cartesian-product design this implies.
2. **Delete confirmation: exact, case-sensitive match.** Confirmed.
3. **`PUT` = full replace; single-field mutations get dedicated `PATCH` endpoints** (`favorite`, `status`) instead of overloading `PUT` for partial updates. Standard REST practice — see §2.

## 6. One new open question from the recommend-mode redesign

1. **Sort order for returned candidate pairs, and inverter pre-filter inputs (§4.2.4b/4.2.4d).** Two sub-parts:
   - The inverter matcher needs `s_continuous_required_va`/`s_surge_required_va` from Stage 1, which are available before any battery is chosen — fine. But it *also* optionally takes `battery_end_of_discharge_voltage` for the LVD hard gate, which genuinely depends on which battery ends up chosen (chemistry + DOD). Running the inverter pre-filter *before* pairing means that parameter can't be supplied yet — so the pre-filter pass will under-filter slightly (some inverters that pass the matcher's initial scan will still fail the full pipeline's per-pair LVD check in Stage 5, and get correctly excluded there instead). That's not a bug, just worth knowing: the matcher's role here is a coarse pre-filter to avoid running the pipeline against catalog entries that can't possibly work, not the final gate — the final gate is always the full per-pair pipeline run. Confirming this is the intended division of labor rather than something to "fix" by restructuring the matcher.
   - What order should the returned candidate list be presented in? Options: cheapest first (needs a `price` field the catalog models don't currently have — would be a scope addition), smallest adequate capacity first (closest match to the requirement, least oversizing), or just catalog insertion order (simplest, no new logic). Leaning toward "smallest adequate capacity/VA first" since it's meaningful to an engineer without needing new catalog fields, but want your call before hardcoding a sort key.

---

## 6. Verification plan (per `ai-workflow-rules.md`'s "Before Moving to the Next Unit")

- CRUD: create → get → update (confirm `updated_at` + `version_history` changed) → delete (confirm name-mismatch is rejected, confirm exact-match succeeds).
- Stateful calculate: run against a project with loads that match the full spec's worked example (already used to verify Features 03-07) — confirm the stateful path produces byte-identical `battery_summary`/`inverter_summary` numbers to the existing stateless Feature 08 endpoint, since this unit must not duplicate or drift from that math (Invariant 1, and `ai-workflow-rules.md`'s "no formula duplicated across modules" check).
- Confirm a run with a known `hard_errors` case (e.g. non-integer series count) does **not** write to `last_calculation_result` — this is the one behavior in this unit with real safety consequence if it's wrong.