"""
Calculation Engine - Module 3: Inverter Sizing
Implements Part E of the Battery & Inverter Sizing Engineering Specification.

AUDIT FIELD ADDED (Feature 16 engineering review): pf_avg and the
peak_efficiency value actually used were already computed/read locally
but never returned — a report could only say "peak efficiency was used,"
never show the number. No formula changed.
"""

from typing import List, Dict, Any
from backend.projects.models import LoadItem
from backend.catalog.models import InverterCatalog
from backend.calculation.constants import LoadCategory, FUTURE_EXPANSION_FACTOR

def calculate_inverter_sizing(
    peak_apparent_power_va: float,
    peak_real_power_w: float,
    surge_apparent_power_va: float,
    v_bank_actual: float,
    loads: List[LoadItem],
    inverter: InverterCatalog
) -> Dict[str, Any]:
    warnings: List[str] = []
    hard_errors: List[str] = []

    s_continuous_va = peak_apparent_power_va * (1.0 + FUTURE_EXPANSION_FACTOR)
    s_surge_va = surge_apparent_power_va

    if inverter.continuous_va < s_continuous_va:
        hard_errors.append(
            f"Capacity Violation: Inverter continuous rating ({inverter.continuous_va} VA) "
            f"is insufficient for required load + 20% expansion ({s_continuous_va:.2f} VA)."
        )

    if inverter.surge_va < s_surge_va:
        hard_errors.append(
            f"Surge Violation: Inverter surge rating ({inverter.surge_va} VA) "
            f"is less than the required worst-case motor surge ({s_surge_va:.2f} VA)."
        )

    if inverter.nominal_dc_voltage != v_bank_actual:
        hard_errors.append(
            f"Voltage Mismatch: Inverter requires a {inverter.nominal_dc_voltage}V DC input, "
            f"but the configured battery bank provides {v_bank_actual}V DC."
        )

    sensitive_categories = {
        LoadCategory.MOTOR_PUMP,
        LoadCategory.MOTOR_COMPRESSOR,
        LoadCategory.HVAC,
        LoadCategory.ELECTRONICS_IT
    }
    has_sensitive_loads = any(load.category in sensitive_categories for load in loads)
    
    normalized_waveform = inverter.waveform.strip().lower()
    is_pure_sine = normalized_waveform == "pure sine wave"

    if has_sensitive_loads and not is_pure_sine:
        hard_errors.append(
            f"Waveform Violation: Connected loads (motors/IT) require a Pure Sine Wave. "
            f"Selected inverter provides: {inverter.waveform}."
        )

    if hard_errors:
        return _build_response(0.0, 0.0, 0.0, None, None, warnings, hard_errors)

    pf_avg = peak_real_power_w / peak_apparent_power_va if peak_apparent_power_va > 0 else 1.0

    efficiency = inverter.peak_efficiency
    warnings.append(
        "Using peak efficiency rating for DC current calculation. "
        "For maximum precision, verify against the manufacturer's efficiency curve at the specific load fraction."
    )

    if v_bank_actual > 0 and efficiency > 0:
        i_dc_continuous = (s_continuous_va * pf_avg) / (v_bank_actual * efficiency)
    else:
        i_dc_continuous = 0.0

    return _build_response(
        s_continuous_va=s_continuous_va,
        s_surge_va=s_surge_va,
        i_dc_continuous=i_dc_continuous,
        pf_avg_used=pf_avg,
        efficiency_used=efficiency,
        warnings=warnings,
        hard_errors=hard_errors
    )

def _build_response(
    s_continuous_va: float,
    s_surge_va: float,
    i_dc_continuous: float,
    pf_avg_used,
    efficiency_used,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure a consistent calculation output schema."""
    return {
        "s_continuous_va": s_continuous_va,
        "s_surge_va": s_surge_va,
        "i_dc_continuous": i_dc_continuous,
        # --- audit fields (Feature 16 review) ---
        "pf_avg_used": pf_avg_used,
        "efficiency_used": efficiency_used,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }