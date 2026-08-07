"""
Backend API Router - Calculation Engine Endpoint
Wires Features 03-07 into a cohesive, stateless calculation pipeline.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# Import Pydantic models
from backend.projects.models import LoadItem, ProjectParameters
from backend.catalog.models import BatteryCatalog, InverterCatalog

# Import pure calculation engine modules
from backend.calculation.load import calculate_load_profile
from backend.calculation.battery import calculate_battery_bank
from backend.calculation.inverter import calculate_inverter_sizing
from backend.calculation.cabling import calculate_cabling_and_protection
from backend.calculation.validation import validate_system_design

router = APIRouter(prefix="/api/projects", tags=["Calculation Engine"])


class CalculationRequest(BaseModel):
    """Payload schema for stateless calculation execution."""
    loads: List[LoadItem] = Field(..., min_items=1, description="List of electrical loads")
    parameters: ProjectParameters = Field(..., description="System parameters and environment settings")
    selected_battery: BatteryCatalog = Field(..., description="Candidate or selected battery spec")
    selected_inverter: InverterCatalog = Field(..., description="Candidate or selected inverter spec")
    cable_length_m: float = Field(default=5.0, ge=0.1, description="One-way cable length between battery bank and inverter in meters")
    charge_current_a: float = Field(default=0.0, ge=0.0, description="Available charging current in Amps")
    charge_window_hours: float = Field(default=0.0, ge=0.0, description="Available charging duration per day in hours")
    components_colocated: bool = Field(default=False, description="Whether battery and inverter share the same thermal enclosure")


class MasterCalculationResponse(BaseModel):
    """Master Output Schema returning calculated engineering results, warnings, and hard errors."""
    is_valid: bool
    load_summary: Dict[str, Any]
    battery_summary: Dict[str, Any]
    inverter_summary: Dict[str, Any]
    cabling_summary: Dict[str, Any]
    validation_summary: Dict[str, Any]
    warnings: List[str]
    hard_errors: List[str]


@router.post("/calculate", response_model=MasterCalculationResponse, status_code=status.HTTP_200_OK)
async def calculate_project_endpoint(payload: CalculationRequest) -> MasterCalculationResponse:
    """
    Executes the 5-stage engineering calculation pipeline sequentially.
    Guarantees deterministic output and aggregates module-level warnings and hard errors.
    """
    aggregated_warnings: List[str] = []
    aggregated_hard_errors: List[str] = []

    # -------------------------------------------------------------------------
    # STAGE 1: Load Characterization
    # -------------------------------------------------------------------------
    load_res = calculate_load_profile(loads=payload.loads)
    _aggregate_messages(load_res, aggregated_warnings, aggregated_hard_errors)

    if load_res.get("hard_errors"):
        return _build_error_response(load_res, {}, {}, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # -------------------------------------------------------------------------
    # STAGE 2: Battery Bank Sizing (IEEE 485 / IEEE 1013)
    # -------------------------------------------------------------------------
    battery_res = calculate_battery_bank(
        daily_energy_wh=load_res["daily_energy_wh"],
        peak_real_power_w=load_res["peak_real_power_w"],
        surge_apparent_power_va=load_res["surge_apparent_power_va"],
        params=payload.parameters,
        battery=payload.selected_battery
    )
    _aggregate_messages(battery_res, aggregated_warnings, aggregated_hard_errors)

    if battery_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, {}, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # -------------------------------------------------------------------------
    # STAGE 3: Inverter Sizing
    # -------------------------------------------------------------------------
    # Physical system DC voltage
    v_bank_actual = battery_res.get("n_series", 1) * payload.selected_battery.nominal_voltage

    inverter_res = calculate_inverter_sizing(
        peak_apparent_power_va=load_res["peak_apparent_power_va"],
        peak_real_power_w=load_res["peak_real_power_w"],
        surge_apparent_power_va=load_res["surge_apparent_power_va"],
        v_bank_actual=v_bank_actual,
        loads=payload.loads,
        inverter=payload.selected_inverter
    )
    _aggregate_messages(inverter_res, aggregated_warnings, aggregated_hard_errors)

    if inverter_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, inverter_res, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # -------------------------------------------------------------------------
    # STAGE 4: Cabling and Overcurrent Protection (NEC 210.19 / 215.2)
    # -------------------------------------------------------------------------
    cabling_res = calculate_cabling_and_protection(
        i_dc_continuous=inverter_res.get("i_dc_continuous", 0.0),
        v_bank_actual=v_bank_actual,
        cable_length_m=payload.cable_length_m,
        n_parallel_strings=battery_res.get("n_parallel", 1)
    )
    _aggregate_messages(cabling_res, aggregated_warnings, aggregated_hard_errors)

    if cabling_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, inverter_res, cabling_res, {}, aggregated_warnings, aggregated_hard_errors)

    # -------------------------------------------------------------------------
    # STAGE 5: Cross-Module System Validation
    # -------------------------------------------------------------------------
    validation_res = validate_system_design(
        load_result=load_res,
        battery_result=battery_res,
        inverter_result=inverter_res,
        cabling_result=cabling_res,
        system_design_voltage=payload.parameters.system_dc_voltage,
        inverter_input_voltage=payload.selected_inverter.nominal_dc_voltage,
        battery_module_voltage=payload.selected_battery.nominal_voltage,
        charge_current_a=payload.charge_current_a,
        charge_window_hours=payload.charge_window_hours,
        components_colocated=payload.components_colocated,
        battery_surge_limit_a=payload.selected_battery.max_continuous_discharge_amps * 2.0 if payload.selected_battery.max_continuous_discharge_amps else 0.0,
        inverter_surge_limit_a=(payload.selected_inverter.surge_va / v_bank_actual) if v_bank_actual > 0 else 0.0,
        cable_rating_a=cabling_res.get("i_design_a", 0.0),
        fuse_rating_a=cabling_res.get("i_fuse_a", 0.0),
        autonomy_days=payload.parameters.days_of_autonomy,
        inverter_efficiency=payload.parameters.target_inverter_efficiency
    )
    _aggregate_messages(validation_res, aggregated_warnings, aggregated_hard_errors)

    # Deduplicate final messages preserving order
    final_warnings = list(dict.fromkeys(aggregated_warnings))
    final_hard_errors = list(dict.fromkeys(aggregated_hard_errors))
    is_valid = len(final_hard_errors) == 0

    return MasterCalculationResponse(
        is_valid=is_valid,
        load_summary=load_res,
        battery_summary=battery_res,
        inverter_summary=inverter_res,
        cabling_summary=cabling_res,
        validation_summary=validation_res,
        warnings=final_warnings,
        hard_errors=final_hard_errors
    )


def _aggregate_messages(module_result: Dict[str, Any], warnings_list: List[str], hard_errors_list: List[str]) -> None:
    """Utility helper to pull warnings and hard_errors out of module responses."""
    if "warnings" in module_result:
        warnings_list.extend(module_result["warnings"])
    if "hard_errors" in module_result:
        hard_errors_list.extend(module_result["hard_errors"])


def _build_error_response(
    load_res: Dict[str, Any],
    battery_res: Dict[str, Any],
    inverter_res: Dict[str, Any],
    cabling_res: Dict[str, Any],
    validation_res: Dict[str, Any],
    warnings: List[str],
    hard_errors: List[str]
) -> MasterCalculationResponse:
    """Constructs a standard blocked response payload when hard validation errors occur."""
    return MasterCalculationResponse(
        is_valid=False,
        load_summary=load_res,
        battery_summary=battery_res,
        inverter_summary=inverter_res,
        cabling_summary=cabling_res,
        validation_summary=validation_res,
        warnings=list(dict.fromkeys(warnings)),
        hard_errors=list(dict.fromkeys(hard_errors))
    )