# Feature Spec: 02-backend-data-models (Pydantic)

## Objective
Establish the strict data validation layer for the backend using Pydantic. This defines the exact shapes of the four MongoDB collections, ensuring that no invalid data can ever be saved to the database or passed into the calculation engine.

## Context to Read Before Starting
1. `context/calculation-engine-and-data-model.md` (specifically Part 2 - MongoDB Collections schemas).
2. `context/architecture.md` (Storage Model boundaries).
3. `context/battery_inverter_sizing_full_spec.md` (for required fields like voltage, surge VA, etc.).

## Scope of Work
Create the Pydantic models for our MongoDB collections. 

1. **Projects Model (`backend/projects/models.py`):**
   - Create the `LoadItem` sub-schema (name, watts, qty, hours, category, simultaneity, etc.).
   - Create the `ProjectParameters` sub-schema (voltage, region, temp unit, etc.).
   - Create the `Project` root schema containing metadata (name, timestamps, status), a list of `LoadItem`s, parameters, and a placeholder for `last_calculation_result`.

2. **Catalog Models (`backend/catalog/models.py`):**
   - Create the `EquipmentCatalog` schema (name, category, default watts, default PF).
   - Create the `BatteryCatalog` schema (make, model, chemistry, voltage, Ah, max discharge amps, limits).
   - Create the `InverterCatalog` schema (make, model, continuous VA, surge VA, waveform, efficiency curve).

## Out of Scope
- **NO Database Connection Logic:** Do not write the PyMongo client or database connection strings yet.
- **NO API Routes:** Do not create `router.py` or FastAPI endpoints.
- **NO Calculation Logic:** These are purely data schemas (shapes), not math operations.

## Acceptance Criteria
- Files are created in their respective boundary folders (`backend/projects/models.py` and `backend/catalog/models.py`).
- All models strictly match the shapes defined in `calculation-engine-and-data-model.md`.
- `datetime` is used for timestamps, and Enums from `01-backend-constants` (e.g., `LoadCategory`, `BatteryChemistry`) are reused where appropriate to enforce consistency.
- Pydantic `Field` constraints are used where obvious (e.g., `ge=0` for negative-forbidden values).