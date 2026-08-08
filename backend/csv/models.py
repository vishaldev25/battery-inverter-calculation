"""
Response schemas for CSV upload validation.
Boundary: backend/csv/ — this module only reports validation results;
it never performs calculation or persists anything (architecture.md).
"""
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from backend.projects.models import LoadItem


class CsvRowError(BaseModel):
    """A single rejected CSV row, with the exact reason(s) it failed."""

    row_number: int = Field(
        ..., description="1-indexed row number as it would appear in a spreadsheet (header = row 1)"
    )
    raw_data: Dict[str, Any] = Field(
        ..., description="The original row values exactly as submitted, before any coercion"
    )
    errors: List[str] = Field(
        ..., description="Specific, field-level reasons this row was rejected (never a generic message)"
    )


class CsvValidationResult(BaseModel):
    """Full per-row validation report for one uploaded CSV file."""

    total_rows: int
    valid_count: int
    invalid_count: int
    valid_rows: List[LoadItem]
    invalid_rows: List[CsvRowError]