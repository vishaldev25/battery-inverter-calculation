"""
Core Engineering Constants for Battery & Inverter Sizing Calculation
Reference Standards: IEEE 485, IEEE 1013, NEC Articles 210/215/240
"""
from enum import Enum
from typing import Dict, Tuple

class LoadCategory(str, Enum):
    RESISTIVE = "resistive" 
    LIGHTING_INCANDESCENT = "lighting_incandescent"
    LIGHTING_LED = "lighting_led"
    MOTOR_PUMP = "motor_pump"
    MOTOR_COMPRESSOR = "motor_compressor"
    ELECTRONICS_IT = "electronics_it"
    HVAC = "hvac"
    HEATING_RESISTIVE = "heating_resistive"

class BatteryChemistry(str, Enum):
    FLOODED_LEAD_ACID = "flooded_lead_acid"
    AGM = "agm"
    GEL = "gel"
    LIFEPO4 = "lifepo4"

# ---------------------------------------------------------------------------
# Module 1: Load Characterization (Power Factor & Surge Multipliers)
# ---------------------------------------------------------------------------

LOAD_CHARACTERISTICS: Dict[LoadCategory, Tuple[float, float]] = {
    LoadCategory.RESISTIVE: (1.00, 1.0),
    LoadCategory.LIGHTING_INCANDESCENT: (0.97, 1.0),
    LoadCategory.LIGHTING_LED: (0.70, 1.2),
    LoadCategory.MOTOR_PUMP: (0.80, 4.0),
    LoadCategory.MOTOR_COMPRESSOR: (0.75, 5.5),
    LoadCategory.ELECTRONICS_IT: (0.85, 1.5),
    LoadCategory.HVAC: (0.80, 4.5),
    LoadCategory.HEATING_RESISTIVE: (1.00, 1.0),
}

# ---------------------------------------------------------------------------
# Module 2: Battery Bank Sizing (IEEE 485 / IEEE 1013 — lead-acid chemistries.
# LiFePO4 is NOT within IEEE 485/1013's scope; see BATTERY_STANDARDS_BY_CHEMISTRY
# below, consumed by backend/report/pdf_builder.py for accurate citation.)
# ---------------------------------------------------------------------------

BATTERY_CHEMISTRY_DEFAULTS: Dict[BatteryChemistry, dict] = {
    BatteryChemistry.FLOODED_LEAD_ACID: {
        "dod_max": 0.50,
        "dod_abs_max": 0.80,
        "efficiency": 0.85,
        "peukert_k": 1.20,
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 45.0
    },
    BatteryChemistry.AGM: {
        "dod_max": 0.50,
        "dod_abs_max": 0.80,
        "efficiency": 0.90,
        "peukert_k": 1.12,
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 40.0
    },
    BatteryChemistry.GEL: {
        "dod_max": 0.50,
        "dod_abs_max": 0.80,
        "efficiency": 0.90,
        "peukert_k": 1.12,
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 40.0
    },
    BatteryChemistry.LIFEPO4: {
        "dod_max": 0.85,
        "dod_abs_max": 1.00,
        "efficiency": 0.97,
        "peukert_k": 1.01,
        "min_operating_temp_c": -10.0,
        "max_operating_temp_c": 45.0
    }
}

# Chemistry-accurate standards citation, per IEEE's own published scope:
# IEEE 485-2020 and IEEE 1013-2019 explicitly limit their scope to
# lead-acid batteries (both standards' front matter excludes other
# chemistries). Citing them for LiFePO4 sizing is factually incorrect and
# was flagged in the Feature 16 engineering review — fixed here at the
# single source of truth so every consumer (PDF, future dashboard) cites
# correctly without re-deciding this per call site.
BATTERY_STANDARDS_BY_CHEMISTRY: Dict[BatteryChemistry, str] = {
    BatteryChemistry.FLOODED_LEAD_ACID: "IEEE 485-2020 (Vented Lead-Acid Battery Sizing)",
    BatteryChemistry.AGM: "IEEE 1188 (VRLA/Sealed Lead-Acid Battery Sizing)",
    BatteryChemistry.GEL: "IEEE 1188 (VRLA/Sealed Lead-Acid Battery Sizing)",
    BatteryChemistry.LIFEPO4: "IEC 62619 (Lithium Cell/Battery Safety) / IEC 63056 (Lithium ESS Batteries)",
}

TEMP_CORRECTION_TABLE_C: Dict[float, float] = {
    25.0: 1.00,
    20.0: 1.04,
    15.0: 1.07,
    10.0: 1.11,
    5.0: 1.15,
    0.0: 1.19,
    -10.0: 1.30,
    -20.0: 1.40
}

def fahrenheit_to_celsius(f: float) -> float:
    """Helper purely for data translation, actual temp math happens in calc modules."""
    return (f - 32) * 5.0 / 9.0

DEFAULT_WIRE_EFFICIENCY = 0.97
DEFAULT_AGING_FACTOR = 0.80

# ---------------------------------------------------------------------------
# Module 3 & 4: Inverter & Cable Sizing Constraints
# ---------------------------------------------------------------------------

STANDARD_DC_SYSTEM_VOLTAGES = [12.0, 24.0, 48.0, 96.0, 120.0, 240.0, 384.0, 480.0]
FUTURE_EXPANSION_FACTOR = 0.20
CONTINUOUS_LOAD_FACTOR_NEC = 1.25
DEFAULT_INVERTER_EFFICIENCY = 0.90

# NEC 240.6(A) standard ampere ratings for fuses and inverse-time circuit
# breakers. A computed design/fuse current (e.g. 34.10A) is not a
# purchasable part — the actual protective device must be the next
# standard rating at or above the computed value. This was a confirmed
# gap (Feature 16 engineering review): backend/calculation/cabling.py
# previously returned the raw computed float as "the fuse rating."
STANDARD_FUSE_SIZES_A = [
    15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100,
    110, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 600,
]

MAX_PARALLEL_STRINGS_DEFAULT = 4
HIGH_TEMP_DERATING_THRESHOLD_C = 30.0
LIFEPO4_MIN_CHARGE_TEMP_C = 0.0