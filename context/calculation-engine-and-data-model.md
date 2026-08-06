# Calculation Engine & Data Model — Integration Reference

This is the single document that ties the formulas (`battery_inverter_sizing_full_spec.md`), the constants/catalog units (01, 02), and MongoDB together into one working pipeline. Read this before building `backend/calculation/` or any MongoDB collection — it shows exactly what calls what, in what order, and what gets stored where.

---

## PART 1 — The Formula Execution Sheet

This is the **exact order of operations** the backend runs for one calculation request, start to finish. Each step names the function, its inputs, its output, and which spec section it implements.

```
REQUEST IN: { project_id, loads[], parameters{} }
    │
    ▼
STEP 1 — Load Aggregation                         [backend/calculation/load.py]
    Input:  loads[] (each: power_watts, qty, hours_per_day, load_category,
            simultaneity_factor, known_pf?)
    Uses:   POWER_FACTOR_TABLE (constants.py) — only for loads where
            known_pf is not provided
    Formula (per spec Part B.2 / B3.2):
        E_i = P_i × qty_i × t_i × SF_i
        E_day = Σ E_i
        P_peak = Σ (P_i × qty_i × SF_i)
        S_peak = Σ (P_i × qty_i × SF_i / PF_i)
        S_surge = max over motor-type loads k of:
                  [ P_k × surge_multiplier_k + Σ(other loads' VA) ]
    Output: { E_day_wh, P_peak_w, S_peak_va, S_surge_va, blended_pf }
    │
    ▼
STEP 2 — Standby Load Addition (if applicable)     [backend/calculation/load.py]
    Input:  P_standby_w (inverter/controller standby draw, optional)
    Formula (Part E3):
        E_standby_day = P_standby_w × 24
    Output: E_day updated → E_day_wh_total = E_day_wh + E_standby_day
    │
    ▼
STEP 3 — Ah Demand at Bank Voltage                 [backend/calculation/battery.py]
    Input:  E_day_wh_total, V_bank (user-selected)
    Formula (Part D.2):
        Ah_day = E_day_wh_total / V_bank
        Ah_autonomy = Ah_day × autonomy_days (user input)
    Output: Ah_autonomy
    │
    ▼
STEP 4 — Peukert Correction (only if I_actual departs materially   [backend/calculation/battery.py]
          from the battery's rated C-rate — e.g. short autonomy,
          high instantaneous power systems)
    Input:  C_rated, T_rated (battery datasheet), I_actual (derived from P_peak/V_bank)
    Formula (Part D.3):
        C_actual = C_rated × ( (C_rated / T_rated) / I_actual ) ^ (k - 1)
    Output: C_actual (replaces nameplate Ah in later steps if applied)
    │
    ▼
STEP 5 — Temperature Correction                    [backend/calculation/battery.py]
    Input:  ambient_temp_c (converted from °F if needed, see constants.py)
    Uses:   TEMPERATURE_CORRECTION_TABLE_C + get_temperature_correction()
    Formula (Part D.4): k_t = interpolated table value
    Output: k_t
    │
    ▼
STEP 6 — Full Correction Chain                      [backend/calculation/battery.py]
    Input:  Ah_autonomy, k_t, chemistry (η_batt, DOD_max — clamped to absolute max),
            wire_efficiency, aging_factor, design_margin  ← all user-editable,
            defaulting to constants.py values if not provided (see Unit 01 Design note)
    Formula (Part D.5):
        Ah_required = Ah_autonomy × k_t / (η_batt × η_wire × F_aging × DOD_max) × (1 + M)
    Output: Ah_required
    │
    ▼
STEP 7 — Discharge Current Check                    [backend/calculation/battery.py]
    Input:  P_peak_w, S_surge_va, V_bank, η_inverter
    Formula (Part D.2 / D.6):
        I_avg    = P_peak_w / (V_bank × η_inv)
        I_surge  = S_surge_va / (V_bank × η_inv)
    Output: I_avg, I_surge
    │
    ▼
STEP 8 — String Solver                              [backend/calculation/battery.py]
    Input:  Ah_required, I_avg, I_surge, chosen battery_option
            { voltage, ah_rating, max_continuous_discharge_a, max_surge_discharge_a }
    Formula (Part D.3 / D.6):
        N_series   = V_bank / V_battery              → must be integer, else HARD ERROR
        N_parallel = max(
                       ceil(Ah_required / Ah_battery),
                       ceil(I_avg / I_max_continuous),
                       ceil(I_surge / I_max_surge)
                     )
        Self-check loop: while Ah_bank_actual < Ah_required → N_parallel += 1
    Output: { N_series, N_parallel, N_total, V_bank_actual, Ah_bank_actual,
              I_max_bank_continuous, I_max_bank_surge }
    │
    ▼
STEP 9 — Inverter Sizing                            [backend/calculation/inverter.py]
    Input:  S_peak_va, S_surge_va, future_load_factor (user-editable, default 0.20)
    Formula (Part E.1):
        S_continuous = S_peak_va × (1 + future_load_factor)
        S_surge_required = S_surge_va (already worst-case from Step 1)
    Output: { S_continuous_required_va, S_surge_required_va }
    │
    ▼
STEP 10 — Inverter Selection Gate                   [backend/calculation/inverter.py]
    Input:  candidate inverter_option(s) from inverter_catalog
    Formula (Part E.2 — ALL must pass, hard gate not scoring):
        continuous_va ≥ S_continuous_required_va
        surge_va ≥ S_surge_required_va  (+ duration check)
        V_bank_actual within input_voltage_window
        waveform == pure_sine IF any motor/electronics/hvac load present
        LVD_threshold ≥ battery end-of-discharge voltage
        ambient/altitude derating applied to continuous_va before comparing
    Output: passing_candidates[] or HARD ERROR if none pass
    │
    ▼
STEP 11 — Cable & Protection Sizing                 [backend/calculation/cabling.py]
    Input:  I_avg (continuous), cable_length_m, conductor_type, install_method
    Formula (Part F):
        I_design = 1.25 × I_continuous
        min gauge = lookup(ampacity table, I_design, insulation, install_method)
        V_drop = (2 × L × I × R_cable) / 1000
        binding_constraint = whichever (ampacity vs voltage-drop) yields larger gauge
        I_fuse = 1.25 × I_continuous
    Output: { min_awg_or_mm2, binding_constraint, fuse_rating_a, required_breaking_capacity_a }
    │
    ▼
STEP 12 — Cross-Module Validation                   [backend/calculation/validation.py]
    Input:  all outputs from Steps 1–11
    Checks (Part G):
        - V_bank_actual matches declared V_bank input
        - I_surge does not exceed weakest link (battery / inverter / cable)
        - Recharge feasibility (if charge source specified)
        - Chemistry-specific hard flags (BMS required for lithium, ventilation
          for flooded lead-acid, sub-0°C lithium charging warning)
    Output: { hard_errors[], warnings[] }
    │
    ▼
RESPONSE OUT: Master Output Schema (see battery_inverter_sizing_full_spec.md, Part I)
              — response is only returned as "final" if hard_errors[] is empty
```

