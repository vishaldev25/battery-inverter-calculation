"""
Calculation Engine - Module 3: Inverter Sizing
Implements Part E of the Battery & Inverter Sizing Engineering Specification.
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
    """
    Executes inverter sizing logic, validating continuous VA, surge VA, input voltage,
    and output waveform against system requirements. Calculates DC input current.
    """
    warnings: List[str] = []
    hard_errors: List[str] = []

    # 1. Required Capacity Calculations
    # S_continuous = S_peak * (1 + F_future)
    s_continuous_va = peak_apparent_power_va * (1.0 + FUTURE_EXPANSION_FACTOR)
    s_surge_va = surge_apparent_power_va

    # 2. Continuous Capacity Check
    if inverter.continuous_va < s_continuous_va:
        hard_errors.append(
            f"Capacity Violation: Inverter continuous rating ({inverter.continuous_va} VA) "
            f"is insufficient for required load + 20% expansion ({s_continuous_va:.2f} VA)."
        )

    # 3. Surge Capacity Check
    if inverter.surge_va < s_surge_va:
        hard_errors.append(
            f"Surge Violation: Inverter surge rating ({inverter.surge_va} VA) "
            f"is less than the required worst-case motor surge ({s_surge_va:.2f} VA)."
        )

    # 4. Input Voltage Window Check
    # Validates that the battery bank voltage matches the inverter's required DC input.
    if inverter.nominal_dc_voltage != v_bank_actual:
        hard_errors.append(
            f"Voltage Mismatch: Inverter requires a {inverter.nominal_dc_voltage}V DC input, "
            f"but the configured battery bank provides {v_bank_actual}V DC."
        )

    # 5. Waveform Validation
    # Spec mandates Pure Sine Wave if any load category includes motors or sensitive electronics.
    sensitive_categories = {
        LoadCategory.MOTOR_PUMP,
        LoadCategory.MOTOR_COMPRESSOR,
        LoadCategory.HVAC,
        LoadCategory.ELECTRONICS_IT
    }
    has_sensitive_loads = any(load.category in sensitive_categories for load in loads)
    
    # Exact waveform classification to prevent false positives
    normalized_waveform = inverter.waveform.strip().lower()
    is_pure_sine = normalized_waveform == "pure sine wave"

    if has_sensitive_loads and not is_pure_sine:
        hard_errors.append(
            f"Waveform Violation: Connected loads (motors/IT) require a Pure Sine Wave. "
            f"Selected inverter provides: {inverter.waveform}."
        )

    # Block further calculation if hard validation rules are violated
    if hard_errors:
        return _build_response(0.0, 0.0, 0.0, warnings, hard_errors)

    # 6. DC Input Current Calculation (I_DC,cont)
    # I_DC,cont = (S_continuous * PF_avg) / (V_bank * η_inverter)
    pf_avg = peak_real_power_w / peak_apparent_power_va if peak_apparent_power_va > 0 else 1.0

    # Note: Using peak_efficiency as a baseline. For a strictly accurate calculation across all loads, 
    # we flag that the flat nameplate value is being used instead of the dynamic load-fraction curve.
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
        warnings=warnings,
        hard_errors=hard_errors
    )

def _build_response(
    s_continuous_va: float,
    s_surge_va: float,
    i_dc_continuous: float,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure a consistent calculation output schema."""
    return {
        "s_continuous_va": s_continuous_va,
        "s_surge_va": s_surge_va,
        "i_dc_continuous": i_dc_continuous,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }