# Feature Spec: 03-backend-calculation-load

## Objective
Implement the pure mathematical logic for **Module 1 — Load Characterization** of the calculation engine. This module takes a list of validated `LoadItem` objects, applies the engineering constants (from Unit 01), and calculates the system's daily energy demand, peak apparent power (VA), and worst-case surge demand (VA).

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (Specifically **Part B - Load Characterization** and **Part C - Power Factor & Surge Table**).
2. `context/calculation-engine-and-data-model.md` (Specifically **Part 1, Steps 1 & 2** to understand inputs and outputs).

## Scope of Work
Create the file `backend/calculation/load.py` containing a pure, deterministic function (e.g., `calculate_load_profile(loads: List[LoadItem]) -> dict`).

Implement the following formulas precisely as defined in the spec:
1. **Daily Energy ($E_{day}$):** Calculate total Watt-hours per day incorporating the simultaneity factor.
2. **Peak Real Power ($P_{peak}$):** Calculate concurrent Watts.
3. **Peak Apparent Power ($S_{peak}$):** Calculate concurrent VA using the appropriate power factors (or standard defaults based on `LoadCategory`).
4. **Surge Apparent Power ($S_{surge}$):** Calculate the worst-case surge by evaluating every motor-type load individually (Motor Surge + Background Loads), finding the maximum possible value.
5. **Validation & Advisory Flags:** 
    - Output a `hard_errors` list if any load has `<= 0` watts or `> 24` hours.
    - Output a `warnings` list if no diversity factor is applied across the whole system.

## Out of Scope
- **NO Battery or Inverter Sizing:** That will be Units 04 and 05.
- **NO Database Calls:** This function must rely entirely on the input `loads` list and `constants.py`.
- **NO API Routes:** Do not create the `/calculate` FastAPI endpoint yet.

## Acceptance Criteria
- `backend/calculation/load.py` is created.
- The function is completely pure (no side-effects, no database imports).
- Math strictly follows the formulas $E_i = P_i \times qty_i \times t_i \times SF_i$, etc.
- Return payload strictly separates computed numeric values, a `warnings` list of strings, and a `hard_errors` list of strings.