**This entire chain runs as pure functions with no database calls inside them** (per `architecture.md` Invariant 1 and `code-standards.md`). The API route layer (Unit 06, not yet written) is the only place that touches MongoDB — it reads the project's saved loads/parameters, calls this pipeline, and writes the result back.

---

## PART 2 — MongoDB Collections (schemas)

Four collections, per `architecture.md`'s storage model. Shown as the shape of each document — implement as Pydantic models in `backend/projects/models.py` and `backend/catalog/*.py`, and let MongoDB (schemaless) simply store whatever Pydantic validates.

### 2.1 `projects`
```json
{
  "_id": ObjectId,
  "name": "Green Villa Residence",
  "client_name": "ABC Builders",
  "application_type": "residential",
  "system_type": "hybrid",
  "location": { "city": "Hyderabad", "country": "India", "region": "india" },
  "status": "draft",                      // draft | active | completed | archived
  "is_favorite": false,

  "electrical_config": {
    "grid_voltage": 230,
    "frequency_hz": 50,
    "phase": "single",
    "bank_voltage_nominal": 48,
    "autonomy_days": 1,                   // or reserve hours, per wizard step 2
    "temperature_unit": "celsius",
    "ambient_temp": 30
  },

  "system_config": {
    "system_mode": "hybrid",              // on_grid | off_grid | hybrid | backup
    "battery_chemistry": "lifepo4",
    "expected_expansion_pct": 20,
    "critical_loads_only": false
  },

  "loads": [
    {
      "load_id": "uuid",
      "name": "Split AC 1.5 Ton",
      "category": "living_room_bedroom",
      "load_category": "hvac",
      "power_watts": 1500,
      "qty": 1,
      "hours_per_day": 6,
      "simultaneity_factor": 1.0,
      "known_pf": null,                   // null = use category default; else user float
      "source": "catalog",                // catalog | custom
      "catalog_equipment_id": "eq_ac_1_5t_inverter"
    }
  ],

  "overrides": {
    "aging_factor": null,                 // null = use constants.py default
    "design_margin": null,
    "wire_efficiency": null,
    "future_load_factor": null,
    "dod_max": null
  },

  "last_calculation_result": { /* Master Output Schema — see Part I of spec doc */ },

  "version_history": [
    {
      "edited_at": ISODate,
      "summary": "Added 2 loads, changed reserve days 1 → 2",
      "snapshot_ref": "optional — either full snapshot or diff, implementation choice"
    }
  ],

  "created_at": ISODate,
  "updated_at": ISODate,
  "last_opened_at": ISODate
}
```

