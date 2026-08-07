"""
Calculation Engine - Module 2: Battery Bank Sizing
Implements Part D of the Battery & Inverter Sizing Engineering Specification (IEEE 485 / IEEE 1013).
"""

import math
from typing import Dict, Any, List

from backend.projects.models import ProjectParameters
from backend.catalog.models import BatteryCatalog
from backend.calculation.constants import (
    BATTERY_CHEMISTRY_DEFAULTS,
    TEMP_CORRECTION_TABLE_C,
    BatteryChemistry
)

def interpolate_temperature_correction(temp_c: float) -> float:
    """
    Linearly interpolates the IEEE 485 temperature correction factor (k_t) referenced to 25°C.
    """
    temps = sorted(TEMP_CORRECTION_TABLE_C.keys())
    
    # Boundary clamping
    if temp_c >= temps[-1]:
        return TEMP_CORRECTION_TABLE_C[temps[-1]]
    if temp_c <= temps[0]:
        return TEMP_CORRECTION_TABLE_C[temps[0]]
        
    for i in range(len(temps) - 1):
        t1, t2 = temps[i], temps[i+1]
        if t1 <= temp_c <= t2:
            k1, k2 = TEMP_CORRECTION_TABLE_C[t1], TEMP_CORRECTION_TABLE_C[t2]
            # Linear interpolation
            return k1 + (k2 - k1) * (temp_c - t1) / (t2 - t1)
    
    return 1.0

def calculate_battery_bank(
    daily_energy_wh: float,
    peak_real_power_w: float,
    surge_apparent_power_va: float,
    params: ProjectParameters,
    battery: BatteryCatalog
) -> Dict[str, Any]:
    """
    Executes battery bank sizing logic including Ah demand, temperature correction, 
    Peukert adjustment, and the series/parallel string solver.
    """
    warnings: List[str] = []
    hard_errors: List[str] = []

    # 1. Validation & Hard Safety Constraints
    if params.ambient_temp_c < 0 and battery.chemistry == BatteryChemistry.LIFEPO4:
        hard_errors.append("Safety Violation: Charging LiFePO4 below 0°C damages cells (lithium plating). Battery heater required.")
        
    # Series String Check
    n_series_raw = params.system_dc_voltage / battery.nominal_voltage
    if not n_series_raw.is_integer():
        hard_errors.append(
            f"Invalid Configuration: System voltage ({params.system_dc_voltage}V) "
            f"is not cleanly divisible by battery module voltage ({battery.nominal_voltage}V)."
        )
    
    n_series = int(n_series_raw)

    # Block further calculation if hard validation rules are violated
    if hard_errors:
        return _build_response(0, 0, 0, 0, 0, 0, warnings, hard_errors)

    # 2. Advisory Flags & Warnings
    if params.ambient_temp_c > 30:
        warnings.append(f"Cycle life derating: Ambient temperature ({params.ambient_temp_c}°C) exceeds 30°C. Arrhenius aging will reduce cycle life.")
    
    if battery.chemistry == BatteryChemistry.FLOODED_LEAD_ACID:
        warnings.append("Ventilation required: Flooded lead-acid batteries emit hydrogen gas during charging and require regular equalization.")
        
    if battery.chemistry == BatteryChemistry.LIFEPO4:
        warnings.append("BMS Mandatory: A Battery Management System is required to protect LiFePO4 cells from overcharge/over-discharge.")

    # 3. Extract baseline variables with parameter overrides
    dod_max = params.max_dod_override if params.max_dod_override else battery.max_dod_recommended
    eta_batt = battery.round_trip_efficiency
    peukert_k = battery.peukert_exponent

    # 4. Base Ah Demand
    ah_day = daily_energy_wh / params.system_dc_voltage
    ah_autonomy = ah_day * params.days_of_autonomy

    # 5. Temperature Correction (k_t)
    k_t = interpolate_temperature_correction(params.ambient_temp_c)

    # 6. Full Correction Chain (Ah_required)
    denominator = eta_batt * params.wire_efficiency * params.aging_factor * dod_max
    ah_required = ah_autonomy * (k_t / denominator)

    # 7. Current Calculations
    i_avg = peak_real_power_w / (params.system_dc_voltage * params.target_inverter_efficiency)
    
    # 8. Peukert & String Solver
    
    # Initialize baseline string count from continuous current minimum
    n_parallel_cont = 1
    if battery.max_continuous_discharge_amps:
        n_parallel_cont = math.ceil(i_avg / battery.max_continuous_discharge_amps)

    # Initialize combined minimum string count
    n_parallel = max(math.ceil(ah_required / battery.capacity_ah), n_parallel_cont)
    
    rated_hours = 20.0  # Standard C/20 rating period
    rated_current = battery.capacity_ah / rated_hours
    effective_ah_per_battery = battery.capacity_ah
    
    # Iteratively stabilize parallel string count under Peukert's Law
    if peukert_k > 1.0:
        while True:
            i_string_avg = i_avg / n_parallel
            
            if i_string_avg > rated_current:
                effective_ah_per_battery = battery.capacity_ah * ((rated_current / i_string_avg) ** (peukert_k - 1))
            else:
                effective_ah_per_battery = battery.capacity_ah
                
            new_n_parallel_ah = math.ceil(ah_required / effective_ah_per_battery)
            new_n_parallel = max(new_n_parallel_ah, n_parallel_cont)
            
            # Break if the string count has stabilized
            if new_n_parallel == n_parallel:
                break
                
            # Failsafe against theoretical runaway
            if new_n_parallel > 50:
                n_parallel = new_n_parallel
                break
                
            n_parallel = new_n_parallel

    # Final string-level warning
    if n_parallel > 4:
        warnings.append(
            f"Current-sharing risk: Design requires {n_parallel} parallel strings. "
            "Configurations above 4 parallel strings require active balancing or strict busbar symmetry."
        )

    # 9. Final physical sizing output
    total_batteries = n_series * n_parallel
    actual_ah_capacity = battery.capacity_ah * n_parallel

    return _build_response(
        ah_required=ah_required,
        n_series=n_series,
        n_parallel=n_parallel,
        total_batteries=total_batteries,
        actual_ah_capacity=actual_ah_capacity,
        effective_ah_per_string=effective_ah_per_battery,
        warnings=warnings,
        hard_errors=hard_errors
    )

def _build_response(
    ah_required: float,
    n_series: int,
    n_parallel: int,
    total_batteries: int,
    actual_ah_capacity: float,
    effective_ah_per_string: float,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure consistent calculation output schema."""
    return {
        "ah_required": ah_required,
        "n_series": n_series,
        "n_parallel": n_parallel,
        "total_batteries": total_batteries,
        "actual_ah_capacity": actual_ah_capacity,
        "effective_ah_per_string": effective_ah_per_string,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }