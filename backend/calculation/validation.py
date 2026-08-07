"""
Calculation Engine - Module 5: Cross-Module Validation
Implements Part G of the Battery & Inverter Sizing Engineering Specification.
"""

from typing import Dict, Any, List

def validate_system_design(
    load_result: Dict[str, Any],
    battery_result: Dict[str, Any],
    inverter_result: Dict[str, Any],
    cabling_result: Dict[str, Any],
    system_design_voltage: float,
    inverter_input_voltage: float,
    battery_module_voltage: float,
    charge_current_a: float = 0.0,
    charge_window_hours: float = 0.0,
    components_colocated: bool = False,
    battery_surge_limit_a: float = 0.0,
    inverter_surge_limit_a: float = 0.0,
    cable_rating_a: float = 0.0,
    fuse_rating_a: float = 0.0,
    inverter_efficiency: float = 1.0
) -> Dict[str, Any]:
    """
    Executes cross-module system validation.
    Aggregates warnings and hard errors from all previous modules and performs 
    system-level consistency checks (voltage matching, surge limits, recharge feasibility, thermal).
    """
    aggregated_warnings: List[str] = []
    aggregated_hard_errors: List[str] = []

    # 1. Aggregate existing module outputs
    for module_res in [load_result, battery_result, inverter_result, cabling_result]:
        if "warnings" in module_res:
            aggregated_warnings.extend(module_res["warnings"])
        if "hard_errors" in module_res:
            aggregated_hard_errors.extend(module_res["hard_errors"])

    # 2. Voltage Consistency Check
    n_series = battery_result.get("n_series", 0)
    v_bank_actual = n_series * battery_module_voltage

    if v_bank_actual > 0:
        if v_bank_actual != system_design_voltage:
            aggregated_hard_errors.append(
                f"System Voltage Mismatch: Actual battery bank voltage ({v_bank_actual}V) "
                f"does not match the target system design voltage ({system_design_voltage}V)."
            )
        
        if v_bank_actual != inverter_input_voltage:
            aggregated_hard_errors.append(
                f"Inverter Voltage Mismatch: Actual battery bank voltage ({v_bank_actual}V) "
                f"does not match the required inverter input voltage ({inverter_input_voltage}V)."
            )

    # 3. Surge Current Path Validation
    surge_va = load_result.get("surge_apparent_power_va", 0.0)
    if v_bank_actual > 0 and surge_va > 0 and inverter_efficiency > 0:
        # Convert AC apparent power to DC surge current using inverter efficiency
        i_surge_required = surge_va / (v_bank_actual * inverter_efficiency)

        if battery_surge_limit_a > 0 and i_surge_required > battery_surge_limit_a:
            aggregated_hard_errors.append(
                f"Surge Violation: Required surge current ({i_surge_required:.1f}A) exceeds battery bank limit ({battery_surge_limit_a}A)."
            )
        if inverter_surge_limit_a > 0 and i_surge_required > inverter_surge_limit_a:
            aggregated_hard_errors.append(
                f"Surge Violation: Required surge current ({i_surge_required:.1f}A) exceeds inverter limit ({inverter_surge_limit_a}A)."
            )
        if cable_rating_a > 0 and i_surge_required > cable_rating_a:
            aggregated_hard_errors.append(
                f"Surge Violation: Required surge current ({i_surge_required:.1f}A) exceeds cable ampacity ({cable_rating_a}A)."
            )
        if fuse_rating_a > 0 and i_surge_required > fuse_rating_a:
            aggregated_hard_errors.append(
                f"Surge Violation: Required surge current ({i_surge_required:.1f}A) exceeds fuse rating ({fuse_rating_a}A)."
            )

    # 4. Recharge Feasibility Check
    # Consumes actual discharged Ah output strictly from the battery module
    ah_discharged = battery_result.get("ah_discharged", 0.0)
    
    if charge_current_a > 0 and charge_window_hours > 0 and ah_discharged > 0:
        # 1.1 factor accounts for charge inefficiency (Coulombic efficiency)
        t_recharge_required = (ah_discharged * 1.1) / charge_current_a
        
        if t_recharge_required > charge_window_hours:
            aggregated_warnings.append(
                f"Recharge Feasibility Warning: System requires {t_recharge_required:.1f} hours to fully recharge "
                f"the daily autonomy demand at {charge_current_a}A, but only {charge_window_hours} hours of charge "
                f"window (e.g., daylight or generator run time) are available."
            )

    # 5. Thermal Co-location Check
    if components_colocated:
        aggregated_warnings.append(
            "Thermal Co-location: Battery bank and inverter are marked as sharing an enclosure. "
            "Ensure combined heat dissipation is accounted for in enclosure ventilation to prevent "
            "Arrhenius cycle-life degradation of the batteries."
        )

    # 6. Standby Load Advisory
    if load_result.get("daily_energy_wh", 0) > 0:
        aggregated_warnings.append(
            "Verify that the inverter's 24/7 parasitic/standby draw has been included in the daily load schedule."
        )

    # Deduplicate lists while preserving order
    final_warnings = list(dict.fromkeys(aggregated_warnings))
    final_hard_errors = list(dict.fromkeys(aggregated_hard_errors))

    is_valid = len(final_hard_errors) == 0

    return {
        "is_valid": is_valid,
        "warnings": final_warnings,
        "hard_errors": final_hard_errors,
        "summary": {
            "v_bank_actual": v_bank_actual,
            "system_design_voltage": system_design_voltage,
            "recharge_feasible": (
                ((ah_discharged * 1.1) / charge_current_a <= charge_window_hours)
                if (charge_current_a > 0 and charge_window_hours > 0 and ah_discharged > 0) else None
            )
        }
    }