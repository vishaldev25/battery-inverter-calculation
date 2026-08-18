"""
Backend API Router - Calculation Engine + Project CRUD Endpoints
Feature 08's stateless /calculate pipeline extracted into _execute_pipeline()
so Feature 12's stateful routes call the identical code path — zero
formula/sequencing duplication, per Invariant 1.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.projects.models import LoadItem, ProjectParameters, Project
from backend.catalog.models import BatteryCatalog, InverterCatalog

from backend.calculation.load import calculate_load_profile
from backend.calculation.battery import calculate_battery_bank
from backend.calculation.inverter import calculate_inverter_sizing
from backend.calculation.cabling import calculate_cabling_and_protection
from backend.calculation.validation import validate_system_design
from backend.calculation.constants import FUTURE_EXPANSION_FACTOR

from backend.projects import repository
from backend.catalog import matcher
from backend.projects import queries as project_queries

# --- FEATURE 15 imports — reusing Feature 13's csv module exactly as built ---
from backend.csv.parser import parse_csv_bytes, CsvStructureError
from backend.csv.validator import validate_rows
from backend.csv.template import generate_template_csv
from backend.csv.models import CsvValidationResult

# --- FEATURE 16 imports — reusing backend/report/ exactly as built ---
from backend.report.pdf_builder import build_report_pdf, build_report_filename

router = APIRouter(prefix="/api/projects", tags=["Calculation Engine"])


class CalculationRequest(BaseModel):
    loads: List[LoadItem] = Field(..., min_items=1)
    parameters: ProjectParameters
    selected_battery: BatteryCatalog
    selected_inverter: InverterCatalog
    cable_length_m: float = Field(default=5.0, ge=0.1)
    charge_current_a: float = Field(default=0.0, ge=0.0)
    charge_window_hours: float = Field(default=0.0, ge=0.0)
    components_colocated: bool = Field(default=False)


class MasterCalculationResponse(BaseModel):
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
    """Stateless calculation entrypoint (Feature 08) — unchanged behavior."""
    return _execute_pipeline(
        loads=payload.loads,
        parameters=payload.parameters,
        selected_battery=payload.selected_battery,
        selected_inverter=payload.selected_inverter,
        cable_length_m=payload.cable_length_m,
        charge_current_a=payload.charge_current_a,
        charge_window_hours=payload.charge_window_hours,
        components_colocated=payload.components_colocated,
    )


def _execute_pipeline(
    loads: List[LoadItem],
    parameters: ProjectParameters,
    selected_battery: BatteryCatalog,
    selected_inverter: InverterCatalog,
    cable_length_m: float,
    charge_current_a: float,
    charge_window_hours: float,
    components_colocated: bool,
) -> MasterCalculationResponse:
    aggregated_warnings: List[str] = []
    aggregated_hard_errors: List[str] = []

    # STAGE 1
    load_res = calculate_load_profile(loads=loads)
    _aggregate_messages(load_res, aggregated_warnings, aggregated_hard_errors)
    if load_res.get("hard_errors"):
        return _build_error_response(load_res, {}, {}, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # STAGE 2
    battery_res = calculate_battery_bank(
        daily_energy_wh=load_res["daily_energy_wh"],
        peak_real_power_w=load_res["peak_real_power_w"],
        surge_apparent_power_va=load_res["surge_apparent_power_va"],
        params=parameters,
        battery=selected_battery,
    )
    _aggregate_messages(battery_res, aggregated_warnings, aggregated_hard_errors)
    if battery_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, {}, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # STAGE 3
    v_bank_actual = battery_res.get("n_series", 1) * selected_battery.nominal_voltage

    inverter_res = calculate_inverter_sizing(
        peak_apparent_power_va=load_res["peak_apparent_power_va"],
        peak_real_power_w=load_res["peak_real_power_w"],
        surge_apparent_power_va=load_res["surge_apparent_power_va"],
        v_bank_actual=v_bank_actual,
        loads=loads,
        inverter=selected_inverter,
    )
    _aggregate_messages(inverter_res, aggregated_warnings, aggregated_hard_errors)
    if inverter_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, inverter_res, {}, {}, aggregated_warnings, aggregated_hard_errors)

    # STAGE 4
    cabling_res = calculate_cabling_and_protection(
        i_dc_continuous=inverter_res.get("i_dc_continuous", 0.0),
        v_bank_actual=v_bank_actual,
        cable_length_m=cable_length_m,
        n_parallel_strings=battery_res.get("n_parallel", 1),
    )
    _aggregate_messages(cabling_res, aggregated_warnings, aggregated_hard_errors)
    if cabling_res.get("hard_errors"):
        return _build_error_response(load_res, battery_res, inverter_res, cabling_res, {}, aggregated_warnings, aggregated_hard_errors)

    # STAGE 5
    validation_res = validate_system_design(
        load_result=load_res,
        battery_result=battery_res,
        inverter_result=inverter_res,
        cabling_result=cabling_res,
        system_design_voltage=parameters.system_dc_voltage,
        inverter_input_voltage=selected_inverter.nominal_dc_voltage,
        battery_module_voltage=selected_battery.nominal_voltage,
        charge_current_a=charge_current_a,
        charge_window_hours=charge_window_hours,
        components_colocated=components_colocated,
        battery_surge_limit_a=selected_battery.max_continuous_discharge_amps * 2.0 if selected_battery.max_continuous_discharge_amps else 0.0,
        inverter_surge_limit_a=(selected_inverter.surge_va / v_bank_actual) if v_bank_actual > 0 else 0.0,
        cable_rating_a=cabling_res.get("i_design_a", 0.0),
        fuse_rating_a=cabling_res.get("i_fuse_a", 0.0),
        inverter_efficiency=parameters.target_inverter_efficiency,
    )
    _aggregate_messages(validation_res, aggregated_warnings, aggregated_hard_errors)

    final_warnings = list(dict.fromkeys(aggregated_warnings))
    final_hard_errors = list(dict.fromkeys(aggregated_hard_errors))

    return MasterCalculationResponse(
        is_valid=len(final_hard_errors) == 0,
        load_summary=load_res,
        battery_summary=battery_res,
        inverter_summary=inverter_res,
        cabling_summary=cabling_res,
        validation_summary=validation_res,
        warnings=final_warnings,
        hard_errors=final_hard_errors,
    )


def _aggregate_messages(module_result: Dict[str, Any], warnings_list: List[str], hard_errors_list: List[str]) -> None:
    if "warnings" in module_result:
        warnings_list.extend(module_result["warnings"])
    if "hard_errors" in module_result:
        hard_errors_list.extend(module_result["hard_errors"])


def _build_error_response(load_res, battery_res, inverter_res, cabling_res, validation_res, warnings, hard_errors) -> MasterCalculationResponse:
    return MasterCalculationResponse(
        is_valid=False,
        load_summary=load_res,
        battery_summary=battery_res,
        inverter_summary=inverter_res,
        cabling_summary=cabling_res,
        validation_summary=validation_res,
        warnings=list(dict.fromkeys(warnings)),
        hard_errors=list(dict.fromkeys(hard_errors)),
    )


# ===========================================================================
# FEATURE 12 — Project CRUD
# ===========================================================================

class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    loads: List[LoadItem] = Field(default_factory=list)
    parameters: ProjectParameters = Field(default_factory=ProjectParameters)


class UpdateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    loads: List[LoadItem] = Field(default_factory=list)
    parameters: ProjectParameters = Field(default_factory=ProjectParameters)


class SetFavoriteRequest(BaseModel):
    is_favorite: bool


class SetStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(draft|active|completed|archived)$")


class DeleteProjectRequest(BaseModel):
    confirm_name: str = Field(..., min_length=1)


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(payload: CreateProjectRequest) -> Project:
    project = Project(name=payload.name, description=payload.description, loads=payload.loads, parameters=payload.parameters)
    return await repository.create_project(project)


# --- FEATURE 15: registered here, BEFORE GET /{project_id}, deliberately.
# FastAPI matches routes in registration order — a fixed-path route like
# "/csv-template" must be declared before any "/{project_id}" route in the
# same router, otherwise "/csv-template" is shadowed (project_id gets bound
# to the literal string "csv-template" and this route is never reached).
# This was the actual cause of the smoke test's Test 1a/1b/1c failures
# (404 from get_project_endpoint, not a template-generation bug).
@router.get("/csv-template")
async def download_csv_template_endpoint() -> Response:
    """
    Streams Feature 13's generate_template_csv() output as a downloadable
    file. Stateless — no project context needed. Bytes are returned exactly
    as generate_template_csv() produces them, no transformation.
    """
    csv_bytes = generate_template_csv()
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="load_upload_template.csv"'
        },
    )


@router.get("/{project_id}", response_model=Project)
async def get_project_endpoint(project_id: str) -> Project:
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=Project)
async def replace_project_endpoint(project_id: str, payload: UpdateProjectRequest) -> Project:
    updated = Project(name=payload.name, description=payload.description, loads=payload.loads, parameters=payload.parameters)
    result = await repository.replace_project(project_id, updated)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result


@router.patch("/{project_id}/favorite", response_model=Project)
async def set_favorite_endpoint(project_id: str, payload: SetFavoriteRequest) -> Project:
    result = await repository.set_favorite(project_id, payload.is_favorite)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result


@router.patch("/{project_id}/status", response_model=Project)
async def set_status_endpoint(project_id: str, payload: SetStatusRequest) -> Project:
    result = await repository.set_status(project_id, payload.status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_endpoint(project_id: str, payload: DeleteProjectRequest) -> None:
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    success = await repository.delete_project(project_id, payload.confirm_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delete rejected: confirm_name did not match the project's name.")


# ===========================================================================
# FEATURE 12 — Stateful Calculate (Validate / Recommend) + Commit
# ===========================================================================

class StatefulCalculateRequest(BaseModel):
    mode: str = Field(..., pattern="^(recommend|validate)$")
    chosen_battery_id: Optional[str] = None
    chosen_inverter_id: Optional[str] = None
    cable_length_m: float = Field(default=5.0, ge=0.1)
    charge_current_a: float = Field(default=0.0, ge=0.0)
    charge_window_hours: float = Field(default=0.0, ge=0.0)
    components_colocated: bool = Field(default=False)


class CandidatePairResult(BaseModel):
    battery_id: str
    inverter_id: str
    result: MasterCalculationResponse


class RecommendResponse(BaseModel):
    mode: str = "recommend"
    candidates: List[CandidatePairResult]


class CommitRequest(BaseModel):
    battery_id: str
    inverter_id: str
    cable_length_m: float = Field(..., ge=0.1)
    charge_current_a: float = Field(..., ge=0.0)
    charge_window_hours: float = Field(..., ge=0.0)
    components_colocated: bool = Field(...)


@router.post("/{project_id}/calculate")
async def stateful_calculate_endpoint(project_id: str, payload: StatefulCalculateRequest):
    """
    Validate mode -> single MasterCalculationResponse.
    Recommend mode -> RecommendResponse listing every (battery, inverter)
    pair that clears the full pipeline with zero hard_errors, sorted
    smallest-adequate-first (actual_ah_capacity, then inverter.continuous_va —
    both confirmed against the real battery.py/inverter.py output shapes).

    Neither mode writes to last_calculation_result — only /calculate/commit does.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not project.loads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no loads to calculate against.")

    if payload.mode == "validate":
        if not payload.chosen_battery_id or not payload.chosen_inverter_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chosen_battery_id and chosen_inverter_id are required in validate mode.")
        battery = await matcher.get_battery_by_id(payload.chosen_battery_id)
        if battery is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Battery '{payload.chosen_battery_id}' not found in catalog.")
        inverter = await matcher.get_inverter_by_id(payload.chosen_inverter_id)
        if inverter is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Inverter '{payload.chosen_inverter_id}' not found in catalog.")

        return _execute_pipeline(
            loads=project.loads,
            parameters=project.parameters,
            selected_battery=battery,
            selected_inverter=inverter,
            cable_length_m=payload.cable_length_m,
            charge_current_a=payload.charge_current_a,
            charge_window_hours=payload.charge_window_hours,
            components_colocated=payload.components_colocated,
        )

    # --- Recommend mode ---
    load_res = calculate_load_profile(loads=project.loads)
    if load_res.get("hard_errors"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
            "message": "Load characterization failed before any candidate could be evaluated.",
            "hard_errors": load_res["hard_errors"],
        })

    battery_candidates = await matcher.find_battery_candidates(
        bank_voltage_nominal=project.parameters.system_dc_voltage,
        chemistry=project.parameters.battery_chemistry.value,
    )

    s_continuous_required_va = load_res["peak_apparent_power_va"] * (1.0 + FUTURE_EXPANSION_FACTOR)
    active_categories = [load.category.value for load in project.loads]

    # KNOWN GAP (confirmed, not a guess — see cover note): validate_system_design
    # (Stage 5) does not implement an LVD coordination check, so
    # battery_end_of_discharge_voltage has nowhere to be enforced per-pair
    # even if it were passed here. Omitted rather than plumbed through to a
    # gate that doesn't exist. Flagged in progress-tracker.md as a
    # backend/calculation/validation.py gap, outside this unit's boundary.
    inverter_candidates = await matcher.find_inverter_candidates(
        s_continuous_required_va=s_continuous_required_va,
        s_surge_required_va=load_res["surge_apparent_power_va"],
        v_bank_actual=project.parameters.system_dc_voltage,
        active_load_categories=active_categories,
        grid_tie_required=False,  # No grid-tie field exists on ProjectParameters yet.
    )

    if not battery_candidates or not inverter_candidates:
        return RecommendResponse(candidates=[])

    scored_candidates: List[tuple] = []

    for battery in battery_candidates:
        for inverter in inverter_candidates:
            pair_result = _execute_pipeline(
                loads=project.loads,
                parameters=project.parameters,
                selected_battery=battery,
                selected_inverter=inverter,
                cable_length_m=payload.cable_length_m,
                charge_current_a=payload.charge_current_a,
                charge_window_hours=payload.charge_window_hours,
                components_colocated=payload.components_colocated,
            )
            if pair_result.hard_errors:
                continue

            # Sort key confirmed against real battery.py/inverter.py output:
            # actual_ah_capacity is battery.py's final post-string-solver
            # capacity; inverter.continuous_va is the InverterCatalog's own
            # rated value (inverter_res has no rated-capacity field — its
            # s_continuous_va is the *requirement*, identical across pairs).
            sort_key = (
                pair_result.battery_summary.get("actual_ah_capacity", float("inf")),
                inverter.continuous_va,
            )
            scored_candidates.append((
                sort_key,
                CandidatePairResult(battery_id=battery.id, inverter_id=inverter.id, result=pair_result),
            ))

    scored_candidates.sort(key=lambda pair: pair[0])
    return RecommendResponse(candidates=[item for _, item in scored_candidates])


