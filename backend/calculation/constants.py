"""
Core Engineering Constants for Battery & Inverter Sizing Calculation
Reference Standards: IEEE 485, IEEE 1013, NEC Articles 210/215
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

# Maps LoadCategory to a tuple of (Default Power Factor, Surge Multiplier)
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
# Module 2: Battery Bank Sizing (IEEE 485 / IEEE 1013)
# ---------------------------------------------------------------------------

# Default values for different battery chemistries
# Values: DOD_max (design), DOD_abs_max, Round-trip Efficiency, Default Peukert Exponent
BATTERY_CHEMISTRY_DEFAULTS: Dict[BatteryChemistry, dict] = {
    BatteryChemistry.FLOODED_LEAD_ACID: {
        "dod_max": 0.50,
        "dod_abs_max": 0.80,
        "efficiency": 0.85,
        "peukert_k": 1.20, # Midpoint of 1.15-1.25
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 45.0
    },
    BatteryChemistry.AGM: {
        "dod_max": 0.50, # Conservative end of 0.50-0.60
        "dod_abs_max": 0.80,
        "efficiency": 0.90,
        "peukert_k": 1.12, # Midpoint of 1.10-1.15
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 40.0
    },
    BatteryChemistry.GEL: {
        "dod_max": 0.50, # Conservative end of 0.50-0.60
        "dod_abs_max": 0.80,
        "efficiency": 0.90,
        "peukert_k": 1.12, # Midpoint of 1.10-1.15
        "min_operating_temp_c": -20.0,
        "max_operating_temp_c": 40.0
    },
    BatteryChemistry.LIFEPO4: {
        "dod_max": 0.85, # Midpoint of 0.80-0.90
        "dod_abs_max": 1.00,
        "efficiency": 0.97,
        "peukert_k": 1.01, # Midpoint of ~1.00-1.02
        "min_operating_temp_c": -10.0,
        "max_operating_temp_c": 45.0
    }
}

# IEEE 485 Temperature Correction Table (kt) referenced to 25°C
# Note: For calculation logic, values should be linearly interpolated if falling between keys.
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

# General battery sizing defaults
DEFAULT_WIRE_EFFICIENCY = 0.97
DEFAULT_AGING_FACTOR = 0.80

# ---------------------------------------------------------------------------
# Module 3 & 4: Inverter & Cable Sizing Constraints
# ---------------------------------------------------------------------------

STANDARD_DC_SYSTEM_VOLTAGES = [12.0, 24.0, 48.0, 96.0, 120.0, 240.0, 384.0, 480.0]
FUTURE_EXPANSION_FACTOR = 0.20
CONTINUOUS_LOAD_FACTOR_NEC = 1.25
DEFAULT_INVERTER_EFFICIENCY = 0.90

# Standard limits
MAX_PARALLEL_STRINGS_DEFAULT = 4 # Conservative threshold for circulating current risk
HIGH_TEMP_DERATING_THRESHOLD_C = 30.0 # Above this, Arrhenius aging warning is triggered
LIFEPO4_MIN_CHARGE_TEMP_C = 0.0 # Hard safety constraint against lithium plating