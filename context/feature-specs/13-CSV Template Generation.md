# Feature 13 — CSV Template Generation, Parsing & Row-Level Validation

**Status:** Spec for review — no code yet, per workflow rules.
**Boundary:** `backend/csv/` only (`models.py`, `template.py`, `parser.py`, `validator.py` — all new). Does not touch `backend/calculation/`, `backend/projects/`, `backend/catalog/`, or any frontend directory — single system boundary per `architecture.md`.
**Depends on:** Feature 02 (`backend/projects/models.py` — `LoadItem`, verified against real source in this review pass), Feature 01 (`backend/calculation/constants.py` — `LoadCategory` enum, verified against real source in this review pass).

---

## 1. What this unit delivers

`architecture.md`'s system boundary for this module:
> `backend/csv/` — Owns CSV template generation, parsing (Pandas), and row-level validation (valid / invalid / missing), producing a clear per-row report before any data reaches the calculation module.

Three things, kept in one unit because they're the same system boundary and each step is untestable without the previous one:

1. **Template generation** — a downloadable CSV with the correct headers and one example row, so a user's upload has a fighting chance of matching what the validator expects.
2. **Parsing** — Pandas reads uploaded CSV bytes into a DataFrame, with structural checks (right headers present, not an empty file) kept separate from field-level validation.
3. **Row-level validation** — every row run through the *real* `LoadItem` Pydantic model (not a parallel schema), producing a clear valid/invalid split per Architecture Invariant 8.

**Explicitly NOT in this unit** (per `ai-workflow-rules.md` splitting rules):
- Wiring a `POST /projects/{id}/loads/csv-upload` route into `backend/projects/router.py` — that touches a second backend module (`backend/projects/`) in the same step, which the split rule forbids. Separate unit, after this one.
- Resolving blank `power_factor` cells into a real calculated PF value — that's `backend/calculation/load.py`'s job (already built, Features 03–07). This unit's job stops at "the row is structurally valid and passes `LoadItem`," not "the row is fully resolved for calculation."
- Any frontend work (upload button, template download link) — backend-only.

---

## 2. Verified field mapping

Checked directly against your pasted source files — nothing below is inferred from the spec doc's naming.

**Source: `backend/projects/models.py` → `LoadItem`**

| CSV column | LoadItem field | Type | Constraint (as coded) | Blank-cell behavior |
|---|---|---|---|---|
| `name` | `name` | `str` | required, non-empty | invalid row |
| `category` | `category` | `LoadCategory` enum | must match an enum value below | Pydantic default (`RESISTIVE`) — same as manual entry leaving the field at its default |
| `quantity` | `quantity` | `int` | `>= 1` | Pydantic default (`1`) |
| `nominal_watts` | `nominal_watts` | `float` | `> 0` | invalid row — this is the one required numeric field, no default exists |
| `power_factor` | `power_factor` | `float` | `> 0` and `<= 1.0` | Pydantic default (`1.0`) |
| `daily_hours` | `daily_hours` | `float` | `>= 0.0` and `<= 24.0` | Pydantic default (`1.0`) |
| `surge_multiplier` | `surge_multiplier` | `float` | `>= 1.0` | Pydantic default (`1.0`) |
| `is_concurrent` | `is_concurrent` | `bool` | — | Pydantic default (`True`) |

`id` is **not** a CSV column — it's a client-assigned identifier per `LoadItem`'s own docstring ("Unique client-side item identifier"), not something a CSV row provides. It stays unset (`None`) for every row this module produces.

**Source: `backend/calculation/constants.py` → `LoadCategory` enum values (case-sensitive, exact match required)**
```text
resistive, lighting_incandescent, lighting_led, motor_pump,
motor_compressor, electronics_it, hvac, heating_resistive
```
A `category` cell that doesn't match one of these exactly (including case) is an **invalid row** with a specific "unknown category" reason — never silently mapped to a nearby value or defaulted.

---

## 3. Two confirmed naming divergences from the sizing-spec doc (informational, not bugs)

1. `battery_inverter_sizing_full_spec.md` Part B1 defines `simultaneity_factor` (float 0–1). The real, already-shipped `LoadItem` (Feature 02) instead has `is_concurrent` (bool). This unit validates against the **real model**, per `ai-workflow-rules.md`'s instruction to implement against the context files as the living source — not against the engineering-formula doc's field naming, which governs formulas/constants, not schema field names. No change is made here; this is carried forward as-is.
2. Spec doc's `power_watts` = real model's `nominal_watts`. Same situation — already shipped, followed as-is.

Neither is treated as something to "fix" in this unit — that would be a `backend/projects/models.py` change, a different system boundary, out of scope here per the split rule.

