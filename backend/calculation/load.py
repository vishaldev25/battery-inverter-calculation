"""
Calculation Engine - Module 1: Load Characterization
Implements Part B and C of the Battery & Inverter Sizing Engineering Specification.
"""

from typing import List, Dict, Any
from backend.projects.models import LoadItem
from backend.calculation.constants import LoadCategory, LOAD_CHARACTERISTICS


def _resolve_power_factor(load: LoadItem) -> float:
    """
    Resolves the effective power factor for a load: the explicit override
    if the user supplied one, otherwise the category-based default from
    LOAD_CHARACTERISTICS (Part C). This is the single point where PF
    ambiguity is resolved — nothing downstream should read
    `load.power_factor` directly, since it may be None.
    """
    if load.power_factor is not None:
        return load.power_factor
    return LOAD_CHARACTERISTICS[load.category][0]


def calculate_load_profile(loads: List[LoadItem]) -> Dict[str, Any]:
    """
    Aggregates a list of LoadItems to calculate daily energy, peak demand, and surge demand.
    Returns a dictionary containing the results, along with any engineering warnings or hard errors.
    """
    warnings: List[str] = []
    hard_errors: List[str] = []

    total_daily_energy_wh = 0.0
    peak_real_power_w = 0.0
    peak_apparent_power_va = 0.0

    # 1. Validation Pre-pass
    if not loads:
        hard_errors.append("Load list is empty. Cannot perform sizing calculations.")
        return _build_response(0, 0, 0, 0, warnings, hard_errors)

    all_concurrent = True

    for load in loads:
        # Part B1 Constraints
        if load.nominal_watts <= 0:
            hard_errors.append(f"Load '{load.name}' has invalid nominal watts: {load.nominal_watts}. Must be > 0.")
        if not (0 <= load.daily_hours <= 24):
            hard_errors.append(f"Load '{load.name}' has invalid daily hours: {load.daily_hours}. Must be between 0 and 24.")
        # power_factor may legitimately be None (category default applies) —
        # only range-check it when the user gave an explicit override.
        # (Pydantic's gt=0/le=1.0 on the field already enforces this at the
        # model boundary; this check stays as defense-in-depth, mirroring
        # the explicit nominal_watts/daily_hours checks above.)
        if load.power_factor is not None and (load.power_factor <= 0 or load.power_factor > 1.0):
            hard_errors.append(f"Load '{load.name}' has invalid power factor: {load.power_factor}. Must be > 0 and <= 1.0.")

        if not load.is_concurrent:
            all_concurrent = False

    # Block further calculation if hard validation rules are violated
    if hard_errors:
        return _build_response(0, 0, 0, 0, warnings, hard_errors)

    if all_concurrent:
        warnings.append("No diversity applied (all loads set to concurrent) — this is a conservative (larger) design; consider reviewing actual simultaneous usage.")

    # 2. Base Accumulations
    for load in loads:
        effective_pf = _resolve_power_factor(load)

        # Pydantic model uses a boolean `is_concurrent` which maps to SF=1.0 or SF=0.0 for peak calculations.
        sf_peak = 1.0 if load.is_concurrent else 0.0

        # Ei = Pi * qty * ti (Energy is consumed regardless of peak overlap; PF doesn't affect Wh)
        energy_i = load.nominal_watts * load.quantity * load.daily_hours
        total_daily_energy_wh += energy_i

        # P_peak = sum(Pi * qty * SFi)
        peak_real_power_w += (load.nominal_watts * load.quantity * sf_peak)

        # S_peak = sum((Pi * qty * SFi) / PFi)
        peak_apparent_power_va += (load.nominal_watts * load.quantity * sf_peak) / effective_pf

    # 3. Surge Calculation
    # S_surge = max_k [ (P_k * M_k) + sum_j!=k (P_j * qty_j * SF_j / PF_j) ]
    # Evaluated across motor-type loads to find the worst case.
    motor_categories = {
        LoadCategory.MOTOR_PUMP,
        LoadCategory.MOTOR_COMPRESSOR,
        LoadCategory.HVAC
    }

    max_surge_va = peak_apparent_power_va  # Baseline is standard peak if no motors surge

    for k, load_k in enumerate(loads):
        if load_k.category in motor_categories:
            # Component 1: The single surging motor
            # Note: Surge multiplier (M_k) applies to the base nominal watts
            surge_k_va = load_k.nominal_watts * load_k.surge_multiplier

            # Component 2: All other loads running concurrently
            background_va = 0.0
            for j, load_j in enumerate(loads):
                if j != k:
                    sf_j = 1.0 if load_j.is_concurrent else 0.0
                    pf_j = _resolve_power_factor(load_j)
                    background_va += (load_j.nominal_watts * load_j.quantity * sf_j) / pf_j

            candidate_surge_va = surge_k_va + background_va
            if candidate_surge_va > max_surge_va:
                max_surge_va = candidate_surge_va

    return _build_response(
        daily_energy_wh=total_daily_energy_wh,
        peak_real_power_w=peak_real_power_w,
        peak_apparent_power_va=peak_apparent_power_va,
        surge_apparent_power_va=max_surge_va,
        warnings=warnings,
        hard_errors=hard_errors
    )


def _build_response(
    daily_energy_wh: float,
    peak_real_power_w: float,
    peak_apparent_power_va: float,
    surge_apparent_power_va: float,
    warnings: List[str],
    hard_errors: List[str]
) -> Dict[str, Any]:
    """Helper to ensure consistent calculation output schema across the engine."""
    return {
        "daily_energy_wh": daily_energy_wh,
        "peak_real_power_w": peak_real_power_w,
        "peak_apparent_power_va": peak_apparent_power_va,
        "surge_apparent_power_va": surge_apparent_power_va,
        "warnings": warnings,
        "hard_errors": hard_errors,
        "is_valid": len(hard_errors) == 0
    }