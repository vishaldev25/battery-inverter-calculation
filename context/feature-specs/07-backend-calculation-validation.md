# Feature Spec: 07-backend-calculation-validation

## Objective
Implement the pure mathematical logic for **Module 5 — Cross-Module Validation** of the calculation engine. This module takes the outputs from the Load, Battery, Inverter, and Cabling modules and evaluates system-level constraints to ensure no combination of independently valid components creates an unsafe or invalid overall design.

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (Specifically **Part G - CROSS-MODULE VALIDATION RULES**).
2. `context/calculation-engine-and-data-model.md` (Specifically **Part 1, Step 12**).

## Scope of Work
Create the file `backend/calculation/validation.py` containing a pure, deterministic function (e.g., `validate_system_design(...) -> dict`).

Implement the following cross-module checks precisely as defined in the spec:
1. **Voltage Consistency:** Verify that the actual battery bank voltage (`v_bank_actual`) exactly matches the system design voltage (`bank_voltage_nominal`) and the inverter's required input voltage.
2. **Current Path / Surge Check:** Verify that the required system surge current ($I_{surge}$) does not exceed the weakest link in the chain: the battery bank's maximum surge rating, the inverter's surge limit, and the cable/fuse capacity.
3. **Recharge Feasibility:** Check if the available charging current (if provided) can replenish the discharged Ah within the available daylight/run window (Formula: $T_{recharge} = (Ah_{discharged} \times 1.1) / I_{charge,available}$).
4. **Validation & Advisory Flags:**
   - **Hard Errors:** Throw an error if voltages are mismatched across components, or if the system surge current exceeds component limits.
   - **Warnings:** Flag if recharge feasibility fails (autonomy days cannot be replenished) or if thermal co-location checks (ventilation/heat dissipation) should be reviewed by the engineer.

## Out of Scope
- **NO Database Calls:** This function must rely entirely on the parameters and module outputs passed into it.
- **NO API Routes:** Do not modify `router.py` yet (that will be Unit 08).
- **NO Calculation logic:** Do not recalculate Ah or VA; only evaluate the combined outputs from modules 1-4.

## Acceptance Criteria
- `backend/calculation/validation.py` is created.
- The function is completely pure (no side-effects, no database imports).
- It returns a master object aggregating all results, along with a unified, deduplicated list of `warnings` and `hard_errors`.