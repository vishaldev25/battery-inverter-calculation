"""
PDF Report Generation — reads project.last_calculation_result and formats
it into a fixed light-mode PDF, styled to match the reference engineering
report format (title block, highlight-box executive summary, load
schedule, formula-substituted engineering calculations, cabling table,
charts, safety notes).

STRICT RULE (Invariant 1 / code-standards.md): this module performs ZERO
calculation. Every number rendered here — including inside the "formula =
substituted numbers = result" lines in the Engineering Calculations
section — is read directly from project.last_calculation_result. The
formula lines display the SAME already-computed values already present in
the result dict; the "=" shown documents how that stored number was
derived, it is never re-evaluated here.

Chart decision (locked, per standard industry practice): the reference's
"Estimated Daily Load Curve" is a time-of-day curve, which requires a
per-load start-time that does not exist anywhere in LoadItem/the
calculation pipeline — fabricating one would invent data, which
ai-workflow-rules.md prohibits. Standard practice for sizing tools that
don't capture time-of-use (Victron/Schneider-style exports) is a
category-based energy breakdown instead: a bar chart (Wh/day by category)
paired with a donut (% share by category) — both built from real,
already-saved per-load fields (nominal_watts x quantity x daily_hours),
zero fabrication, zero recalculation.

Solar array sizing, monthly savings, and an approval/license block from
the reference are NOT included — no solar or pricing calculation exists
anywhere in backend/calculation/, and project-overview.md's Out of Scope
list excludes live pricing.

Chart implementation uses ReportLab's native reportlab.graphics.charts
(no matplotlib) — zero new dependencies, per architecture.md's rationale
for ReportLab (pure Python, no system dependencies, Vercel serverless).

VERIFIED: rendered against realistic data and visually inspected
page-by-page (see Feature 16 session notes) — a table-overflow bug in the
Load Schedule section (raw strings instead of Paragraph cells silently
overflowing the page margin) was found and fixed this way, not guessed.

AUDIT-FIELD CONSUMPTION (post-Feature-16 follow-up, this session): this
file now reads and displays four audit fields that the calculation-engine
audit added to battery.py/inverter.py/cabling.py but that were not yet
surfaced anywhere: pf_avg_used (inverter.py), a chemistry-aware standards
citation via BATTERY_STANDARDS_BY_CHEMISTRY (constants.py), cable_length_m
(cabling.py), and i_fuse_computed_a shown alongside the standard-snapped
i_fuse_a (cabling.py). No new calculation was added — every value below
was already present in project.last_calculation_result before this
change; this update only makes it visible in the PDF.
"""

import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

from backend.projects.models import Project
from backend.calculation.constants import BATTERY_STANDARDS_BY_CHEMISTRY

# ---------------------------------------------------------------------------
# Fixed light-mode palette (ui-context.md — PDF is ALWAYS light-mode)
# ---------------------------------------------------------------------------
_ACCENT = colors.HexColor("#2563EB")
_ACCENT_HOVER = colors.HexColor("#1D4ED8")
_TEXT_PRIMARY = colors.HexColor("#111418")
_TEXT_MUTED = colors.HexColor("#5B6472")
_BORDER = colors.HexColor("#E4E7EC")
_SURFACE_RAISED = colors.HexColor("#FBFBFC")
_BOX_BG = colors.HexColor("#EFF4FF")
_WARNING = colors.HexColor("#D97706")
_ERROR = colors.HexColor("#DC2626")

_CHART_PALETTE = [
    colors.HexColor("#2563EB"),
    colors.HexColor("#60A5FA"),
    colors.HexColor("#93C5FD"),
    colors.HexColor("#CBD5E1"),
    colors.HexColor("#1D4ED8"),
    colors.HexColor("#3B82F6"),
]

_PAGE_SIZE = A4
_MARGIN = 16 * mm
_CONTENT_WIDTH = A4[0] - 2 * _MARGIN  # usable width, used to size tables/boxes consistently


# ---------------------------------------------------------------------------
# Filename sanitization (Feature 16 spec §3.3 — conservative allow-list)
# ---------------------------------------------------------------------------

_FILENAME_ALLOWED = re.compile(r"[^A-Za-z0-9 _-]")
_FILENAME_MAX_LEN = 80


