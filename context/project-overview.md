# Inverter and Battery Sizing Calculation

> **Role instruction for the AI agent:** While working on this project, act as an industry professional with real, hands-on experience in both electrical engineering and professional web/UI development. Every decision — from the sizing math to the layout of a form — should reflect what a senior electrical engineer *and* a senior product/UI developer would actually do in the real world, not a simplified or "demo" version. This is a real tool used by real professionals for real installations. Treat it that way at every step.

## Overview

This application helps electrical professionals — industrial, household, hospital, and college installers — correctly size a battery bank and inverter for a given electrical load. The user creates a project, enters or uploads their loads (appliances, electronics, motors, lights, etc.), and the app calculates the required battery bank size, inverter size, cable/fuse sizing, and any warnings — using standards-based electrical engineering formulas (IEEE 485, IEEE 1013, NEC), not rough estimates. Projects are saved so they can be revisited, edited, and exported as a PDF report to share with a client or keep on record.

## Goals

1. Give professionals a battery bank and inverter size recommendation that is calculated correctly, using real engineering formulas and constraints — not a rough guess.
2. Make load entry easy and error-free by offering a categorized ratings library (so most users don't need to know exact wattages) while still allowing manual override or CSV upload for advanced users.
3. Let every project be saved, edited, revisited, and exported as a clean PDF report — without requiring the user to create an account.
4. Support both metric (India, default) and other regional units, and both Celsius and Fahrenheit, with the correct formulas applied automatically based on the user's selection.

## Core User Flow

1. User opens the app and creates a **new project** (name is editable/deletable/updatable later).
2. User selects the **firm/load type** (industry, household, hospital, college, etc.).
3. User adds their loads, either:
   - Manually, picking from a **segregated ratings library** (Appliances, Electronics, Motors, Lights, Others) with typical wattage suggestions, or
   - By **uploading a CSV** using the provided template.
4. For each load, the user optionally marks **"I know the power factor"** and enters it — otherwise the app uses the standard category-based power factor automatically.
5. The app shows the **running total load** as items are added.
6. User selects/enters known parameters where applicable — battery voltage, series/parallel wiring, available battery size, inverter efficiency, reserve days, temperature (°C or °F), and region.
7. User submits for calculation. The backend runs the full sizing engine and returns:
   - Required battery bank size (Ah, voltage, series/parallel configuration)
   - Required inverter size (continuous + surge VA)
   - Cable/fuse sizing recommendations
   - Any warnings (e.g., "ventilation required," "power factor below 0.85")
8. If the user already knows their battery/inverter model, the app can instead **validate** whether it's sufficient for the calculated load.
9. Project is automatically saved to the database. User can return anytime via the **dashboard** (the app's landing page), where it appears under **All**, and also under **Recent**, **Favorites** (if starred), or **Edited** (if modified, with a last-edited timestamp) as applicable. From the dashboard the user can open, edit, star, or delete any project, and narrow the list using the **date-range filter** and **search**.
10. User can **export a PDF report** at any time — including load-by-load breakdown, total load, final battery + inverter recommendation, cable/fuse sizing, and warnings.

## Features

### Project Management
- Create, rename, edit, and delete projects
- Projects saved automatically to the database (no login required)
- **Dashboard is the landing page** of the app — the first thing a user sees on open
- Dashboard organizes projects into four tabs: **All**, **Recent** (by last opened/edited), **Favorites** (user-starred), and **Edited** (modified after creation, with last-edited timestamp)
- **Filter bar** above the project list: date-range filter and project-name search, both working within whichever tab is active
- Star/unstar a project to add or remove it from Favorites
- Version history retained when a project is edited
- Clear navigation back to the dashboard from inside any project workspace

### Load Entry
- Segregated load categories: Appliances, Electronics, Motors, Lights, Others
- Standard ratings library with typical wattage per equipment, selectable by the user
- Manual override of wattage for known/custom equipment
- "Others" section for equipment not in the library (kept private to the project; not automatically added to the shared library)
- Per-load toggle: known power factor (manual entry) vs. standard category-based power factor (automatic)
- CSV upload with a downloadable template; valid rows are processed, invalid/missing data is clearly flagged with an explanation

### Calculation Engine
- Full battery bank sizing (Ah required, series/parallel configuration, temperature/aging/DOD/Peukert corrections)
- Full inverter sizing (continuous VA, surge VA, waveform requirement)
- Cable and fuse sizing recommendations
- Region-aware calculation: India as default, other regions selectable; Celsius/Fahrenheit selectable, with the correct formula applied automatically
- "Recommend" mode (suggest a battery/inverter configuration) and "Validate" mode (check if a known battery/inverter is sufficient)
- Clear separation between hard errors (blocks a result) and warnings (shown but doesn't block)

### Reporting
- PDF export including: load-by-load breakdown, total load, battery + inverter recommendation, cable/fuse sizing, and warnings

## Scope

### In Scope
- Project creation, editing, deletion, and revisiting (no login)
- Segregated, categorized load entry with a standard ratings library
- CSV upload with template and validation
- Per-load power-factor toggle (known vs. category-based)
- Full battery bank and inverter sizing engine, built on standards-based formulas
- Region and temperature-unit selection (India default) affecting the calculation
- "Recommend" and "Validate" flows for battery/inverter selection
- PDF report export (load breakdown, totals, recommendation, cable/fuse sizing, warnings)
- Manually curated battery/inverter/equipment catalogs
- Project card actions: rename, duplicate, archive, star/favorite, delete (with confirmation), and a placeholder "Share" action (UI only — no real link/permission functionality yet)
- Dashboard filters (application type, system type, battery technology, status, location) in a slide-in drawer, separate from the date-range control

### Out of Scope (for this version)
- User login/authentication
- Live/real-time (MCP-fetched) pricing or product availability
- Admin review-queue UI for promoting custom "Others" equipment into the shared library
- Multi-region currency/pricing display
- Compliance checklist section in the PDF report
- Real functionality behind the "Share" action (link generation, permissions, expiry) — placeholder UI only for now
- Export to Excel (PDF export only for this version)

## Success Criteria

1. A user can create a project, select a firm/load type, and add loads either manually or via CSV upload.
2. Every load correctly uses either a manually entered power factor or the correct category-based default — never a guess with no basis.
3. The calculation engine returns a battery bank and inverter recommendation (or validation result) using the full standards-based formula set, including cable/fuse sizing and any relevant warnings.
4. Region and temperature unit selection correctly changes which formulas/values are used.
5. A project can be saved, revisited later from the dashboard, edited (appearing under the "Edited" tab with a timestamp), starred (appearing under "Favorites"), filtered by date range or name, and deleted.
6. A PDF report can be exported at any time, containing the load breakdown, totals, recommendation, cable/fuse sizing, and warnings.
7. Invalid CSV rows are never silently accepted — they are flagged clearly, while valid rows are still processed.