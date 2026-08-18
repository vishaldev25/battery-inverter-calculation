"""
Report Generation Module
Owns PDF generation (ReportLab) only. Reads project.last_calculation_result
as-is and formats it — never recalculates, never touches backend/calculation/
functions directly, per architecture.md's backend/report/ boundary and
Invariant 1.
"""