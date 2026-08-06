# UI Context

## Theme

Dual theme: **dark mode and light mode, both fully supported** — every component must work correctly in both, switchable via a theme toggle in the header (not tied to any login/user account, since authentication is out of scope for this version).

The overall visual language is a **premium, professional engineering-software aesthetic** — inspired by tools like Linear, Vercel, Notion, and industry engineering platforms (Schneider EcoStruxure, Victron Energy Design Tool, ETAP). Not playful or consumer-styled. Confident use of a single blue accent color, generous spacing, soft elevation on cards instead of heavy borders, and restrained use of color — reserved mainly for status, warnings, and interactivity.

## Colors

All components use these CSS custom property tokens — no hardcoded hex values anywhere in the codebase.

| Role | CSS Variable | Dark mode | Light mode |
|---|---|---|---|
| Page background | `--bg-base` | `#0B0E14` | `#F7F8FA` |
| Surface (cards/panels) | `--bg-surface` | `#151A23` | `#FFFFFF` |
| Surface (raised/hover) | `--bg-surface-raised` | `#1C222E` | `#FBFBFC` |
| Primary text | `--text-primary` | `#E7EAEF` | `#111418` |
| Muted text | `--text-muted` | `#8B93A1` | `#5B6472` |
| Primary accent | `--accent-primary` | `#3B82F6` | `#2563EB` |
| Accent (hover) | `--accent-primary-hover` | `#5C97F7` | `#1D4ED8` |
| Border | `--border-default` | `#242B38` | `#E4E7EC` |
| Success (Active status) | `--state-success` | `#4ADE80` | `#16A34A` |
| Warning (advisories) | `--state-warning` | `#FBBF24` | `#D97706` |
| Error (hard_errors / Delete) | `--state-error` | `#F87171` | `#DC2626` |
| Draft status | `--state-draft` | `#94A3B8` | `#64748B` |
| Completed status | `--state-completed` | `#60A5FA` | `#2563EB` |
| Archived status | `--state-archived` | `#6B7280` | `#9CA3AF` |

