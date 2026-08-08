"""
Pydantic Data Models for Project Sizing Calculations & MongoDB Storage
Collection: projects
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.calculation.constants import LoadCategory, BatteryChemistry

def _utc_now() -> datetime:
    """Timezone-aware UTC 'now', replacing the deprecated datetime.utcnow().
    Storage stays UTC per architecture.md's region-aware design
    (project-overview.md scopes non-India regions as in-scope, not
    hypothetical) — IST/local display conversion belongs in frontend/,
    not here.
    """
    return datetime.now(timezone.utc)

class LoadItem(BaseModel):
    """Represents a single electrical load entry within a project sizing calculation."""

    id: Optional[str] = Field(default=None, description="Unique client-side item identifier")
    name: str = Field(..., description="Name or description of the load item")
    category: LoadCategory = Field(default=LoadCategory.RESISTIVE, description="Equipment category")
    quantity: int = Field(default=1, ge=1, description="Number of identical units")
    nominal_watts: float = Field(..., gt=0, description="Nominal power rating per unit in Watts")
    power_factor: Optional[float] = Field(
    default=None,
    gt=0,
    le=1.0,
    description=(
        "Explicit power factor override (0.0–1.0]. Leave unset (null) to use "
        "the category-based default from LOAD_CHARACTERISTICS (Part C of the "
        "sizing spec / Architecture Invariant 3) — power factor is never a "
        "free-text guess, only an explicit override or a validated default."
        ),
    )
    power_factor: Optional[float] = Field(default=None, gt=0, le=1.0, description="Power factor (0.0 to 1.0]. If unset, resolved from category defaults in LOAD_CHARACTERISTICS during calculation.")
    daily_hours: float = Field(default=1.0, ge=0.0, le=24.0, description="Average operating hours per day")
    surge_multiplier: float = Field(default=1.0, ge=1.0, description="Inrush/surge starting factor")
    is_concurrent: bool = Field(default=True, description="Whether this load contributes to peak concurrent demand")


class ProjectParameters(BaseModel):
    """Engineering constraints and site parameters for a sizing project."""

    system_dc_voltage: float = Field(default=48.0, gt=0, description="Target DC bus voltage (12V, 24V, 48V, etc.)")
    days_of_autonomy: float = Field(default=1.0, ge=0.1, description="Required days of backup power without recharge")
    ambient_temp_c: float = Field(default=25.0, description="Design ambient operating temperature in Celsius")
    battery_chemistry: BatteryChemistry = Field(default=BatteryChemistry.LIFEPO4, description="Target battery technology")
    max_dod_override: Optional[float] = Field(default=None, gt=0, le=1.0, description="Optional custom DOD limit override")
    target_inverter_efficiency: float = Field(default=0.90, gt=0, le=1.0, description="Estimated continuous inverter efficiency")
    wire_efficiency: float = Field(default=0.97, gt=0, le=1.0, description="Estimated DC/AC wiring efficiency")
    aging_factor: float = Field(default=0.80, gt=0, le=1.0, description="Battery end-of-life capacity factor (IEEE 485)")


class VersionHistoryEntry(BaseModel):
    """
    A single entry in a project's version_history array.
    Shape matches calculation-engine-and-data-model.md Part 2.1 exactly.
    `snapshot_ref` stays None — full-snapshot vs. diff-based history is an
    explicit open question deferred past this unit, not a guess.
    """
    edited_at: datetime = Field(default_factory=_utc_now)
    summary: str = Field(..., description="Human-readable summary of what changed")
    snapshot_ref: Optional[str] = Field(default=None)


class Project(BaseModel):
    """Root model for a user's battery & inverter sizing project."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id", description="MongoDB Document ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(default=None, description="Optional project description or location notes")
    status: str = Field(default="draft", description="Project state: 'draft', 'active', 'completed', 'archived'")

    # --- Added in Feature 12 ---
    # Required by architecture.md's Storage Model / ui-context.md's dashboard
    # card spec (Favorite toggle, "Edited" tab) but absent from the model as
    # it stood after Feature 02. Extended here rather than guessed around,
    # same pattern as the InverterCatalog extension in Feature 11.
    is_favorite: bool = Field(
        default=False,
        description="Dashboard favorite/star flag — does NOT trigger version history (see repository.py).",
    )
    version_history: List[VersionHistoryEntry] = Field(
        default_factory=list, description="Append-only audit log of substantive edits, per Invariant 9."
    )
    last_opened_at: Optional[datetime] = Field(
        default=None,
        description="Set on project view/open — NOT wired to an endpoint in this unit (no view/open route exists yet); reserved for Feature 14's 'Recent' sort.",
    )
    # --- end Feature 12 additions ---

    loads: List[LoadItem] = Field(default_factory=list, description="List of connected load items")
    parameters: ProjectParameters = Field(default_factory=ProjectParameters, description="System design parameters")
    last_calculation_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Cached output of the calculation engine"
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)