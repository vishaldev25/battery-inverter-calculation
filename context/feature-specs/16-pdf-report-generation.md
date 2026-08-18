# Feature 16 — PDF Report Generation

**Status:** Code-complete, visually verified (rendered to PNG and inspected page-by-page).
**Owner module:** `backend/report/` (per `architecture.md` system boundaries).
**Reconstructed:** this file was lost and has been rebuilt from the actual implemented
`backend/report/pdf_builder.py` and the `POST /{project_id}/report` route in
`backend/projects/router.py` — it documents what was built, not a fresh proposal.

---

## 1. Purpose

Generate an exportable, professional-grade PDF engineering report from a project's
**already-saved** `last_calculation_result` — load-by-load breakdown, total load, final
battery + inverter recommendation, cable/fuse sizing, and warnings — per
`project-overview.md` Goal 3 and the Reporting feature list.

## 2. Hard Rule (Invariant 1 / code-standards.md)

`backend/report/pdf_builder.py` performs **zero calculation**. Every number rendered —
including inside the "formula → substituted numbers → result" lines in the Engineering
Calculations section — is read directly from `project.last_calculation_result`. The
formula lines document *how* an already-computed number was derived; they never
re-evaluate anything. `pdf_builder.py` never imports from `backend/calculation/`.

## 3. Entry point

```
POST /api/projects/{project_id}/report
```

Implemented in `backend/projects/router.py`:
- 404 if project not found.
- 400, with a specific actionable message, if `project.last_calculation_result is None`
  (i.e. "Calculate" has never been successfully run for this project).
- Otherwise calls `build_report_pdf(project) -> bytes` and streams it back as
  `application/pdf` via `Response` — **never written to disk**, per `architecture.md`'s
  "No file/blob storage required for v1" storage model.

`build_report_filename(project_name)` generates the download filename:
`{sanitized_name}_report_{YYYYMMDD}.pdf`, using a conservative allow-list
(`[^A-Za-z0-9 _-]` stripped, collapsed whitespace/underscores, truncated to 80 chars,
falls back to `"project"` if the name sanitizes to nothing).

## 4. Locked decisions (resolved during the original spec session)

These were explicit open questions at spec time, each resolved and now reflected in code:

1. **Charts: ReportLab-native only, no `matplotlib`.** Zero new dependency, consistent
   with `architecture.md`'s original rationale for choosing ReportLab (pure Python, no
   system dependencies, required for Vercel serverless). Implemented via
   `reportlab.graphics.charts.barcharts.VerticalBarChart` and
   `reportlab.graphics.charts.piecharts.Pie`.
2. **Filename sanitization: conservative allow-list**, not a blocklist — see §3 above.
3. **"As of" timestamp: reuse `project.updated_at`.** No new `calculated_at` field was
   added to `backend/projects/models.py` — the report's "Calculated As Of" line in the
   title block reads `project.updated_at` directly.

## 5. Chart data decision (locked)

The reference PDF's "Estimated Daily Load Curve" is a **time-of-day** curve, which would
require a per-load start-time field. No such field exists anywhere in `LoadItem` or the
calculation pipeline, and fabricating one would invent data — prohibited by
`ai-workflow-rules.md`. Standard industry practice for sizing tools without time-of-use
data (Victron/Schneider-style exports) was used instead: a **category-based energy
breakdown**, built entirely from real, already-saved per-load fields
(`nominal_watts × quantity × daily_hours`, grouped by `load.category`):

- A bar chart — Wh/day by category (`_build_load_analysis_charts` → `VerticalBarChart`).
- A donut/pie chart — % share of total energy by category (`Pie`, `sideLabels = 1`).

Both panels render side-by-side via `_chart_panel()`, sharing the content width.

## 6. Explicitly NOT included, and why

- **Solar array sizing** — no solar calculation exists anywhere in `backend/calculation/`.
- **Monthly savings / pricing** — `project-overview.md`'s Out of Scope list excludes
  live/real pricing; no pricing calculation exists to report.
- **Approval/license block** — present in the user-supplied reference PDF but no
  corresponding workflow/data exists in this app; inventing one would violate
  `ai-workflow-rules.md`'s "do not invent product behavior not defined in the context
  files" rule.

Net effect: the executive-summary highlight-box row has **3 boxes** (Battery, Inverter,
Cabling), not the reference's 4 (no Solar/Savings box).

## 7. PDF structure (as built, in document order)