**Color meaning is consistent everywhere:** blue = interactive/primary action, green = success/active, amber = warning (matches the calculation engine's `warnings`), red = error/destructive action (matches `hard_errors` and the Delete action), gray = inactive/draft/archived.

## Typography

| Role | Font | Variable |
|---|---|---|
| UI text | Inter | `--font-sans` |
| Numeric/technical values (Ah, VA, AWG readings) | Inter with tabular numerals, or JetBrains Mono for emphasis | `--font-mono` |

**Hierarchy:** project name / key result figures (e.g., "200 Ah @ 48 Vdc") are the largest and boldest text on any screen — they are the "hero" element. Metadata (client name, timestamps, location) is always smaller and in muted text. This hierarchy must hold on every card and every results panel.

## Border Radius

| Context | Class |
|---|---|
| Inline / small UI (badges, inputs) | `rounded-md` (6px) |
| Cards / panels | `rounded-xl` (12px) |
| Modals / overlays / drawers | `rounded-2xl` (16px) |

## Component Library

shadcn/ui on top of Tailwind CSS. Components live in `components/ui/`. Use the shadcn CLI to add new components rather than writing from scratch (per `code-standards.md`'s protected-files rule). Icons: **Lucide React**, stroke-based only. Sizes: `h-4 w-4` for inline icons, `h-5 w-5` for buttons/card icons.

## Layout Patterns

### Header (every screen)
Logo + app name (left) → global search bar (center) → calendar shortcut, notifications, help, theme toggle, user avatar icon (right). No login/logout control — the avatar icon is decorative/placeholder only in this version, since authentication is out of scope.

### Toolbar (dashboard, below header)
"+ New Project" as the primary, most visually prominent button (solid blue, left side of toolbar) → search → Filters button → Sort → Date Range → Import/Export.

### Filters — drawer, not a dropdown
**Filters open in a slide-in side drawer/panel from the right edge of the screen, pushing content aside rather than floating over it.** This directly replaces the earlier overlapping-dropdown approach — the drawer has its own scroll area, a clear "Apply" and "Clear all" action pinned to the bottom, and a close (×) button, so it never visually collides with the date-range control, page content, or project cards behind it. Filter sections (collapsible): Application Type, System Type, Battery Technology, Status, Location, Sort By. Date Range remains a separate, independent calendar-picker control in the toolbar (Today / Last 7 Days / Last 30 Days / This Month / Last Month / Custom Range) — it does not open inside the Filters drawer, so the two never overlap each other.

### Dashboard — project cards
Responsive grid: 4–5 cards per row (desktop), 3 (laptop), 2 (tablet), 1 (mobile) — equal card height regardless of content. Each card includes:
- Project thumbnail/cover area (top)
- Project name — most prominent text on the card
- Client name
- Application type + System type (e.g., "Residential • Hybrid")
- Location (city, region)
- Key results: daily energy (kWh/day), recommended inverter size, recommended battery capacity
- Status badge (Draft / Active / Completed / Archived), color-coded per the token table
- Created date and last-modified date
- Favorite (star) toggle
- **Three-dot (⋮) overflow menu**, top-right corner, containing: Open, Rename, Edit Details, Duplicate, Move to Favorites, Archive, Share, Export PDF, Export Excel, Delete — with **Delete shown in the error/red color** to mark it as destructive
- Clicking anywhere on the card (other than the star or the ⋮ menu) opens the project
- Hover state: soft elevation increase, smooth shadow transition, slight border highlight, pointer cursor

### New Project — 4-step wizard
Opened by "+ New Project," not an inline form on the dashboard. Horizontal progress stepper at the top (Project Details → Electrical Configuration → System Configuration → Review). Each step is a single centered card with generous spacing; Back/Next navigation at the bottom of the card; smooth step transitions.

### Project workspace — load entry
Left sidebar: category navigation (Kitchen, Living Room, Bedroom, Outdoor, HVAC, Lighting, Office, IT Equipment, Industrial, Hospital, Agriculture, Motors, EV Charging, Custom/Others) — categories reflect real-world room/use-case groupings, not just the four original buckets, so professionals can find equipment intuitively regardless of firm type. Main panel: searchable, sortable load table (icon, name, quantity, wattage, hours, power factor toggle, priority). Right sidebar (sticky): live-updating project summary — peak demand, daily consumption, recommended battery/inverter at a glance, plus the core parameters (battery voltage, reserve days, region, temperature unit).

### Results view
Card grid for Battery Bank, Inverter, Cable & Fuse, and Protection Panel — each with its key figures as the dominant text and supporting details below. A warnings banner (amber, using `--state-warning` token) appears above the results cards only when warnings exist — never shown empty. Collapsible sections below for formula transparency (Battery Formula, Inverter Formula, Voltage Drop, Fuse Selection) so a professional can audit the math, not just trust a black box. "Export PDF" as a clearly primary action near the top of the page.

### Modals
Centered overlay with backdrop blur — used for Edit Project Details and Delete confirmation (which requires typing the project name before the Delete button becomes active, per `architecture.md`'s access model).

## Icons

Lucide React, stroke-based icons only. `h-4 w-4` for inline/list icons, `h-5 w-5` for buttons and card header icons. Icon choice should reflect meaning consistently across the app (e.g., the same battery icon always represents "Battery Bank," the same plug icon always represents "Inverter") so recognition builds across screens.

## PDF Export — standard, light-mode only

**The exported PDF report always uses a fixed light color scheme, regardless of the app's current theme setting.** This is a deliberate, standard rule: a PDF is a printed/shared document, and professional engineering reports are expected to be readable in print and in email previews — a dark-themed PDF is not standard practice and must never be generated, even if the user is working in dark mode when they export. The PDF layout includes: a title block (project name, client, location, system type, date generated, calculation version), an executive summary of the recommended inverter/battery/cable specs, the detailed load schedule table, the engineering formulas used (for transparency/audit), load analysis charts, and a safety recommendations/engineer notes section — all styled in a clean, print-appropriate light layout with a single blue accent for headers, consistent with the report structure already validated in the sample export.