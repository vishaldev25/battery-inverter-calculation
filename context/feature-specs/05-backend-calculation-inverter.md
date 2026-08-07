# Feature Spec: 05-backend-calculation-inverter

## Objective
Implement the pure mathematical logic for **Module 3 — Inverter Sizing** of the calculation engine. This module takes the peak apparent power, surge requirements, and system parameters calculated in previous modules, matches them against inverter catalog specifications or baseline defaults, and validates continuous and surge capabilities, waveform requirements, and voltage windows.

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (Specifically **Part E - INVERTER SIZING**).
2. `context/calculation-engine-and-data-model.md` (Specifically **Part 1, Steps 9 & 10** to understand inputs and outputs).

## Scope of Work
Create the file `backend/calculation/inverter.py` containing a pure, deterministic function (e.g., `calculate_inverter_sizing(...) -> dict`).

Implement the following formulas and checks precisely as defined in the spec:
1. **Continuous Apparent Power ($S_{continuous}$):** Calculate required continuous VA incorporating the future expansion factor ($F_{future} = 0.20$ default).
2. **Surge Apparent Power ($S_{surge}$):** Validate against the worst-case surge VA calculated in Module 1.
3. **DC Input Current ($I_{DC,cont}$):** Calculate the inverter DC input current under continuous load, utilizing the efficiency at the given load fraction.
4. **Selection & Validation Gates:**
   - **Continuous Capacity Check:** Inverter continuous VA rating must be $\ge S_{continuous}$.
   - **Surge Capacity Check:** Inverter surge VA rating must be $\ge S_{surge}$.
   - **Waveform Validation:** If any load category includes motors or sensitive electronics, waveform must be pure sine wave (throw a hard error or warning depending on strictness; spec mandates pure sine for motor/IT loads).
   - **Input Voltage Window Check:** System DC voltage must fall within the inverter's specified input operating voltage window.
5. **Validation & Advisory Flags:**
   - **Hard Errors:** Throw an error if continuous VA or surge VA of the candidate inverter is insufficient. Throw an error if input voltage falls outside the operating window.
   - **Warnings:** Flag if efficiency curves or temperature derating limits are approached.

## Out of Scope
- **NO Cable or Fuse Sizing:** That will be Unit 06.
- **NO Database Calls:** This function must rely entirely on the parameters passed into it and `constants.py`.
- **NO API Routes:** Do not modify `router.py`.

## Acceptance Criteria
- `backend/calculation/inverter.py` is created.
- The function is completely pure (no side-effects, no database imports).
- Math strictly follows the formulas $S_{continuous} = S_{peak} \times (1 + F_{future})$, etc.
- Return payload strictly separates computed numeric values, a `warnings` list of strings, and a `hard_errors` list of strings.