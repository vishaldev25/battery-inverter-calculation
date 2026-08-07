# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase
- In progress: Phase 2 - Calculation Engine (Phase 1 Foundation complete)

## Current Goal
- Implement the pure mathematical functions of the calculation engine, moving to battery bank sizing constraints.

## Completed
- **Infrastructure:** Initialized frontend with React + Vite (Plain JavaScript, no TypeScript).
- **Infrastructure:** Installed and configured Tailwind CSS v4 using the `@tailwindcss/vite` plugin (legacy PostCSS configs removed).
- **Infrastructure:** Initialized shadcn/ui and installed base components (`card`, `button`, `input`, `label`, `select`).
- **Infrastructure:** Injected custom CSS variables (dark/light mode tokens like `--bg-surface`, `--accent-primary`, etc.) into `src/index.css`.
- **Infrastructure:** Configured Vite path aliases (`@/`) in `jsconfig.json` and `vite.config.js`.
- **Infrastructure:** Initialized Git repository and pushed initial code for CodeRabbit PR integration.
- **Infrastructure:** Created `/backend` directory and Python virtual environment (`venv`).
- **Infrastructure:** Installed required backend dependencies (`fastapi[standard]`, `pydantic`, `pymongo`, `pandas`, `reportlab`) and generated `requirements.txt`.
- **Infrastructure:** Scaffolded standard backend module folders (`calculation`, `catalog`, `csv`, `projects`, `report`) and `__init__.py` files via PowerShell.
- **Feature 01 (Backend Constants):** Created `backend/calculation/constants.py` with strict IEEE/NEC standard engineering defaults (Power Factors, Surge Multipliers, Battery Chemistry limits, Temp correction).
- **Feature 02 (Backend Data Models):** Created Pydantic models in `backend/projects/models.py` and `backend/catalog/models.py` to define the exact shapes of MongoDB collections (`projects`, `equipment_catalog`, `battery_catalog`, `inverter_catalog`).
- **Feature 03 (Backend Calculation):** Created `backend/calculation/load.py` to aggregate `LoadItem` data, apply constants, and calculate Peak VA, Surge VA, and Daily Energy.

## In Progress
- **Feature 04 (Backend Calculation):** Implementing battery bank sizing (`battery.py`).

## Next Up
- **Feature 04 (Backend Calculation):** Create `backend/calculation/battery.py` to calculate Ah requirements, apply Peukert's law, temperature corrections (IEEE 485), and solve for series/parallel string configurations.

## Open Questions
- None at present.

## Architecture Decisions
- **Frontend Typing:** Strictly adhering to Plain JavaScript with JSDoc comments where needed, explicitly rejecting TypeScript per `code-standards.md`.
- **CSS Framework:** Adopted Tailwind v4 (latest standard) meaning no `tailwind.config.js` is used; all theme mapping is strictly controlled via `src/index.css`.
- **Theme Variables:** Directly mapped the premium engineering-software UI tokens (e.g., `#0B0E14` for dark background, `#3B82F6` for primary accent) into the CSS root variables. Cards will use the standard `rounded-xl` (12px) per `ui-context.md`.
- **Git Strategy:** Utilizing feature branch workflows; Pull Requests into `main` trigger CodeRabbit automated code reviews.
- **Backend Architecture:** Created strict folder separation (`calculation/`, `projects/`, etc.) per `code-standards.md` to ensure pure functions and API logic do not mix.
- **Database Driver:** Using `pymongo` (`AsyncMongoClient`) for fully asynchronous non-blocking interactions with MongoDB, adapting to modern ecosystem standards.
- **Data Layers (Feature 01 & 02):** Decided to keep generic, immutable IEEE/NEC engineering defaults hardcoded in `constants.py` as a fail-safe baseline, while dynamic manufacturer-specific equipment specs and user project configurations are strictly typed with Pydantic and stored in MongoDB.
- **Calculation Engine (Feature 03):** Established the pure, deterministic response schema for calculation modules, strictly separating `warnings` from `hard_errors` to ensure invalid constraints block output rendering.

## Session Notes
- Both `/frontend` and `/backend` foundations are 100% complete and version-controlled.
- Virtual environment `venv` created inside `/backend`. Must be activated before running backend servers or installing new pip packages.
- Features 01, 02, and 03 are complete. Load characterization module is locked in.
- Proceeding through Phase 2 (Calculation Engine) sequentially.