Always rendered in **fixed light-mode**, regardless of the app's current theme — per
`ui-context.md`'s "PDF Export — standard, light-mode only" rule. This is the one
deliberate hardcoded-hex-color exception in the codebase (`_ACCENT`, `_TEXT_PRIMARY`,
etc. in `pdf_builder.py`'s palette constants), since the CSS token system doesn't apply
to a generated document.

### 7.1 Title block (`_build_title_block`)
- Kicker ("ENGINEERING SIZING REPORT"), project name (hero text), subtitle.
- 3×4 metadata grid: Project Status, System Voltage / Calculated As Of
  (`project.updated_at`), Battery Chemistry / Report Generated, Autonomy (Reserve).

### 7.2 Section 1 — Executive Summary (`_build_executive_summary`)
- Intro paragraph citing IEEE 485 / IEEE 1013 / NEC.
- 3 highlight boxes (`_highlight_box`), equal width, reading from
  `result["battery_summary"]`, `result["inverter_summary"]`, `result["cabling_summary"]`:
  - **Recommended Battery Bank** — actual Ah capacity, `NsNp` config, total unit count.
  - **Recommended Inverter** — continuous VA, surge VA.
  - **Cable & Protection** — recommended AWG, fuse rating (`i_fuse_a`).

### 7.3 Section 2 — Load Schedule (`_build_load_schedule_table`)
Per-load table: Load, Qty, Power (W), Hrs/Day, Energy (Wh/day), PF, Concurrent, with a
Total row (total Wh/day, total peak W). PF cell shows the numeric override if
`load.power_factor is not None`, else the literal string `"category default"`.

**Fixed bug (Resolved Issue #17):** all cells are `Paragraph`-wrapped, not raw Python
strings — raw strings silently overflow a `Table`'s declared column width with no error.
Column widths are fractional shares of `_CONTENT_WIDTH`, rebalanced after the fix so the
"PF" and "Concurrent" columns (the two that overflowed before) have enough room.

### 7.4 Section 3 — Engineering Calculations (`_build_engineering_calculations`)
Formula → substitution → selection blocks (`_formula_block`), one per module, reading
only from `result["load_summary"]`, `result["battery_summary"]`,
`result["inverter_summary"]`, and `project.parameters` — no recomputation:

- **3.1 Inverter Sizing** — `S_continuous = S_peak × (1 + F_future)`, `S_surge`
  (worst-case motor start + concurrent background load), selection line stating the
  required continuous/surge VA, waveform, and DC input voltage.
- **3.2 Battery Bank Sizing** — full correction-chain formula, daily energy demand,
  system voltage/autonomy/aging-factor/wire-efficiency substitution lines,
  `N_series`/`N_parallel` formula, and a selection line stating the final Ah capacity,
  voltage, chemistry, and string configuration.

### 7.5 Section 4 — Cable, Fuse & Voltage Drop (`_build_cabling_table`)
One-row table: Circuit Segment ("Battery to Inverter"), Design Current (`i_design_a`),
Wire Gauge (`recommended_awg`), Fuse Rating (`i_fuse_a`), Voltage Drop (`voltage_drop_pct`
with a Pass/Review label at the 3% threshold). Intro line cites NEC 210.19/215.2's 125%
continuous-load factor and states the larger-of-ampacity-or-voltage-drop selection rule.

### 7.6 Section 5 — Energy & Load Analysis (`_build_load_analysis_charts`)
The bar + donut chart pair described in §5, aggregated via `_aggregate_by_category`.

### 7.7 Section 6 — Safety Recommendations & Engineer Notes (`_build_safety_notes_section`)
- If `result["hard_errors"]` is non-empty: a red data-integrity warning block stating
  this saved result should never contain hard errors and the project must be
  recalculated — this should be structurally unreachable (Invariant 2: a result is never
  saved while `hard_errors` is present), so this is a defensive display path, not an
  expected one.
- All `result["warnings"]` rendered as an amber bulleted list, or a muted
  "No warnings were raised for this calculation" line if empty.

### 7.8 Page footer (`_FooterCanvas`)
Accent rule under the header area, a lighter rule above the footer strip, project name +
"Generated: {date}" on the left, page number on the right — drawn on every page via
`onFirstPage`/`onLaterPages`.

## 8. Verification performed

- **Code-reviewed** against real pasted `models.py` / `repository.py` / `router.py` /
  `main.py` and all five `backend/calculation/` files — no field names guessed.
- **Actually rendered**: a real sample PDF was generated against realistic data,
  converted to PNG via `pdftoppm`, and visually inspected page-by-page. This is what
  caught the Load Schedule table-overflow bug (§7.3) — code review alone had missed it.
- **Smoke-tested** via `_smoke_test_16.py` using `httpx.AsyncClient` + `ASGITransport`
  (not `TestClient` + `asyncio.run()`, which caused an `AsyncMongoClient` event-loop
  conflict on the first attempt — see Resolved Issue #16 in `progress-tracker.md`).
  Script deleted after confirmation, per standing practice.

## 9. Known gap as of this writing (tracked in `progress-tracker.md`, not yet closed)

`pdf_builder.py` was written **before** the later calculation-engine audit added the
audit-trail fields (`ah_autonomy`, `k_t`, `dod_max_used`, `eta_batt_used` from
`battery.py`; `pf_avg_used`, `efficiency_used` from `inverter.py`; `cable_length_m`,
`n_parallel_strings`, `i_fuse_computed_a` from `cabling.py`) and the chemistry-aware
`BATTERY_STANDARDS_BY_CHEMISTRY` citation lookup in `constants.py`. None of these are
consumed by this file yet — `cabling.py`'s `i_fuse_a` key is unchanged so nothing is
broken, it simply doesn't yet display the new standard-vs-computed fuse comparison, the
numeric PF, or the correct per-chemistry standards citation. This is the currently
scheduled next unit of work, not part of this feature's original scope.