"""
Calculation Engine - Module 4: Cable & Protection Sizing
Implements Part F of the Battery & Inverter Sizing Engineering Specification (NEC / IEC 60364).

FIX (Feature 16 engineering review, confirmed real): the fuse/breaker
rating is now snapped up to the nearest standard NEC 240.6(A) size via
select_standard_protective_device() — a raw computed float like 34.10A
is not a device anyone can buy, and a fuse sized exactly at the 125%
continuous-load current gives zero margin against motor-starting
transients, which is a real nuisance-tripping risk.

AUDIT FIELDS ADDED: cable_length_m and n_parallel_strings are now echoed
back in the response (they were already function inputs, just never
returned) so a report/dashboard can display exactly what was used,
without re-deriving or guessing it later.
"""

from typing import Dict, Any, List, Optional
from backend.calculation.constants import STANDARD_FUSE_SIZES_A

# Standard NEC Copper Wire Ampacity (75°C insulation) and DC Resistance (Ohms/km)
# Verified against NEC 310.16's 75°C copper column — every value below matches.
AWG_COPPER_TABLE = [
    {"awg": "14", "ampacity": 20.0, "r_per_km": 8.286},
    {"awg": "12", "ampacity": 25.0, "r_per_km": 5.211},
    {"awg": "10", "ampacity": 35.0, "r_per_km": 3.277},
    {"awg": "8", "ampacity": 50.0, "r_per_km": 2.061},
    {"awg": "6", "ampacity": 65.0, "r_per_km": 1.296},
    {"awg": "4", "ampacity": 85.0, "r_per_km": 0.815},
    {"awg": "2", "ampacity": 115.0, "r_per_km": 0.513},
    {"awg": "1/0", "ampacity": 150.0, "r_per_km": 0.322},
    {"awg": "2/0", "ampacity": 175.0, "r_per_km": 0.256},
    {"awg": "4/0", "ampacity": 230.0, "r_per_km": 0.161},
]


def select_standard_protective_device(computed_current_a: float) -> float:
    """
    Returns the smallest STANDARD_FUSE_SIZES_A entry that is >= the
    computed design/fuse current, per NEC 240.6(A). A computed value that
    exceeds every standard size (should not happen for any realistic
    residential/commercial DC system, but guarded rather than silently
    truncated) returns the largest standard size and lets the hard-error
    path below flag it.
    """
    for size in STANDARD_FUSE_SIZES_A:
        if size >= computed_current_a:
            return float(size)
    return float(STANDARD_FUSE_SIZES_A[-1])


