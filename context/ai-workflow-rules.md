# AI Workflow Rules

## Approach

Build this project incrementally using a spec-driven workflow. The six context files (`project-overview.md`, `architecture.md`, `ui-context.md`, `code-standards.md`, `ai-workflow-rules.md`, `progress-tracker.md`) and the engineering reference document (`battery_inverter_sizing_full_spec.md`) define what to build, how to build it, the visual system to follow, and the current state of progress. Always implement against these documents — do not infer, invent, or approximate product behavior, formulas, or design decisions from scratch. This is a real-world tool used by professionals for real installations, and everything discussed with the user is treated as a firm requirement, not a suggestion — see `project-overview.md`'s framing.

## Scoping Rules

- Work on one feature unit at a time.
- Prefer small, verifiable increments over large speculative changes.
- Do not combine unrelated system boundaries (as defined in `architecture.md`) in a single implementation step — e.g., do not touch `backend/calculation/` and `frontend/dashboard/` in the same unit.
- Do not implement anything listed under "Out of Scope" in `project-overview.md` (login/auth, live pricing, admin review queue, multi-currency, Excel export, real Share functionality) unless the user explicitly asks to bring it into scope first.

## When to Split Work

Split an implementation step if it combines:

- Frontend UI changes and backend calculation/API changes
- Changes to more than one `backend/` module defined in `architecture.md` (e.g., `backend/calculation/` and `backend/csv/` together)
- A new engineering formula or constraint that isn't yet defined in `battery_inverter_sizing_full_spec.md` — that must be resolved as a spec question first, not implemented as a guess
- UI work that touches both dashboard and project-workspace layouts at once
- Behavior not clearly defined in the context files

If a change cannot be verified end to end quickly, the scope is too broad — split it.

## Handling Missing Requirements

- Do not invent product behavior not defined in the context files.
- Do not invent or approximate an engineering formula, constraint, default value, or standards reference not already defined in `battery_inverter_sizing_full_spec.md` — flag it as an open question instead of guessing, since incorrect sizing math is a safety issue, not a cosmetic one.
- If a requirement is ambiguous, resolve it in the relevant context file before implementing.
- If a requirement is missing, add it as an open question in `progress-tracker.md` before continuing, and ask the user rather than assuming.

## Protected Files

Do not modify the following unless explicitly instructed:

- `components/ui/*` — generated shadcn/ui components (add new ones via the shadcn CLI, per `code-standards.md`)
- `battery_inverter_sizing_full_spec.md` — the engineering reference; formulas/constraints here are only changed when the user explicitly revises the engineering spec, never silently "corrected" during implementation
- Any third-party library internals

## Keeping Docs in Sync

Update the relevant context file whenever implementation changes:

- System architecture or boundaries → `architecture.md`
- Storage model or MongoDB collection structure → `architecture.md`
- Code conventions or standards → `code-standards.md`
- Feature scope (in or out) → `project-overview.md`
- Visual/design decisions (colors, layout patterns, component conventions) → `ui-context.md`
- Any engineering formula, constraint, or default value → `battery_inverter_sizing_full_spec.md`

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope.
2. No invariant defined in `architecture.md` was violated — in particular: the calculation engine still lives only in the backend, `hard_errors` still block a result from being returned, and no formula is duplicated across modules.
3. `progress-tracker.md` reflects the completed work.
4. The frontend build passes with no errors, and the backend starts and responds without errors.
5. If the unit touched the calculation engine, its output was checked against a manually worked example from `battery_inverter_sizing_full_spec.md` — not just "it ran without crashing."