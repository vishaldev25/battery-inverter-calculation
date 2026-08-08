"""
Row-level validation against the REAL LoadItem model (Architecture Invariant 8:
every accepted row must pass the same Pydantic validation as manual entry —
no parallel CSV-specific schema is used here).
"""
from typing import Any, Dict

import pandas as pd
from pydantic import ValidationError

from backend.csv.models import CsvRowError, CsvValidationResult
from backend.projects.models import LoadItem

# Fields where a blank/missing cell should fall through to LoadItem's own
# Pydantic default, rather than being passed through as an empty string
# (which would fail type coercion instead of applying the default).
# Note: power_factor defaults to None when blank, allowing calculate_load_profile()
# to resolve the category-specific default from LOAD_CHARACTERISTICS (e.g., 0.80
# for motor_pump) instead of using LoadItem's hardcoded fallback.
OPTIONAL_FIELDS_WITH_DEFAULTS = {
    "category",
    "quantity",
    "power_factor",
    "daily_hours",
    "surge_multiplier",
    "is_concurrent",
}

# Fields that must be coerced to bool explicitly — pandas reads everything
# as str (parser.py uses dtype=str), so "true"/"false"/"1"/"0" all need a
# deliberate mapping rather than relying on Python's truthy-string bugs
# (bool("False") is True in plain Python — must not let that slip through).
_TRUE_STRINGS = {"true", "1", "yes", "y"}
_FALSE_STRINGS = {"false", "0", "no", "n"}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _coerce_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in _TRUE_STRINGS:
        return True
    if normalized in _FALSE_STRINGS:
        return False
    raise ValueError(f"'{raw}' is not a recognized true/false value")


def _build_row_dict(row: "pd.Series") -> Dict[str, Any]:
    """
    Converts one raw CSV row (all strings, per parser.py's dtype=str) into a
    dict suitable for LoadItem(**row_dict):
      - blank/NaN cells on fields with a default are dropped entirely, so
        Pydantic's own field default applies (parity with manual entry).
      - is_concurrent is explicitly coerced to bool when present, since
        pandas gives us a string, not a real bool.
      - numeric fields are left as strings; Pydantic coerces numeric strings
        natively, so no manual float()/int() conversion is duplicated here.
    """
    row_dict: Dict[str, Any] = {}

    for field, value in row.items():
        if _is_blank(value):
            if field in OPTIONAL_FIELDS_WITH_DEFAULTS:
                continue  # let LoadItem's default apply
            row_dict[field] = value  # required field left blank -> LoadItem will reject it
            continue

        if field == "is_concurrent":
            row_dict[field] = _coerce_bool(str(value))
        else:
            row_dict[field] = value

    return row_dict


def validate_rows(df: pd.DataFrame) -> CsvValidationResult:
    """
    Validates every row of an already structurally-checked DataFrame
    (see parser.py) against the real LoadItem model. Never drops a row
    silently — every row ends up in exactly one of valid_rows/invalid_rows.
    """
    valid_rows = []
    invalid_rows = []

    for offset, (_, row) in enumerate(df.iterrows()):
        row_number = offset + 2  # +1 for 1-indexing, +1 because header is row 1
        raw_data = row.to_dict()

        try:
            row_dict = _build_row_dict(row)
        except ValueError as exc:
            invalid_rows.append(
                CsvRowError(row_number=row_number, raw_data=raw_data, errors=[str(exc)])
            )
            continue

        try:
            load_item = LoadItem(**row_dict)
        except ValidationError as exc:
            error_messages = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            invalid_rows.append(
                CsvRowError(row_number=row_number, raw_data=raw_data, errors=error_messages)
            )
            continue

        valid_rows.append(load_item)

    total_rows = len(df)
    return CsvValidationResult(
        total_rows=total_rows,
        valid_count=len(valid_rows),
        invalid_count=len(invalid_rows),
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
    )