def calculate_cabling_and_protection(
    i_dc_continuous: float,
    v_bank_actual: float,
    cable_length_m: float,
    n_parallel_strings: int
) -> Dict[str, Any]:
    """
    Executes cable sizing and overcurrent protection logic.
    Calculates design current, selects adequate AWG, verifies voltage drop, and sizes the fuse.
    """
    warnings: List[str] = []
    hard_errors: List[str] = []
    
    # 1. Design Current Calculation (NEC 210.19 / 215.2)
    i_design = i_dc_continuous * 1.25
    
    # 2. Overcurrent Protection — computed value first, then snapped to a
    # real standard size below (step 3b).
    i_fuse_computed = i_dc_continuous * 1.25

    if i_dc_continuous <= 0 or v_bank_actual <= 0:
        hard_errors.append("Invalid input: Continuous current and bank voltage must be greater than zero.")
    if cable_length_m < 0:
        hard_errors.append("Invalid input: Cable length cannot be negative.")
        
    if hard_errors:
        return _build_response(0.0, 0.0, 0.0, None, 0.0, 0.0, cable_length_m, n_parallel_strings, warnings, hard_errors)

    # 3a. Cable Selection (Ampacity and Voltage Drop)
    selected_cable: Optional[Dict[str, Any]] = None
    voltage_drop_v = 0.0
    voltage_drop_pct = 100.0
    
    max_allowable_drop_v = 0.03 * v_bank_actual
    
    for cable in AWG_COPPER_TABLE:
        if cable["ampacity"] >= i_design:
            v_drop = (2 * cable_length_m * i_design * cable["r_per_km"]) / 1000.0
            if v_drop <= max_allowable_drop_v:
                selected_cable = cable
                voltage_drop_v = v_drop
                voltage_drop_pct = (v_drop / v_bank_actual) * 100.0
                break
    
    if not selected_cable:
        hard_errors.append(
            f"Cable Sizing Failure: Required design current is {i_design:.2f} A, or voltage drop exceeds 3% "
            f"over {cable_length_m}m. Standard single conductors up to 4/0 AWG are insufficient. "
            "Consider parallel conductors or reducing distance."
        )
        awg_result = "N/A"
    else:
        awg_result = selected_cable["awg"]

    # 3b. Snap fuse rating to the nearest standard NEC 240.6(A) size.
    i_fuse_standard = select_standard_protective_device(i_fuse_computed)

    # Standard fuse rating must not exceed the selected conductor's
    # ampacity (NEC 240.4 — conductor must be protected at its ampacity,
    # not the reverse). If the next standard size up would overprotect
    # the wire, this is a real hard error, not a warning — it means the
    # cable needs to go up a size, not that the fuse choice is cosmetic.
    if selected_cable and i_fuse_standard > selected_cable["ampacity"]:
        hard_errors.append(
            f"Protective Device Coordination Failure: The nearest standard fuse/breaker rating "
            f"({i_fuse_standard:.0f} A) exceeds the selected {awg_result} AWG conductor's ampacity "
            f"({selected_cable['ampacity']:.0f} A), per NEC 240.4. Select a larger conductor."
        )

    # 4. Mandatory System Advisories / Warnings
    warnings.append("Disconnect Switch: An accessible, rated disconnect switch is required between the battery bank and inverter (NEC 690.13).")
    warnings.append("Grounding: Ensure system and equipment grounding complies with NEC 690.41/690.45 or local equivalent.")
    
    if n_parallel_strings > 1:
        warnings.append(
            f"String Fusing Required: The battery bank has {n_parallel_strings} parallel strings. "
            "Each parallel string must carry its own overcurrent device at the point it joins the common bus."
        )

    if hard_errors:
        return _build_response(
            i_design, i_fuse_computed, i_fuse_standard, awg_result if selected_cable else None,
            voltage_drop_v, voltage_drop_pct, cable_length_m, n_parallel_strings, warnings, hard_errors,
        )

    return _build_response(
        i_design=i_design,
        i_fuse_computed=i_fuse_computed,
        i_fuse_standard=i_fuse_standard,
        recommended_awg=awg_result,
        voltage_drop_v=voltage_drop_v,
        voltage_drop_pct=voltage_drop_pct,
        cable_length_m=cable_length_m,
        n_parallel_strings=n_parallel_strings,
        warnings=warnings,
        hard_errors=hard_errors,
    )


def _build_response(
    i_design: float,
    i_fuse_computed: float,
    i_fuse_standard: Optional[float],
    recommended_awg: Optional[str],
    voltage_drop_v: float,
    voltage_drop_pct: float,
    cable_length_m: float,
    n_parallel_strings: int,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure a consistent calculation output schema."""
    return {
        "i_design_a": i_design,
        "i_fuse_computed_a": i_fuse_computed,
        # "i_fuse_a" stays as the primary field name for backward
        # compatibility with existing callers (router.py's
        # validate_system_design fuse_rating_a arg, backend/report/) —
        # it now holds the STANDARD, purchasable rating, not the raw
        # computed value. i_fuse_computed_a above preserves the raw
        # number for audit/transparency.
        "i_fuse_a": i_fuse_standard if i_fuse_standard is not None else 0.0,
        "recommended_awg": recommended_awg,
        "voltage_drop_v": voltage_drop_v,
        "voltage_drop_pct": voltage_drop_pct,
        "cable_length_m": cable_length_m,
        "n_parallel_strings": n_parallel_strings,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }