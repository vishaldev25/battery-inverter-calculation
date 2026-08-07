# Feature Spec: 11-catalog-seed-and-matching

## Objective
Seed the `battery_catalog`, `inverter_catalog`, and `equipment_catalog` collections with placeholder/reference data, and implement the matching logic that lets `/calculate` operate in two modes: **Recommend** (find catalog candidates that satisfy a calculated requirement) and **Validate** (check whether a specific, user-chosen catalog entry is sufficient). Per `architecture.md`, this module matches — it never performs sizing math itself.

## Context to Read Before Starting
1. `context/architecture.md` (**System Boundaries** — `backend/catalog/` "owns matching a calculated requirement against available catalog entries. Does not perform sizing math itself"; **Invariant 4** — catalog and project data stay in separate collections; **Invariant 6** — catalog data is a known-limited seed set, never presented as live/real-time).
2. `context/calculation-engine-and-data-model.md` (**Part 2.2–2.4** — exact seed document shapes for all three catalogs).
3. `context/Battery_inverter_sizing_full_spec.md` (**Part E2** — inverter selection hard-gate rules; **Part D3** — battery string uniformity and max-parallel-strings constraints — matching logic must respect these, not just distance-sort on VA/Ah).
4. `context/code-standards.md` (**Backend** — Pydantic models at every boundary; **Data and Storage** — catalog collections never embedded in projects).

## Scope of Work

### 1. Seed data (`backend/catalog/seed_data.py` + a one-off seed script)
   - Define seed documents for:
     - `battery_catalog`: at least 3–4 entries spanning different chemistries (flooded lead-acid, AGM, LiFePO₄) and voltage/Ah combinations, using the exact shape from `calculation-engine-and-data-model.md` §2.3.
     - `inverter_catalog`: at least 3–4 entries spanning different continuous_va/surge_va ranges and waveforms, using the shape from §2.4.
     - `equipment_catalog`: a reasonable starter set across the load categories in the sizing spec (resistive, lighting_led, motor_pump, hvac, electronics_it, etc.), using the shape from §2.2.
   - Write a seed script (`backend/catalog/seed.py`, run manually via `python -m backend.catalog.seed`) that upserts this data using the Feature 10 collection accessors — idempotent (safe to re-run without duplicating documents; use `_id` as the natural key and `replace_one(..., upsert=True)`).
   - Every seed entry must include a `notes` field flagging it as placeholder/reference data, per Invariant 6 — this must never be presented as live/guaranteed-current.

### 2. Matching logic (`backend/catalog/matcher.py`)
   - **Recommend mode:** given a calculated requirement (`Ah_required`, `V_bank`, `S_continuous_required_va`, `S_surge_required_va`, load categories present, etc.), query the relevant catalog collection and return candidates that pass the hard-gate rules already defined in the spec:
     - Battery candidates: same logic Feature 04 already encodes for string-solving (series/parallel fit) — this module's job is to fetch *candidate battery models*, not resolve the string count itself (that stays in `backend/calculation/battery.py`, per Invariant 1 — no formula duplication).
     - Inverter candidates: apply the Part E2 hard gates (continuous_va, surge_va, input_voltage_window, waveform-vs-load-type, certifications) as a **filter query**, not a re-implementation of the sizing formulas.
   - **Validate mode:** given a specific `battery_id` or `inverter_id`, fetch that single catalog document by `_id` and return it (or a clear "not found" result) for the calculation pipeline to run its existing pass/fail checks against.
   - Both modes return catalog documents/candidates only — the actual accept/reject determination (hard_errors/warnings) still happens in `backend/calculation/`, not here. This module's output feeds into Stage 8/10 of the pipeline described in `calculation-engine-and-data-model.md` Part 1, it doesn't replace them.

### 3. Pydantic response shaping
   - Reuse the existing `BatteryCatalog`/`InverterCatalog` models from `backend/catalog/models.py` (Feature 02) for matcher return types — do not define parallel/duplicate models.

## Out of Scope
- **NO changes to `backend/calculation/`** — matching logic here must not re-implement string-solving, VA sizing, or any formula already owned by `backend/calculation/battery.py` / `inverter.py`.
- **NO new API routes yet** — this unit is the matching logic itself; wiring `router.py` to actually call it (so `/calculate` can accept `mode: "recommend" | "validate"` instead of requiring a full battery/inverter object every time) is a natural follow-up but should be its own small unit if it touches `router.py` meaningfully — flag as an open question rather than silently expanding scope here.
- **NO admin UI or review-queue for catalog edits** — explicitly out of scope per `project-overview.md`.
- **NO real/live pricing or availability data** — explicitly out of scope per Invariant 6.

## Acceptance Criteria
- `backend/catalog/seed_data.py` contains realistic placeholder entries for all three catalogs, each clearly flagged as reference/placeholder data.
- Running the seed script populates `battery_catalog`, `inverter_catalog`, and `equipment_catalog` in MongoDB Atlas — verified by inspecting the collections directly (e.g., via `mongosh` or Atlas's web UI).
- Re-running the seed script does not create duplicate documents (idempotent upsert confirmed).
- `backend/catalog/matcher.py` exposes clear, separately-testable functions for Recommend and Validate mode, for both battery and inverter matching.
- Matching logic returns data via the existing Feature 02 Pydantic models — no new duplicate schema introduced.
- No formula or sizing constraint already defined in `backend/calculation/` is reimplemented here — confirmed by review against `code-standards.md`'s "no calculation logic is ever duplicated between backend modules" rule.