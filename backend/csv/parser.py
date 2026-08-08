"""
CSV structural parsing (Pandas).
Boundary: this module ONLY checks structural validity (headers present,
file not empty). It never performs field-level/row-level validation —
that is validator.py's job (code-standards.md: don't mix concerns).
"""
import io
from typing import List

import pandas as pd

# Must match backend/csv/validator.py's expected LoadItem-mapped columns exactly.
EXPECTED_COLUMNS: List[str] = [
    "name",
    "category",
    "quantity",
    "nominal_watts",
    "power_factor",
    "daily_hours",
    "surge_multiplier",
    "is_concurrent",
]


class CsvStructureError(Exception):
    """Raised for structural problems with an uploaded CSV — distinct from
    row-level validation errors, which never reach this exception type."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def parse_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    """
    Reads raw uploaded CSV bytes into a DataFrame and performs structural
    checks only. Raises CsvStructureError with a specific reason on failure;
    never silently proceeds with a malformed file.
    """
    if not file_bytes or not file_bytes.strip():
        raise CsvStructureError("The uploaded file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        raise CsvStructureError("The uploaded file has no readable header row or data.")
    except pd.errors.ParserError as exc:
        raise CsvStructureError(f"The uploaded file could not be parsed as CSV: {exc}")

    actual_columns = list(df.columns)

    missing = [c for c in EXPECTED_COLUMNS if c not in actual_columns]
    unexpected = [c for c in actual_columns if c not in EXPECTED_COLUMNS]

    if missing:
        raise CsvStructureError(
            f"The uploaded file is missing required column(s): {', '.join(missing)}."
        )
    if unexpected:
        raise CsvStructureError(
            f"The uploaded file has unexpected column(s) not in the template: {', '.join(unexpected)}."
        )

    if df.shape[0] == 0:
        raise CsvStructureError("The uploaded file has a header row but no data rows.")

    # Reorder to the canonical column order so validator.py can rely on it.
    return df[EXPECTED_COLUMNS]