# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- In progress: Phase 1 - Project Setup & Initial Infrastructure

## Current Goal

- Transition from infrastructure setup to implementing the core engineering constants for the backend calculation engine.

## Completed

- Initialized frontend with React + Vite (Plain JavaScript, no TypeScript).
- Installed and configured Tailwind CSS v4 using the `@tailwindcss/vite` plugin (legacy PostCSS configs removed).
- Initialized shadcn/ui and installed base components (`card`, `button`, `input`, `label`, `select`).
- Injected custom CSS variables (dark/light mode tokens like `--bg-surface`, `--accent-primary`, etc.) into `src/index.css`.
- Configured Vite path aliases (`@/`) in `jsconfig.json` and `vite.config.js`.
- Initialized Git repository, created `main` and `development` branches, and pushed initial code for CodeRabbit PR integration.
- Created `/backend` directory and Python virtual environment (`venv`).
- Installed required backend dependencies (`fastapi[standard]`, `pydantic`, `motor`, `pandas`, `reportlab`) and generated `requirements.txt`.
- Scaffolded standard backend module folders (`calculation`, `catalog`, `csv`, `projects`, `report`) and `__init__.py` files via PowerShell.

## In Progress

- Building the core calculation engine constants.

## Next Up

- **Unit 01 (Backend)**: Create `backend/calculation/constants.py` to define core server-side engineering constants (power factors, surge multipliers, temperature correction tables) exactly as outlined in the sizing spec.

## Open Questions

- None at present.

## Architecture Decisions

- **Frontend Typing:** Strictly adhering to Plain JavaScript with JSDoc comments where needed, explicitly rejecting TypeScript per `code-standards.md`.
- **CSS Framework:** Adopted Tailwind v4 (latest standard) meaning no `tailwind.config.js` is used; all theme mapping is strictly controlled via `src/index.css`.
- **Theme Variables:** Directly mapped the premium engineering-software UI tokens (e.g., `#0B0E14` for dark background, `#3B82F6` for primary accent) into the CSS root variables. Cards will use the standard `rounded-xl` (12px) per `ui-context.md`.
- **Git Strategy:** Working exclusively on the `development` branch; PRs to `main` will trigger CodeRabbit automated reviews.
- **Backend Architecture:** Created strict folder separation (`calculation/`, `projects/`, etc.) per `code-standards.md` to ensure pure functions and API logic do not mix.
- **Database Driver:** Installed `motor` to ensure fully asynchronous non-blocking interactions with MongoDB.

## Session Notes

- Both `/frontend` and `/backend` foundations are 100% complete and version-controlled.
- Virtual environment `venv` created inside `/backend`. Must be activated before running backend servers or installing new pip packages.
- Overcame PowerShell-specific folder creation quirks; architecture is stable. Ready to begin writing actual calculation logic based on IEEE/NEC standards.