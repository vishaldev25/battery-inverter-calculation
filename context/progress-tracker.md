# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase
- In progress: Phase 1 - Project Setup & Initial Infrastructure

## Current Goal
- Transition from static constants to establishing the data models (Pydantic) for the MongoDB collections.

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

## In Progress
- **Feature 02 (Backend Data Models):** Defining the database schemas and data validation layer for MongoDB collections.

## Next Up
- **Feature 02 (Backend Data Models):** Create the Pydantic models in `backend/projects/models.py` and `backend/catalog/*.py` to define the shapes for our four MongoDB collections (`projects`, `equipment_catalog`, `battery_catalog`, `inverter_catalog`) based on the data model spec.

## Open Questions
- None at present.

## Architecture Decisions
- **Frontend Typing:** Strictly adhering to Plain JavaScript with JSDoc comments where needed, explicitly rejecting TypeScript per `code-standards.md`.
- **CSS Framework:** Adopted Tailwind v4 (latest standard) meaning no `tailwind.config.js` is used; all theme mapping is strictly controlled via `src/index.css`.
- **Theme Variables:** Directly mapped the premium engineering-software UI tokens (e.g., `#0B0E14` for dark background, `#3B82F6` for primary accent) into the CSS root variables. Cards will use the standard `rounded-xl` (12px) per `ui-context.md`.
- **Git Strategy:** Utilizing feature branch workflows; Pull Requests into `main` trigger CodeRabbit automated code reviews.
- **Backend Architecture:** Created strict folder separation (`calculation/`, `projects/`, etc.) per `code-standards.md` to ensure pure functions and API logic do not mix.
- **Database Driver:** Using `pymongo` (`AsyncMongoClient`) for fully asynchronous non-blocking interactions with MongoDB, adapting to modern ecosystem standards.
- **Data Layers (Feature 01):** Decided to keep generic, immutable IEEE/NEC engineering defaults hardcoded in `constants.py` as a fail-safe baseline, while dynamic manufacturer-specific equipment specs will be stored in MongoDB for easy admin updates.

## Session Notes
- Both `/frontend` and `/backend` foundations are 100% complete and version-controlled.
- Virtual environment `venv` created inside `/backend`. Must be activated before running backend servers or installing new pip packages.
- Overcame PowerShell-specific folder creation quirks; architecture is stable. 
- Feature 01 is complete. We now have our foundational math constants locked in.