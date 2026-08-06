# AI Entry Point — Inverter and Battery Sizing Calculation

Paste this entire file (or point your AI tool at it) at the start of every new session, before asking it to build anything.

## Read these files in order before implementing or making any decision

1. `context/project-overview.md` — product definition, goals, features, and scope. Includes the role instruction: act as an industry professional experienced in both electrical engineering and web/UI development.
2. `context/architecture.md` — system structure, folder boundaries, MongoDB storage model, and invariants (rules that must never be violated).
3. `context/ui-context.md` — theme, colors (light + dark), typography, layout patterns, and component conventions.
4. `context/code-standards.md` — implementation rules (JavaScript frontend, FastAPI/Python backend — no TypeScript).
5. `context/ai-workflow-rules.md` — development workflow, scoping rules, and how to handle missing or ambiguous requirements.
6. `context/battery_inverter_sizing_full_spec.md` — the full engineering reference (formulas, constraints, standards). Every calculation formula must trace back to this document.
7. `context/calculation-engine-and-data-model.md` — the exact execution order of the calculation pipeline and the MongoDB collection schemas. Read this before touching `backend/calculation/` or any database model.
8. `context/progress-tracker.md` — current phase, completed work, open questions, and next steps.
9. `context/feature-specs/NN-*.md` — the specific unit being built in this session (only read the one relevant to the current task).

## Rules for this session

- Work on **one unit at a time**, exactly as scoped in its `feature-specs/` file. Do not go beyond that scope.
- Do not invent or approximate any engineering formula, default value, or constraint not already defined in `battery_inverter_sizing_full_spec.md` or `calculation-engine-and-data-model.md`. If something is missing, say so — do not guess. Incorrect sizing math is a safety issue, not a cosmetic one.
- Do not implement anything listed as "Out of Scope" in `project-overview.md` unless explicitly asked.
- Follow `code-standards.md` exactly — plain JavaScript (no TypeScript) on the frontend, FastAPI + Pydantic on the backend, no formula duplicated across files.
- Follow `ui-context.md` exactly for any UI work — both light and dark mode, token-based colors only, no hardcoded hex values.

## After this session

Update `context/progress-tracker.md`:
- Move the completed unit from "Next Up" to "Completed"
- Note anything unresolved under "Open Questions"
- Add a short note under "Session Notes" — enough for a fresh session (or a different developer) to resume without re-reading everything from scratch

If implementation changes the architecture, scope, formulas, or standards documented in the context files, update the relevant file before continuing — do not let the code and the documentation drift apart.