"""
Calculation Engine - Module 5: Cross-Module Validation
Implements Part G of the Battery & Inverter Sizing Engineering Specification.
"""

from typing import Dict, Any, List, Optional

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
    components_colocated: bool = False
) -> Dict[str, Any]:
    """
    Executes cross-module system validation.
    Aggregates warnings and hard errors from all previous modules and performs 
    system-level consistency checks (voltage matching, recharge feasibility, thermal).
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
    # Verify that the physical bank voltage matches the system design and inverter requirements
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

    # 3. Recharge Feasibility Check
    # T_recharge = (Ah_discharged * 1.1) / I_charge_available
    ah_required = battery_result.get("ah_required", 0.0)
    
    if charge_current_a > 0 and charge_window_hours > 0 and ah_required > 0:
        # 1.1 factor accounts for charge inefficiency (Coulombic efficiency)
        t_recharge_required = (ah_required * 1.1) / charge_current_a
        
        if t_recharge_required > charge_window_hours:
            aggregated_warnings.append(
                f"Recharge Feasibility Warning: System requires {t_recharge_required:.1f} hours to fully recharge "
                f"the daily autonomy demand at {charge_current_a}A, but only {charge_window_hours} hours of charge "
                f"window (e.g., daylight or generator run time) are available."
            )

    # 4. Thermal Co-location Check
    if components_colocated:
        aggregated_warnings.append(
            "Thermal Co-location: Battery bank and inverter are marked as sharing an enclosure. "
            "Ensure combined heat dissipation is accounted for in enclosure ventilation to prevent "
            "Arrhenius cycle-life degradation of the batteries."
        )

    # 5. Standby Load Advisory
    # While Module 1 handles total energy, this is a final system-level sanity check reminder.
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
                (ah_required * 1.1) / charge_current_a <= charge_window_hours
                if charge_current_a > 0 else None
            )
        }
    }