def build_report_filename(project_name: str) -> str:
    cleaned = _FILENAME_ALLOWED.sub("", project_name or "")
    cleaned = re.sub(r"[ _]{2,}", " ", cleaned).strip()
    cleaned = cleaned.replace(" ", "_")
    cleaned = cleaned[:_FILENAME_MAX_LEN].strip("_") or "project"
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{cleaned}_report_{date_str}.pdf"


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    base = getSampleStyleSheet()
    return {
        "ReportKicker": ParagraphStyle(
            "ReportKicker", parent=base["Normal"], textColor=_TEXT_MUTED,
            fontSize=9, spaceAfter=2, fontName="Helvetica-Bold",
        ),
        "Title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], textColor=_TEXT_PRIMARY,
            fontSize=21, leading=25, spaceAfter=2, alignment=0,
        ),
        "SubTitle": ParagraphStyle(
            "ReportSubTitle", parent=base["Normal"], textColor=_ACCENT,
            fontSize=12, spaceAfter=10,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"], textColor=_ACCENT,
            fontSize=13.5, spaceBefore=16, spaceAfter=8, borderColor=_BORDER,
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["Normal"], textColor=_TEXT_PRIMARY, fontSize=9.5,
            leading=14,
        ),
        "Muted": ParagraphStyle(
            "Muted", parent=base["Normal"], textColor=_TEXT_MUTED, fontSize=8.5,
            leading=12,
        ),
        "BoxLabel": ParagraphStyle(
            "BoxLabel", parent=base["Normal"], textColor=_TEXT_MUTED, fontSize=7.8,
            alignment=TA_CENTER, spaceAfter=3, fontName="Helvetica-Bold",
        ),
        "BoxValue": ParagraphStyle(
            "BoxValue", parent=base["Normal"], textColor=_ACCENT, fontSize=15,
            fontName="Helvetica-Bold", alignment=TA_CENTER, leading=18,
        ),
        "BoxSub": ParagraphStyle(
            "BoxSub", parent=base["Normal"], textColor=_TEXT_MUTED, fontSize=7.5,
            alignment=TA_CENTER,
        ),
        "FormulaLabel": ParagraphStyle(
            "FormulaLabel", parent=base["Normal"], textColor=_TEXT_PRIMARY,
            fontSize=10, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3,
        ),
        "FormulaText": ParagraphStyle(
            "FormulaText", parent=base["Normal"], textColor=_ACCENT_HOVER,
            fontName="Courier-Bold", fontSize=9.5, leading=14, spaceAfter=3,
        ),
        "FormulaSub": ParagraphStyle(
            "FormulaSub", parent=base["Normal"], textColor=_TEXT_PRIMARY,
            fontName="Courier", fontSize=8.8, leading=13, spaceAfter=1,
        ),
        "SelectionText": ParagraphStyle(
            "SelectionText", parent=base["Normal"], textColor=_TEXT_PRIMARY,
            fontSize=9.5, leading=14, spaceBefore=5, spaceAfter=10,
            backColor=_SURFACE_RAISED,
        ),
        "CitationText": ParagraphStyle(
            "CitationText", parent=base["Normal"], textColor=_TEXT_MUTED,
            fontSize=8, fontName="Helvetica-Oblique", leading=11, spaceBefore=2, spaceAfter=6,
        ),
        "WarningText": ParagraphStyle(
            "WarningText", parent=base["Normal"], textColor=_WARNING, fontSize=9,
            leading=13, spaceAfter=4,
        ),
        "ErrorText": ParagraphStyle(
            "ErrorText", parent=base["Normal"], textColor=_ERROR, fontSize=9,
            leading=13, spaceAfter=4,
        ),
        "ChartTitle": ParagraphStyle(
            "ChartTitle", parent=base["Normal"], textColor=_ACCENT,
            fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4,
        ),
    }


