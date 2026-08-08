"""
Static CSV template generation — no DB call, no calculation call.
Boundary: backend/csv/ owns this per architecture.md.
"""
import csv
import io

from backend.csv.parser import EXPECTED_COLUMNS


def generate_template_csv() -> bytes:
    """
    Returns a downloadable CSV template: the exact header row validator.py
    expects, plus one example row. The example row's power_factor is left
    blank deliberately, to demonstrate that a blank cell falls through to
    the category-based default downstream (calculation engine), not a
    guessed number filled in here.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(EXPECTED_COLUMNS)
    writer.writerow(
        [
            "Water Pump",       # name
            "motor_pump",       # category
            "1",                # quantity
            "750",              # nominal_watts
            "",                 # power_factor (blank -> category default applies)
            "4",                # daily_hours
            "4.0",              # surge_multiplier
            "True",             # is_concurrent
        ]
    )

    return buffer.getvalue().encode("utf-8")