### 2.2 `equipment_catalog`
```json
{
  "_id": "eq_ac_1_5t_inverter",
  "name": "Air conditioner (1.5 ton, inverter)",
  "category": "living_room_bedroom",
  "typical_watts_min": 1200,
  "typical_watts_max": 1800,
  "reference_watts": 1500,
  "load_category": "hvac",
  "source_note": "BEE/ISEER India reference — see feature-specs/02"
}
```
Seeded once from Unit 02's table; admin-editable later without touching any `projects` document (Invariant 4).

### 2.3 `battery_catalog`
```json
{
  "_id": "batt_generic_12v_100ah_lifepo4",
  "manufacturer": "generic",              // real manufacturer names added as curated later
  "model": "12V 100Ah LiFePO4",
  "voltage": 12,
  "ah_rating": 100,
  "rated_discharge_hours": 20,
  "chemistry": "lifepo4",
  "max_continuous_discharge_a": 100,
  "max_surge_discharge_a": 200,
  "peukert_exponent": 1.01,
  "max_recommended_parallel_strings": 4,
  "dimensions_mm": null,
  "weight_kg": null,
  "notes": "Seed placeholder — replace with real datasheet values as catalog is curated"
}
```

### 2.4 `inverter_catalog`
```json
{
  "_id": "inv_generic_5kva_hybrid",
  "manufacturer": "generic",
  "model": "5kVA Hybrid Inverter",
  "continuous_va": 5000,
  "continuous_w": 4000,
  "surge_va": 10000,
  "surge_duration_s": 5,
  "waveform": "pure_sine",
  "input_voltage_window": [40, 60],
  "efficiency_curve": [ [10, 0.85], [25, 0.92], [50, 0.95], [100, 0.93] ],
  "lvd_threshold_v": 42,
  "certifications": ["IEC62109"],
  "grid_tie_capable": true,
  "notes": "Seed placeholder — replace with real datasheet values as catalog is curated"
}
```