class _FooterCanvas:
    """Draws a consistent accent top rule + footer strip on every page."""

    def __init__(self, project_name: str, generated_on: str):
        self.project_name = project_name
        self.generated_on = generated_on

    def __call__(self, canvas, doc):
        canvas.saveState()
        page_w, page_h = _PAGE_SIZE

        canvas.setStrokeColor(_ACCENT)
        canvas.setLineWidth(1.4)
        canvas.line(_MARGIN, page_h - 9 * mm, page_w - _MARGIN, page_h - 9 * mm)

        canvas.setStrokeColor(_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(_MARGIN, 12 * mm, page_w - _MARGIN, 12 * mm)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_TEXT_MUTED)
        footer_left = f"Project: {self.project_name}  |  Generated: {self.generated_on}"
        canvas.drawString(_MARGIN, 8 * mm, footer_left)
        canvas.drawRightString(page_w - _MARGIN, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def build_report_pdf(project: Project) -> bytes:
    result: Dict[str, Any] = project.last_calculation_result or {}
    styles = _build_styles()
    generated_on = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Look up chemistry-specific standards citation for accurate referencing
    chemistry_citation = BATTERY_STANDARDS_BY_CHEMISTRY.get(project.parameters.battery_chemistry)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=_PAGE_SIZE,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"{project.name} — Engineering Sizing Report",
    )

    footer = _FooterCanvas(project.name or "Untitled Project", generated_on)

    story: List[Any] = []
    story.extend(_build_title_block(project, result, styles, generated_on))
    story.extend(_build_executive_summary(result, styles, chemistry_citation))
    story.append(Spacer(1, 10))
    story.extend(_build_load_schedule_table(project, styles))
    story.append(PageBreak())
    story.extend(_build_engineering_calculations(project, result, styles))
    story.append(PageBreak())
    story.extend(_build_cabling_table(result, styles))
    story.extend(_build_load_analysis_charts(project, styles))
    story.extend(_build_safety_notes_section(result, styles))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Section 1 — Title block
# ---------------------------------------------------------------------------

def _build_title_block(project: Project, result: Dict[str, Any], styles, generated_on: str) -> List[Any]:
    as_of = project.updated_at.strftime("%B %d, %Y") if project.updated_at else "—"
    params = project.parameters

    elements: List[Any] = [
        Paragraph("ENGINEERING SIZING REPORT", styles["ReportKicker"]),
        Paragraph(xml_escape(project.name or "Untitled Project"), styles["Title"]),
        Paragraph("Battery Bank &amp; Inverter Sizing Analysis", styles["SubTitle"]),
    ]

    meta_rows = [
        ["Project Status", (project.status or "draft").capitalize(),
         "System Voltage", f"{params.system_dc_voltage:.0f} V DC"],
        ["Calculated As Of", as_of,
         "Battery Chemistry", params.battery_chemistry.value.replace("_", " ").title()],
        ["Report Generated", generated_on,
         "Autonomy (Reserve)", f"{params.days_of_autonomy:.1f} days"],
    ]
    col_w = _CONTENT_WIDTH / 4
    meta_table = Table(meta_rows, colWidths=[col_w, col_w, col_w, col_w])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), _TEXT_MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), _TEXT_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), _TEXT_PRIMARY),
        ("TEXTCOLOR", (3, 0), (3, -1), _TEXT_PRIMARY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), _SURFACE_RAISED),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 14))
    return elements


# ---------------------------------------------------------------------------
# Section 2 — Executive summary (highlight boxes)
# ---------------------------------------------------------------------------

def _fmt(value: Optional[float], suffix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}{suffix}"


