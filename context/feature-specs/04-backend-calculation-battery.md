# Feature Spec: 04-backend-calculation-battery

## Objective
Implement the pure mathematical logic for **Module 2 — Battery Bank Sizing** of the calculation engine. This module takes the energy and power demands calculated in Module 1, applies IEEE 485 and IEEE 1013 sizing methodologies, and outputs the required battery capacity (Ah) and the physical string configuration (Series/Parallel counts).

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (Specifically **Part D - BATTERY BANK SIZING (IEEE 485 / IEEE 1013 / IEEE 1188)**).
2. `context/calculation-engine-and-data-model.md` (Specifically **Part 1, Steps 3 through 8**).

## Scope of Work
Create the file `backend/calculation/battery.py` containing a pure, deterministic function (e.g., `calculate_battery_bank(...) -> dict`).

Implement the following sizing logic precisely as defined in the spec:
1. **Ah Demand:** Calculate base Ah required for daily energy and requested days of autonomy at the system DC voltage.
2. **Temperature Correction ($k_t$):** Linearly interpolate the IEEE 485 temperature table based on the design ambient temperature.
3. **Full Correction Chain:** Calculate $Ah_{required}$ incorporating $k_t$, battery round-trip efficiency, wire efficiency, aging factor, and maximum depth of discharge (DOD).
4. **Peukert Correction:** Calculate the actual usable capacity based on the continuous discharge rate ($I_{avg}$), adjusting for the Peukert exponent if necessary.
5. **String Solver (Series/Parallel):**
   - Calculate $N_{series}$ (System Voltage / Battery Voltage). *Must be a positive integer.*
   - Calculate $N_{parallel}$ driven by the *maximum* of either the Ah capacity requirement OR the maximum continuous discharge current limit of the chosen battery.
6. **Validation & Advisory Flags:** 
   - **Hard Errors:** Throw an error if $N_{series}$ is not an integer. Throw an error if `ambient_temp_c < 0` and chemistry is `lifepo4` (safety constraint).
   - **Warnings:** Flag if `ambient_temp_c > 30` (cycle-life derating). Flag if chemistry is `flooded_lead_acid` (ventilation required). Flag if chemistry is `lifepo4` (BMS mandatory). Flag if $N_{parallel} > 4$ (current-sharing risk).

## Out of Scope
- **NO Inverter or Cable Sizing:** That will be Units 05 and 06.
- **NO Database Calls:** This function must rely entirely on the parameters passed into it and `constants.py`.
- **NO API Routes:** Do not modify `router.py`.

## Acceptance Criteria
- `backend/calculation/battery.py` is created.
- The function is completely pure (no side-effects, no database imports).
- Math strictly follows the formulas provided in the engineering specification.
- Return payload strictly separates computed numeric values, a `warnings` list of strings, and a `hard_errors` list of strings.