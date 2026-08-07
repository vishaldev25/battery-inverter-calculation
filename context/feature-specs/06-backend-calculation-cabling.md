# Feature Spec: 06-backend-calculation-cabling

## Objective
Implement the pure mathematical logic for **Module 4 — Cable & Protection Sizing** of the calculation engine. This module takes the continuous DC current calculated in the inverter module and applies NEC (National Electrical Code) standards to determine the minimum cable ampacity, allowable voltage drop, and required overcurrent protection (fusing).

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (Specifically **Part F - CABLE & PROTECTION SIZING (NEC / IEC 60364)**).
2. `context/calculation-engine-and-data-model.md` (Specifically **Part 1, Step 11** to understand inputs and outputs).

## Scope of Work
Create the file `backend/calculation/cabling.py` containing a pure, deterministic function (e.g., `calculate_cabling_and_protection(...) -> dict`).

Implement the following formulas and checks precisely as defined in the spec:
1. **Design Current ($I_{design}$):** Apply the NEC 210.19/215.2 continuous-load factor ($1.25 \times I_{continuous}$). This is a hard rule, not an optional margin.
2. **Voltage Drop ($V_{drop}$):** Calculate voltage drop given the cable length ($L$) and resistance ($R_{cable}$). Validate that it is $\le 0.02\text{–}0.03 \times V_{bank,actual}$ (2–3%).
3. **Overcurrent Protection ($I_{fuse}$):** Calculate required fuse rating ($1.25 \times I_{continuous}$).
4. **Validation & Advisory Flags:**
   - **Hard Errors:** Throw an error if the chosen cable gauge cannot support the $I_{design}$ ampacity or if it fails the 3% voltage drop constraint.
   - **Warnings:** Flag the mandatory requirement for an accessible battery disconnect switch (NEC 690.13). Flag the requirement for string-level fusing if the battery bank has multiple parallel strings. Flag system and equipment grounding requirements.

## Out of Scope
- **NO Database Calls:** This function must rely entirely on the parameters passed into it and `constants.py`.
- **NO API Routes:** Do not modify `router.py`.
- **NO Cross-Module Validation:** The final sanity checks combining all modules will happen in Feature 07 (`validation.py`).

## Acceptance Criteria
- `backend/calculation/cabling.py` is created.
- The function is completely pure (no side-effects, no database imports).
- Math strictly follows the $1.25 \times I_{continuous}$ NEC rules and standard voltage drop formulas.
- Return payload strictly separates computed numeric values, a `warnings` list of strings, and a `hard_errors` list of strings.