def _highlight_box(label: str, value: str, sub: str, width_mm: float, styles) -> Table:
    inner = Table(
        [[Paragraph(label, styles["BoxLabel"])],
         [Paragraph(value, styles["BoxValue"])],
         [Paragraph(sub, styles["BoxSub"])]],
        colWidths=[width_mm * mm],
    )
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _BOX_BG),
        ("BOX", (0, 0), (-1, -1), 1.0, _ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return inner


def _build_executive_summary(result: Dict[str, Any], styles, chemistry_citation: Optional[str] = None) -> List[Any]:
    battery = result.get("battery_summary", {}) or {}
    inverter = result.get("inverter_summary", {}) or {}
    cabling = result.get("cabling_summary", {}) or {}

    standards_ref = f"{chemistry_citation} and NEC" if chemistry_citation else "IEEE standards and NEC"

    elements: List[Any] = [
        Paragraph("1. Executive Summary", styles["SectionHeading"]),
        Paragraph(
            f"This report provides the standards-based ({standards_ref}) battery bank and "
            "inverter sizing recommendation calculated for this project's load profile and site parameters.",
            styles["Body"],
        ),
        Spacer(1, 10),
    ]

    box_w = (_CONTENT_WIDTH / mm - 12) / 3  # three equal boxes across the content width, with gaps

    battery_box = _highlight_box(
        "RECOMMENDED BATTERY BANK",
        _fmt(battery.get("actual_ah_capacity"), " Ah", 0),
        f"{battery.get('n_series', '—')}S {battery.get('n_parallel', '—')}P  ·  {battery.get('total_batteries', '—')} units",
        box_w, styles,
    )
    inverter_box = _highlight_box(
        "RECOMMENDED INVERTER",
        _fmt(inverter.get("s_continuous_va"), " VA", 0),
        f"Surge rating: {_fmt(inverter.get('s_surge_va'), ' VA', 0)}",
        box_w, styles,
    )
    cabling_box = _highlight_box(
        "CABLE &amp; PROTECTION",
        f"{cabling.get('recommended_awg', '—')} AWG",
        f"Fuse: {_fmt(cabling.get('i_fuse_a'), ' A', 1)}",
        box_w, styles,
    )

    box_row = Table(
        [[battery_box, inverter_box, cabling_box]],
        colWidths=[box_w * mm + 4, box_w * mm + 4, box_w * mm + 4],
    )
    box_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(box_row)
    return elements


# ---------------------------------------------------------------------------
# Section 3 — Load schedule table
# FIX: cells must be Paragraph objects, not raw strings — Table only wraps
# Paragraph content to its column width; raw strings overflow silently.
# ---------------------------------------------------------------------------

def _build_load_schedule_table(project: Project, styles) -> List[Any]:
    elements: List[Any] = [Paragraph("2. Load Schedule", styles["SectionHeading"])]

    if not project.loads:
        elements.append(Paragraph("No loads recorded for this project.", styles["Muted"]))
        return elements

    header_style = ParagraphStyle(
        "TableHeader", parent=styles["Body"], textColor=colors.white,
        fontName="Helvetica-Bold", fontSize=8.5, leading=10,
    )
    cell_style = ParagraphStyle(
        "TableCell", parent=styles["Body"], fontSize=8.5, leading=10.5,
    )
    total_style = ParagraphStyle(
        "TableTotal", parent=styles["Body"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5,
    )

    def _cell(text: str, style=cell_style) -> Paragraph:
        return Paragraph(text, style)

    header = [_cell(h, header_style) for h in
              ["Load", "Qty", "Power (W)", "Hrs/Day", "Energy (Wh/day)", "PF", "Concurrent"]]
    rows = [header]
    total_energy = 0.0
    total_peak_w = 0.0
    for load in project.loads:
        pf_display = f"{load.power_factor:.2f}" if load.power_factor is not None else "category default"
        energy_wh = load.nominal_watts * load.quantity * load.daily_hours
        total_energy += energy_wh
        if load.is_concurrent:
            total_peak_w += load.nominal_watts * load.quantity
        rows.append([
            _cell(xml_escape(load.name)),
            _cell(str(load.quantity)),
            _cell(f"{load.nominal_watts:.0f}"),
            _cell(f"{load.daily_hours:.1f}"),
            _cell(f"{energy_wh:,.0f}"),
            _cell(pf_display),
            _cell("Yes" if load.is_concurrent else "No"),
        ])

    rows.append([
        _cell("Total", total_style), _cell("", total_style), _cell("", total_style), _cell("", total_style),
        _cell(f"{total_energy:,.0f} Wh", total_style), _cell("", total_style),
        _cell(f"{total_peak_w:,.0f} W (Peak)", total_style),
    ])

    # Rebalanced so "PF" and "Concurrent" (the two columns that overflowed
    # before the Paragraph fix) get enough room; "Load" name still gets the
    # largest share since names are typically the longest content.
    col_widths = [w * _CONTENT_WIDTH for w in (0.22, 0.07, 0.13, 0.11, 0.18, 0.16, 0.13)]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("BACKGROUND", (0, -1), (-1, -1), _SURFACE_RAISED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, _SURFACE_RAISED]),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    elements.append(table)
    return elements


# ---------------------------------------------------------------------------
# Section 4 — Engineering calculations (formula -> substitution -> selection)
# Every value below is read from `result` — never recomputed.
# ---------------------------------------------------------------------------

def _actual_ah_display(actual_ah: Optional[float]) -> str:
    if actual_ah is None:
        return "— Ah"
    return f"{actual_ah:,.0f} Ah"


def _formula_block(
    heading: str,
    formula: str,
    substitution_lines: List[str],
    selection: str,
    styles,
    citation: Optional[str] = None,
) -> List[Any]:
    elements: List[Any] = [Paragraph(heading, styles["FormulaLabel"])]
    elements.append(Paragraph(formula.replace(" ", "&nbsp;"), styles["FormulaText"]))
    for line in substitution_lines:
        if line == "":
            elements.append(Spacer(1, 3))
        else:
            elements.append(Paragraph(line.replace(" ", "&nbsp;"), styles["FormulaSub"]))
    elements.append(Paragraph(selection, styles["SelectionText"]))
    # AUDIT-FIELD ADDITION: chemistry-specific (or otherwise precise)
    # standards citation, shown directly under the block it applies to —
    # more auditable than a single generic citation in the intro
    # paragraph, since different battery chemistries are covered by
    # different standards (see constants.py's BATTERY_STANDARDS_BY_CHEMISTRY).
    if citation:
        elements.append(Paragraph(f"Reference standard: {citation}", styles["CitationText"]))
    return elements


def _build_engineering_calculations(project: Project, result: Dict[str, Any], styles) -> List[Any]:
    load_summary = result.get("load_summary", {}) or {}
    battery = result.get("battery_summary", {}) or {}
    inverter = result.get("inverter_summary", {}) or {}
    params = project.parameters

    elements: List[Any] = [
        Paragraph("3. Engineering Calculations", styles["SectionHeading"]),
        Paragraph(
            "The figures below are the exact values already computed and saved for this project — shown "
            "here alongside their governing formula for audit/transparency, per IEEE 485 / IEEE 1013 / NEC.",
            styles["Muted"],
        ),
        Spacer(1, 6),
    ]

    peak_apparent = load_summary.get("peak_apparent_power_va")
    s_continuous = inverter.get("s_continuous_va")
    s_surge = inverter.get("s_surge_va")
    # AUDIT-FIELD ADDITION: pf_avg_used was already computed in
    # inverter.py and returned in inverter_summary, but never shown here.
    pf_avg_used = inverter.get("pf_avg_used")

    elements.extend(_formula_block(
        "3.1 Inverter Sizing",
        "S_continuous = S_peak x (1 + F_future)",
        [
            f"S_peak (apparent power) = {_fmt(peak_apparent, ' VA', 0)}",
            f"F_future (expansion margin) = 0.20",
            f"=> S_continuous required = {_fmt(s_continuous, ' VA', 0)}",
            "",
            "S_surge = worst-case motor start + concurrent background load",
            f"=> S_surge required = {_fmt(s_surge, ' VA', 0)}",
            "",
            f"Average system power factor (PF_avg) used for DC current derivation = {_fmt(pf_avg_used, '', 3)}",
        ],
        f"Selection: Inverter rated for continuous &ge; {_fmt(s_continuous, ' VA', 0)} "
        f"and surge &ge; {_fmt(s_surge, ' VA', 0)}, Pure Sine Wave, {params.system_dc_voltage:.0f}V DC input.",
        styles,
    ))

    ah_required = battery.get("ah_required")
    actual_ah = battery.get("actual_ah_capacity")
    n_series = battery.get("n_series")
    n_parallel = battery.get("n_parallel")
    total_batteries = battery.get("total_batteries")

    # AUDIT-FIELD ADDITION: chemistry-aware standards citation, looked up
    # by the same enum value already stored on params.battery_chemistry —
    # replaces what would otherwise be a generic "IEEE 485/1013" claim
    # that is factually wrong for LiFePO4 (IEEE 485/1013 explicitly scope
    # themselves to lead-acid only). Falls back to a plain None (renders
    # no citation line) only if the chemistry is somehow not in the map,
    # which should not happen given the enum is closed.
    chemistry_citation = BATTERY_STANDARDS_BY_CHEMISTRY.get(params.battery_chemistry)

    elements.extend(_formula_block(
        "3.2 Battery Bank Sizing",
        "Ah_required = Ah_autonomy x k_t / (eta_batt x eta_wire x F_aging x DOD_max)",
        [
            f"Daily energy demand = {_fmt(load_summary.get('daily_energy_wh'), ' Wh')}",
            f"System DC voltage = {params.system_dc_voltage:.0f} V   |   Autonomy = {params.days_of_autonomy:.1f} days",
            f"Aging factor = {params.aging_factor:.2f}   |   Wire efficiency = {params.wire_efficiency:.2f}",
            f"=> Ah_required = {_fmt(ah_required, ' Ah')}",
            "",
            "N_series = V_bank / V_battery   |   N_parallel = max(ceil(Ah_required/Ah_batt), ceil(I_avg/I_max_cont))",
            f"=> Configuration: {n_series if n_series is not None else '—'}S {n_parallel if n_parallel is not None else '—'}P "
            f"= {total_batteries if total_batteries is not None else '—'} batteries total",
        ],
        f"Selection: {_actual_ah_display(actual_ah)} @ {params.system_dc_voltage:.0f}V "
        f"{params.battery_chemistry.value.replace('_', ' ').title()} battery bank "
        f"({n_series if n_series is not None else '—'}S {n_parallel if n_parallel is not None else '—'}P).",
        styles,
        citation=chemistry_citation,
    ))

    return elements


# ---------------------------------------------------------------------------
# Section 5 — Cable, fuse & voltage drop table
# ---------------------------------------------------------------------------

def _build_cabling_table(result: Dict[str, Any], styles) -> List[Any]:
    cabling = result.get("cabling_summary", {}) or {}

    elements: List[Any] = [
        Paragraph("4. Cable Selection, Fuse &amp; Voltage Drop", styles["SectionHeading"]),
        Paragraph(
            "Conductor sizing per NEC 210.19/215.2 (125% continuous-load factor); the larger of the "
            "ampacity-driven and voltage-drop-driven gauge is always selected. The fuse/breaker rating "
            "shown is the nearest standard NEC 240.6(A) size at or above the computed design current "
            "(shown beneath it for audit purposes).",
            styles["Muted"],
        ),
        Spacer(1, 8),
    ]

    drop_pct = cabling.get("voltage_drop_pct")
    drop_status = "Pass — &lt; 3%" if (drop_pct is not None and drop_pct <= 3.0) else ("Review" if drop_pct is not None else "—")

    # AUDIT-FIELD ADDITION: cable_length_m and i_fuse_computed_a were
    # already returned by cabling.py but never displayed.
    cable_length_m = cabling.get("cable_length_m")
    i_fuse_standard = cabling.get("i_fuse_a")
    i_fuse_computed = cabling.get("i_fuse_computed_a")

    header_style = ParagraphStyle(
        "CableTableHeader", parent=styles["Body"], textColor=colors.white,
        fontName="Helvetica-Bold", fontSize=8.5,
    )
    cell_style = styles["Body"]
    fuse_sub_style = ParagraphStyle(
        "FuseSub", parent=styles["Body"], fontSize=7.5, textColor=_TEXT_MUTED, leading=10,
    )

    # Fuse cell shows the standard (purchasable, primary) rating first,
    # with the raw computed value directly beneath it in muted text — the
    # side-by-side "standard vs. computed" display requested in this
    # session's follow-up, without adding a whole extra column that would
    # crowd the row.
    fuse_cell = Paragraph(
        f"{_fmt(i_fuse_standard, ' A', 1)}"
        f"<br/><font size=7 color='#5B6472'>Computed: {_fmt(i_fuse_computed, ' A', 2)}</font>",
        fuse_sub_style,
    )

    rows = [
        [Paragraph(h, header_style) for h in
         ["Circuit Segment", "Design Current", "Wire Gauge", "Cable Length",
          "Fuse Rating (Std / Computed)", "Voltage Drop"]],
        [
            Paragraph("Battery to Inverter", cell_style),
            Paragraph(_fmt(cabling.get("i_design_a"), " A"), cell_style),
            Paragraph(f"{cabling.get('recommended_awg', '—')} AWG", cell_style),
            Paragraph(_fmt(cable_length_m, " m", 1), cell_style),
            fuse_cell,
            Paragraph(f"{_fmt(drop_pct, '%', 1)} ({drop_status})", cell_style),
        ],
    ]

    col_widths = [w * _CONTENT_WIDTH for w in (0.20, 0.14, 0.12, 0.12, 0.24, 0.18)]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("BACKGROUND", (0, 1), (-1, -1), _SURFACE_RAISED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    return elements


# ---------------------------------------------------------------------------
# Section 6 — Load analysis charts (category bar + category-share donut)
# ---------------------------------------------------------------------------

def _aggregate_by_category(project: Project) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for load in project.loads:
        category = load.category.value if hasattr(load.category, "value") else str(load.category)
        wh = load.nominal_watts * load.quantity * load.daily_hours
        totals[category] = totals.get(category, 0.0) + wh
    return totals


def _chart_panel(title: str, drawing: Drawing, width_mm: float, styles) -> Table:
    panel = Table(
        [[Paragraph(title, styles["ChartTitle"])], [drawing]],
        colWidths=[width_mm * mm],
    )
    panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SURFACE_RAISED),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return panel


def _build_load_analysis_charts(project: Project, styles) -> List[Any]:
    elements: List[Any] = [Paragraph("5. Energy &amp; Load Analysis", styles["SectionHeading"])]

    if not project.loads:
        elements.append(Paragraph("No load data available to chart.", styles["Muted"]))
        return elements

    totals = _aggregate_by_category(project)
    categories = list(totals.keys())
    values = [totals[c] for c in categories]

    if not values or max(values) <= 0:
        elements.append(Paragraph("No positive load values to chart.", styles["Muted"]))
        return elements

    panel_w_mm = (_CONTENT_WIDTH / mm - 6) / 2

    # --- Bar chart: energy by category ---
    bar_drawing = Drawing(panel_w_mm * mm - 10, 150)
    bar_chart = VerticalBarChart()
    bar_chart.x = 35
    bar_chart.y = 40
    bar_chart.height = 100
    bar_chart.width = (panel_w_mm * mm - 10) - 50
    bar_chart.data = [values]
    bar_chart.categoryAxis.categoryNames = [c[:10] for c in categories]
    bar_chart.categoryAxis.labels.angle = 30
    bar_chart.categoryAxis.labels.dy = -10
    bar_chart.categoryAxis.labels.fontSize = 6.5
    bar_chart.valueAxis.valueMin = 0
    bar_chart.valueAxis.labelTextFormat = "%0.0f"
    bar_chart.bars[0].fillColor = _ACCENT
    bar_drawing.add(bar_chart)

    # --- Donut chart: category share of total energy ---
    total_all = sum(values)
    pie_drawing = Drawing(panel_w_mm * mm - 10, 150)
    pie = Pie()
    pie.x = 45
    pie.y = 25
    pie.width = 100
    pie.height = 100
    pie.data = values
    pie.labels = [f"{c[:10]} ({(v / total_all * 100):.0f}%)" for c, v in zip(categories, values)]
    pie.simpleLabels = 0
    pie.slices.strokeWidth = 1
    pie.slices.strokeColor = colors.white
    for i in range(len(values)):
        pie.slices[i].fillColor = _CHART_PALETTE[i % len(_CHART_PALETTE)]
    pie.sideLabels = 1
    pie_drawing.add(pie)

    bar_panel = _chart_panel("Energy by Category (Wh/day)", bar_drawing, panel_w_mm, styles)
    pie_panel = _chart_panel("Load Distribution", pie_drawing, panel_w_mm, styles)

    chart_row = Table(
        [[bar_panel, pie_panel]],
        colWidths=[panel_w_mm * mm + 4, panel_w_mm * mm + 4],
    )
    chart_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(chart_row)
    elements.append(Spacer(1, 14))
    return elements


# ---------------------------------------------------------------------------
# Section 7 — Safety recommendations / engineer notes
# ---------------------------------------------------------------------------

def _build_safety_notes_section(result: Dict[str, Any], styles) -> List[Any]:
    elements: List[Any] = [Paragraph("6. Safety Recommendations &amp; Engineer Notes", styles["SectionHeading"])]

    warnings = result.get("warnings", []) or []
    hard_errors = result.get("hard_errors", []) or []

    if hard_errors:
        elements.append(Paragraph(
            "DATA INTEGRITY WARNING — this saved result contains hard_errors, which should never "
            "occur for a persisted calculation. Do not rely on this report until the project is recalculated.",
            styles["ErrorText"],
        ))
        for err in hard_errors:
            elements.append(Paragraph(f"&bull; {err}", styles["ErrorText"]))
        elements.append(Spacer(1, 6))

    if warnings:
        for w in warnings:
            elements.append(Paragraph(f"&bull; {w}", styles["WarningText"]))
    else:
        elements.append(Paragraph("No warnings were raised for this calculation.", styles["Muted"]))

    return elements