@router.post("/{project_id}/calculate/commit", response_model=Project)
async def commit_calculation_endpoint(project_id: str, payload: CommitRequest) -> Project:
    """
    Commits a chosen (battery, inverter) pair — re-runs Stages 2-5 once and
    saves via repository.save_calculation_result. Refuses to save if the
    pair has any hard_errors.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    battery = await matcher.get_battery_by_id(payload.battery_id)
    if battery is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Battery '{payload.battery_id}' not found in catalog.")
    inverter = await matcher.get_inverter_by_id(payload.inverter_id)
    if inverter is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Inverter '{payload.inverter_id}' not found in catalog.")

    result = _execute_pipeline(
        loads=project.loads,
        parameters=project.parameters,
        selected_battery=battery,
        selected_inverter=inverter,
        cable_length_m=payload.cable_length_m,
        charge_current_a=payload.charge_current_a,
        charge_window_hours=payload.charge_window_hours,
        components_colocated=payload.components_colocated,
    )

    if result.hard_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={
            "message": "Cannot commit — the chosen pair produced hard_errors.",
            "hard_errors": result.hard_errors,
        })

    updated_project = await repository.save_calculation_result(project_id, result.model_dump())
    if updated_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return updated_project


# ===========================================================================
# FEATURE 14 — Dashboard Tab & Filter Queries
# ===========================================================================

class ProjectListResponse(BaseModel):
    items: List[Project]
    total_count: int
    limit: int
    offset: int


@router.get("", response_model=ProjectListResponse)
async def list_projects_endpoint(
    tab: str = Query(..., pattern="^(all|recent|favorites|edited)$"),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProjectListResponse:
    """
    Dashboard listing for one of four tabs (all/recent/favorites/edited).
    Date range filters against the tab's own primary timestamp (see
    queries.py's _DATE_FIELD_BY_TAB) — not a single hardcoded field.
    Search matches project name only (case-insensitive substring).
    Standard limit/offset pagination; total_count returned for page controls.
    """
    query_fn = project_queries.TAB_DISPATCH[tab]
    items, total_count = await query_fn(
        date_from=date_from, date_to=date_to, q=q, limit=limit, offset=offset
    )
    return ProjectListResponse(items=items, total_count=total_count, limit=limit, offset=offset)


@router.patch("/{project_id}/opened", response_model=Project)
async def mark_project_opened_endpoint(project_id: str) -> Project:
    """
    Sets last_opened_at on project view/open. Does NOT trigger
    version_history — viewing isn't editing, mirrors set_favorite's
    precedent from Feature 12.
    """
    result = await repository.mark_project_opened(project_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result


# ===========================================================================
# FEATURE 15 — CSV Upload Route Wiring
# Two thin routes only. No new parsing/validation/calculation logic here —
# both routes consume Feature 13's backend/csv/ functions exactly as built.
# Boundary: backend/projects/ only, per the finalized Feature 15 spec.
# ===========================================================================

# Defensive limits (not engineering constraints — pure request-size guards,
# per code-standards.md's "clear, specific error messages" rule).
_CSV_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_CSV_MAX_ROWS = 10_000

_CSV_TEMPLATE_URL = "/api/projects/csv-template"


class CsvUploadRejectedResponse(BaseModel):
    committed: bool = False
    template_url: str
    validation_result: CsvValidationResult


class CsvUploadCommittedResponse(BaseModel):
    committed: bool = True
    loads_added: int
    project: Project


# NOTE: GET /csv-template is registered earlier in this file, immediately
# before GET /{project_id} — see the route-ordering comment there. It is
# NOT duplicated here; only the upload route lives in this section.


@router.post("/{project_id}/loads/csv-upload")
async def upload_csv_loads_endpoint(project_id: str, file: UploadFile = File(...)):
    """
    Uploads a CSV of loads, validates every row against the real LoadItem
    model (via Feature 13's validate_rows), and:
      - invalid_count > 0  -> nothing saved; returns the full per-row
        validation report plus a template_url so the user can fix and
        re-upload (per spec §3 — strict all-or-nothing commit).
      - invalid_count == 0 -> valid rows are APPENDED to the project's
        existing loads list (per spec §4 — additive, matches
        project-overview.md's manual-entry + CSV-upload complementary flow)
        and saved via repository.replace_project.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # --- Light extension check (UX only, not a security boundary — parser.py's
    # structural checks below would already reject non-CSV content) ---
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"'{file.filename}' does not appear to be a .csv file. Please upload a CSV file.",
                "template_url": _CSV_TEMPLATE_URL,
            },
        )

    # --- Bounded chunked reading with cumulative size tracking ---
    # Reads uploaded bytes in chunks, enforcing _CSV_MAX_UPLOAD_BYTES limit
    # before parsing (defense-in-depth: ASGI server or reverse proxy should
    # also set a request-body limit, e.g., uvicorn --limit-max-requests or
    # nginx client_max_body_size).
    file_bytes = b""
    chunk_size = 64 * 1024  # 64 KB chunks
    cumulative_size = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        cumulative_size += len(chunk)
        if cumulative_size > _CSV_MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "message": (
                        f"Upload exceeds the maximum allowed size of "
                        f"{_CSV_MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                    ),
                    "template_url": _CSV_TEMPLATE_URL,
                },
            )
        file_bytes += chunk

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Uploaded file is empty.",
                "template_url": _CSV_TEMPLATE_URL,
            },
        )

    # --- Structural parsing (Feature 13's parser.py, used as-is) ---
    try:
        df = parse_csv_bytes(file_bytes)
    except CsvStructureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": exc.message if hasattr(exc, "message") else str(exc),
                "template_url": _CSV_TEMPLATE_URL,
            },
        )

    # --- Defensive row-count guard, before row-level validation ---
    if len(df) > _CSV_MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Upload contains {len(df)} rows, exceeding the maximum of {_CSV_MAX_ROWS}.",
                "template_url": _CSV_TEMPLATE_URL,
            },
        )

    # --- Row-level validation (Feature 13's validator.py, used as-is) ---
    validation_result: CsvValidationResult = validate_rows(df)

    if validation_result.invalid_count > 0:
        # Nothing saved — strict all-or-nothing per spec §3.
        return CsvUploadRejectedResponse(
            committed=False,
            template_url=_CSV_TEMPLATE_URL,
            validation_result=validation_result,
        )

    # --- All rows valid: atomically append to the project's loads array
    # using repository.append_loads_atomic (MongoDB $push + $each), which
    # updates updated_at and version_history in the same operation without
    # reading a full-project snapshot first. This prevents lost concurrent
    # updates to other fields (name, description, parameters). ---
    new_loads_dicts = [load.model_dump() for load in validation_result.valid_rows]
    result = await repository.append_loads_atomic(project_id, new_loads_dicts)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    return CsvUploadCommittedResponse(
        committed=True,
        loads_added=validation_result.valid_count,
        project=result,
    )


# ===========================================================================
# FEATURE 16 — PDF Report Generation
# Single thin route. No calculation logic here — reads project.
# last_calculation_result and hands it to backend/report/pdf_builder.py,
# which formats it. Never recalculates. Per finalized Feature 16 spec §2.
# ===========================================================================

@router.post("/{project_id}/report")
async def generate_report_endpoint(project_id: str) -> Response:
    """
    Generates and streams a PDF report built from the project's saved
    last_calculation_result. 404 if the project doesn't exist. 400 if the
    project has never had a successful calculation saved (nothing to
    report on yet). PDF bytes are streamed directly — never written to
    disk or the database, per architecture.md's Storage Model.
    """
    project = await repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.last_calculation_result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This project has no saved calculation result yet — run and save a calculation before exporting a report.",
        )

    pdf_bytes = build_report_pdf(project)
    filename = build_report_filename(project.name)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )