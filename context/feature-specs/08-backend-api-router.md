# Feature Spec: 08-backend-api-router

## Objective
Implement the FastAPI routing layer that connects the frontend to the pure calculation engine. This endpoint will receive the `Project` payload, execute the mathematical modules (Features 03-07) in strict sequence, and return the comprehensive master output schema.

## Context to Read Before Starting
1. `context/calculation-engine-and-data-model.md` (Specifically **Part 1: The Formula Execution Sheet** and **Part 3: How It All Comes Together**).
2. `context/code-standards.md` (Specifically **Backend (FastAPI / Python)** and **API Routes**).

## Scope of Work
Create the file `backend/projects/router.py` (and eventually wire it into a `backend/main.py` entrypoint).

1. **POST `/api/projects/calculate` Endpoint:**
   - **Input:** Accepts a Pydantic payload representing the calculation inputs (loads, parameters, selected battery/inverter specs).
   - **Execution Sequence:** 
     1. Call `calculate_load_profile()`
     2. Call `calculate_battery_bank()`
     3. Call `calculate_inverter_sizing()`
     4. Call `calculate_cabling_and_protection()`
     5. Call `validate_system_design()`
   - **Output:** Returns a structured JSON response matching the Master Output Schema (Part I of the sizing spec).
2. **Error Handling:** Ensure that if any `hard_errors` are generated in steps 1-4, the pipeline gracefully aggregates them and returns the error payload without crashing downstream functions.

## Out of Scope
- **NO Database Writes Yet:** For this specific unit, the `/calculate` endpoint functions as a stateless calculator. Saving the project to MongoDB will be a separate CRUD route later.
- **NO Frontend Code:** This is strictly backend API scaffolding.

## Acceptance Criteria
- `backend/projects/router.py` is created with the `/calculate` endpoint.
- The route successfully imports and executes the pure functions from `backend/calculation/`.
- Data is strictly validated using Pydantic before hitting the calculation engine.