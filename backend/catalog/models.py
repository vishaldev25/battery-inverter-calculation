"""
Pydantic Data Models for MongoDB Catalog Collections
Collections: equipment_catalog, battery_catalog, inverter_catalog
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.calculation.constants import LoadCategory, BatteryChemistry


class EquipmentCatalog(BaseModel):
    """Catalog model for standard household/commercial load defaults."""

    model_config = ConfigDict(populate_by_name=True)

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

    model_config = ConfigDict(populate_by_name=True)

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

    model_config = ConfigDict(populate_by_name=True)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)