**Why four separate collections and not one:** `equipment_catalog`, `battery_catalog`, and `inverter_catalog` are admin-maintained reference data that changes independently of any project — embedding them in `projects` would mean every catalog correction requires touching every project document that referenced it. Keeping them separate means Step 8/10 above just *reads* a catalog entry by ID at calculation time; it never copies the whole spec into the project document except inside `last_calculation_result` (which is a point-in-time snapshot of the result, not a live reference).

---

## PART 3 — How It All Comes Together (end-to-end request flow)

```
1. User opens a project in the frontend → GET /projects/{id}
       → backend/projects/repository.py reads the `projects` document, returns it as-is
       → frontend renders loads, parameters, and (if present) last_calculation_result

2. User edits loads/parameters in the UI → these are held in frontend state until
   "Calculate" is clicked (no auto-save mid-edit, to avoid partial/invalid saves)

3. User clicks "Calculate" → POST /projects/{id}/calculate
       Request body: { loads[], parameters{}, overrides{}, chosen_battery_id?, chosen_inverter_id? }

       Backend route handler (backend/projects/router.py):
         a. Validates request body against Pydantic schema
         b. If chosen_battery_id / chosen_inverter_id provided → fetch from
            battery_catalog / inverter_catalog (Validate mode)
            Else → query catalogs for candidates matching the computed requirement
            (Recommend mode)
         c. Calls the pure calculation pipeline (Part 1 above) — this is the ONLY
            place backend/calculation/ functions are invoked
         d. Pipeline returns { ...results, hard_errors[], warnings[] }
         e. If hard_errors is non-empty → return 422 with hard_errors detail,
            DO NOT save this as a valid last_calculation_result
         f. If hard_errors is empty → save result into
            projects.last_calculation_result, append a version_history entry,
            update updated_at
         g. Return the Master Output Schema to the frontend

4. Frontend renders ResultsPage.jsx directly from the response — no recomputation,
   no reformatting of numbers, per architecture.md Invariant 1

5. User clicks "Export PDF" → POST /projects/{id}/report
       → backend/report/pdf_builder.py reads projects.last_calculation_result
         (does NOT recalculate — exports exactly what was last computed and saved)
       → ReportLab generates the PDF in the fixed light-mode style (ui-context.md)
       → streamed back to the frontend as a file download, not stored server-side

6. Dashboard tabs/filters → GET /projects?tab=recent&date_from=...&date_to=...&q=...
       → backend/projects/queries.py builds the MongoDB query (sort by last_opened_at
         for Recent, filter is_favorite for Favorites, filter updated_at != created_at
         for Edited, apply date-range + text search on top)
```

**The one rule that keeps this whole system trustworthy:** the calculation pipeline (Part 1) never touches MongoDB directly, and MongoDB never stores a calculation result that wasn't produced by that exact pipeline with zero `hard_errors`. Everything else in the app — dashboard, filters, PDF export — is just reading and displaying what that pipeline already validated.

---

## PART 4 — Build order this implies

Given this integration map, the dependency order is now explicit:

1. Unit 01 (constants) + Unit 02 (equipment catalog) — no dependencies, can be done in parallel
2. `backend/calculation/load.py` (Steps 1–2) — depends on Unit 01
3. `backend/calculation/battery.py` (Steps 3–8) — depends on Unit 01, needs a battery_catalog seed entry to test against
4. `backend/calculation/inverter.py` (Steps 9–10) — depends on Unit 01, needs an inverter_catalog seed entry to test against
5. `backend/calculation/cabling.py` (Step 11) — standalone, only needs I_avg as input, can be tested independently
6. `backend/calculation/validation.py` (Step 12) — depends on all of the above being callable
7. `backend/projects/router.py` `/calculate` route — wires Steps 1–12 together, first point MongoDB gets touched
8. Only after step 7 returns correct numbers against the spec doc's worked example → begin `frontend/project-workspace/` and `frontend/results/`