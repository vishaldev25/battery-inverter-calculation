# Feature Spec: Unit 01 - Backend Engineering Constants

## Objective
Establish the foundational engineering data structures required for the calculation engine. This ensures all math logic (built later) references a single source of truth for standard values.

## Context to Read Before Starting
1. `context/battery_inverter_sizing_full_spec.md` (for the exact engineering numbers).
2. `context/code-standards.md` (for Python backend rules).

## Scope of Work
Create the file `backend/calculation/constants.py` and populate it with Python constants, dictionaries, or Enums representing the following data:

1. **Load Categories & Power Factors:** Default Power Factor (PF) values mapped to your specific load categories (Appliances, Electronics, Motors, Lights, Others).
2. **Surge Multipliers:** Standard starting/surge multipliers mapped to those same equipment categories.
3. **Temperature Correction Tables:** The IEEE 485 derating multiplier tables for both Celsius and Fahrenheit.
4. **Battery Chemistry Baselines:** Default Depth of Discharge (DOD) limits, nominal voltages, and typical efficiencies for different battery types (e.g., Lead-Acid, Lithium-ion).
5. **System Standards:** The standard DC system voltages (12V, 24V, 48V, etc.) and standard inverter efficiency defaults.

## Out of Scope
- **NO calculation logic or functions.** This file must only contain static data structures.
- **NO API endpoints or routing.** 
- **NO database schemas or Pydantic models** (that will be Unit 02).

## Acceptance Criteria
- `constants.py` is created inside `backend/calculation/`.
- All values strictly map to the definitions in `battery_inverter_sizing_full_spec.md`. No estimates or "dummy data" are used.
- The file uses standard Python typing and docstrings for clarity.