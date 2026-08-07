"""
Pydantic Data Models for MongoDB Catalog Collections
Collections: equipment_catalog, battery_catalog, inverter_catalog
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.calculation.constants import LoadCategory, BatteryChemistry


class EquipmentCatalog(BaseModel):
    """Catalog model for standard household/commercial load defaults."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: Optional[str] = Field(default=None, alias="_id", description="MongoDB Document ID")
    name: str = Field(..., description="Name/description of the appliance or equipment")
    category: LoadCategory = Field(..., description="Engineering load classification")
    default_watts: float = Field(..., gt=0, description="Default nominal power in Watts")
    default_pf: float = Field(default=1.0, gt=0, le=1.0, description="Default power factor (0.0 to 1.0]")
    default_surge_multiplier: float = Field(
        default=1.0, ge=1.0, description="Standard starting/inrush current surge multiplier"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BatteryCatalog(BaseModel):
    """Catalog model for specific battery products and manufacturer specs."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: Optional[str] = Field(default=None, alias="_id", description="MongoDB Document ID")
    make: str = Field(..., description="Manufacturer / Brand name")
    model: str = Field(..., description="Battery model number/name")
    chemistry: BatteryChemistry = Field(..., description="Battery chemical composition")
    nominal_voltage: float = Field(..., gt=0, description="Nominal module voltage in Volts DC")
    capacity_ah: float = Field(..., gt=0, description="Rated capacity in Ampere-hours (C20 rate)")
    max_dod_recommended: float = Field(
        default=0.50, gt=0, le=1.0, description="Recommended maximum depth of discharge"
    )
    round_trip_efficiency: float = Field(
        default=0.85, gt=0, le=1.0, description="Coulombic or energy round-trip efficiency"
    )
    peukert_exponent: float = Field(
        default=1.12, ge=1.0, le=1.5, description="Peukert coefficient for capacity derating"
    )
    max_continuous_discharge_amps: Optional[float] = Field(
        default=None, gt=0, description="Maximum continuous current limit in Amps"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InverterCatalog(BaseModel):
    """Catalog model for specific inverter products and manufacturer specs."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: Optional[str] = Field(default=None, alias="_id", description="MongoDB Document ID")
    make: str = Field(..., description="Manufacturer / Brand name")
    model: str = Field(..., description="Inverter model number/name")
    nominal_dc_voltage: float = Field(..., gt=0, description="Required input DC system voltage")
    continuous_va: float = Field(..., gt=0, description="Continuous apparent power rating in VA")
    surge_va: float = Field(..., gt=0, description="Peak surge apparent power rating in VA")
    surge_duration_seconds: float = Field(default=5.0, gt=0, description="Surge rating duration limit in seconds")
    peak_efficiency: float = Field(
        default=0.93, gt=0, le=1.0, description="Peak conversion efficiency (0.0 to 1.0]"
    )
    waveform: str = Field(default="Pure Sine Wave", description="Output waveform type")

    # --- Added (Feature 11 follow-up): grid-tie / voltage-window support ---
    # Per Battery_inverter_sizing_full_spec.md Part E2, full inverter selection
    # gating requires a voltage *window* (not just a single nominal voltage),
    # LVD coordination against the battery's end-of-discharge voltage, and
    # certification checks for grid-tie/anti-islanding compliance (a legal
    # safety requirement, not optional, per the spec). All fields below are
    # optional/default-safe so existing documents and code continue to work
    # unchanged; matcher.py falls back to exact nominal_dc_voltage matching
    # when input_voltage_window is not set.
    input_voltage_window: Optional[List[float]] = Field(
        default=None,
        description=(
            "Optional [min, max] DC input voltage window across the full "
            "charge/discharge swing. If unset, nominal_dc_voltage is treated "
            "as an exact-match requirement instead."
        ),
    )
    lvd_threshold_v: Optional[float] = Field(
        default=None,
        description=(
            "Low-voltage-disconnect threshold. Used for LVD coordination "
            "against the battery's end-of-discharge voltage."
        ),
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="Certifications held (e.g. 'IEC62109', 'UL1741', 'IEEE1547'). Empty if none/unknown.",
    )
    grid_tie_capable: bool = Field(
        default=False,
        description="Whether this inverter is rated for grid-interactive/grid-tie operation.",
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)