---

## 4. Files to create

### 4.1 `backend/csv/models.py` — response schema
```python
CsvRowError:
    row_number: int        # 1-indexed, matching spreadsheet row (header = row 1, first data row = 2)
    raw_data: dict          # original row values exactly as submitted
    errors: list[str]       # specific, field-level reasons, plain text (not raw Pydantic error objects)

CsvValidationResult:
    total_rows: int
    valid_count: int
    invalid_count: int
    valid_rows: list[LoadItem]
    invalid_rows: list[CsvRowError]
```

### 4.2 `backend/csv/template.py`
- `generate_template_csv() -> bytes`
- Header row = the 8 CSV columns in §2, in that order.
- One example data row included (a `resistive` load, `power_factor` cell left blank to visibly demonstrate the "blank = category default applies downstream" pattern).
- Static/deterministic — no DB call, no calculation call, matches Architecture's "pure" expectation for anything not explicitly stateful.

### 4.3 `backend/csv/parser.py`
- `parse_csv_bytes(file_bytes: bytes) -> pandas.DataFrame`
- Structural checks only, each with a specific, distinct error (not a generic "something went wrong," per `code-standards.md`'s API Routes rule):
  - File has zero data rows → structural error, not silently "0 valid rows."
  - Header row doesn't match the expected 8 columns (missing or unexpected columns) → structural error, distinct from a row-level validation error.
- Does **not** perform any field-level validation itself — that stays entirely in `validator.py`, keeping parsing and validation as separate, single-purpose concerns per `code-standards.md`'s "do not mix unrelated concerns" rule.

### 4.4 `backend/csv/validator.py`
- `validate_rows(df: pandas.DataFrame) -> CsvValidationResult`
- Per row:
  1. Build a dict from the row.
  2. Strip out any cell that is blank/NaN for `category`, `quantity`, `power_factor`, `daily_hours`, `surge_multiplier`, `is_concurrent` **before** constructing `LoadItem`, so Pydantic's own field defaults apply — this is not a separate default table invented here, it's the same defaulting `LoadItem` already does for manual entry (parity, not new logic).
  3. Attempt `LoadItem(**row_dict)`.
     - Success → append to `valid_rows`.
     - `pydantic.ValidationError` → translate each field error into a plain string, append a `CsvRowError` to `invalid_rows`.
- Row numbering: first data row (immediately after the header) = row 2, matching how a user would count rows if they opened the file in a spreadsheet editor.

---

## 5. Decisions (resolved)

1. **Validate against the real `LoadItem`, not a parallel CSV-specific schema.** Non-negotiable per Architecture Invariant 8 ("every accepted row must have passed the same Pydantic validation as manually entered data").
2. **Blank optional cells → Pydantic defaults, not invented CSV-specific defaults.** Keeps behavior identical to a user leaving a field blank in the manual-entry form.
3. **Structural errors (bad headers, empty file) are distinct from row-level validation errors**, and live in `parser.py` not `validator.py` — a malformed file never reaches per-row validation at all.
4. **`category` matching is exact-string, case-sensitive, against the real enum** — no fuzzy matching, no "closest guess."

---

## 6. Open questions

None outstanding — unlike Feature 12, every field/type/constraint needed for this unit was directly available in the two files you pasted, so there's nothing here requiring a guess or a deferred decision. If anything comes up mid-implementation (e.g. how Pandas represents blank cells for booleans vs. floats, which could affect the "strip blank cells" step in §4.4), it'll be flagged before proceeding rather than assumed.

---

## 7. Verification plan (per `ai-workflow-rules.md`'s "Before Moving to the Next Unit")

- Template: generate it, confirm the header row exactly matches the 8 `LoadItem`-mapped columns in §2, confirm the example row itself passes `validator.py` unchanged (the template must not ship an example that would fail its own validation).
- Parser: confirm an empty file and a bad-header file each produce their own specific structural error (not the same generic message); confirm a well-formed file with valid rows produces a DataFrame with the expected row count.
- Validator: run against a small hand-built CSV containing at least one of each — a fully valid row, a row with a bad `category` value, a row with `nominal_watts <= 0`, a row with `nominal_watts` missing entirely, and a row with `power_factor`/`is_concurrent`/`daily_hours` left blank (confirming Pydantic defaults apply correctly, not silently omitted). Confirm `valid_count + invalid_count == total_rows` always holds.
- Confirm no formula or constant from `backend/calculation/` is duplicated inside `backend/csv/` (this unit only checks structural/type validity, it never computes `E_day`, PF-derived values, etc.) — satisfies `code-standards.md`'s no-duplication rule.