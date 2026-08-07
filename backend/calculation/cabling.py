"""
Calculation Engine - Module 4: Cable & Protection Sizing
Implements Part F of the Battery & Inverter Sizing Engineering Specification (NEC / IEC 60364).
"""

from typing import Dict, Any, List, Optional

# Standard NEC Copper Wire Ampacity (75°C insulation) and DC Resistance (Ohms/km)
# Sizes ranging from 14 AWG up to 4/0 AWG
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
    # I_design = I_continuous * 1.25 (Hard rule for continuous loads)
    i_design = i_dc_continuous * 1.25
    
    # 2. Overcurrent Protection (Fuse)
    # I_fuse = I_continuous * 1.25
    i_fuse = i_dc_continuous * 1.25

    # Hard Input Validation
    if i_dc_continuous <= 0 or v_bank_actual <= 0:
        hard_errors.append("Invalid input: Continuous current and bank voltage must be greater than zero.")
    if cable_length_m < 0:
        hard_errors.append("Invalid input: Cable length cannot be negative.")
        
    if hard_errors:
        return _build_response(0.0, 0.0, None, 0.0, 0.0, warnings, hard_errors)

    # 3. Cable Selection (Ampacity and Voltage Drop)
    selected_cable: Optional[Dict[str, Any]] = None
    voltage_drop_v = 0.0
    voltage_drop_pct = 100.0
    
    # Voltage drop constraint: V_drop <= 0.03 * V_bank_actual (3%)
    max_allowable_drop_v = 0.03 * v_bank_actual
    
    # Iterate through standard cables from smallest to largest
    for cable in AWG_COPPER_TABLE:
        # Check Ampacity
        if cable["ampacity"] >= i_design:
            # Check Voltage Drop
            # V_drop = (2 * L * I * R_cable) / 1000
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

    # 4. Mandatory System Advisories / Warnings
    warnings.append("Disconnect Switch: An accessible, rated disconnect switch is required between the battery bank and inverter (NEC 690.13).")
    warnings.append("Grounding: Ensure system and equipment grounding complies with NEC 690.41/690.45 or local equivalent.")
    
    if n_parallel_strings > 1:
        warnings.append(
            f"String Fusing Required: The battery bank has {n_parallel_strings} parallel strings. "
            "Each parallel string must carry its own overcurrent device at the point it joins the common bus."
        )

    return _build_response(
        i_design=i_design,
        i_fuse=i_fuse,
        recommended_awg=awg_result,
        voltage_drop_v=voltage_drop_v,
        voltage_drop_pct=voltage_drop_pct,
        warnings=warnings,
        hard_errors=hard_errors
    )

def _build_response(
    i_design: float,
    i_fuse: float,
    recommended_awg: Optional[str],
    voltage_drop_v: float,
    voltage_drop_pct: float,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure a consistent calculation output schema."""
    return {
        "i_design_a": i_design,
        "i_fuse_a": i_fuse,
        "recommended_awg": recommended_awg,
        "voltage_drop_v": voltage_drop_v,
        "voltage_drop_pct": voltage_drop_pct,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }