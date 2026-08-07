"""
Catalog Matching Logic
Fetches battery/inverter candidates for Recommend mode, or a specific
entry for Validate mode. Per architecture.md, this module MATCHES against
a requirement already computed by backend/calculation/ — it never performs
sizing math itself, and never duplicates a formula owned by another module.
"""

import logging
from typing import List, Optional

from backend.catalog.models import BatteryCatalog, InverterCatalog

logger = logging.getLogger("backend.catalog.matcher")

# Load categories that require pure sine per sizing spec Part E2 waveform gate.
_WAVEFORM_SENSITIVE_CATEGORIES = {
    "motor_pump",
    "motor_compressor",
    "electronics_it",
    "hvac",
}

# InverterCatalog.waveform is a free string (default "Pure Sine Wave"), not
# an enum — normalize case/spacing so filtering isn't brittle.
_PURE_SINE_MARKERS = {"pure sine wave", "pure_sine", "pure sine"}


def _is_pure_sine(waveform_value: str) -> bool:
    return waveform_value.strip().lower() in _PURE_SINE_MARKERS


# ---------------------------------------------------------------------------
# BATTERY MATCHING
# ---------------------------------------------------------------------------

async def find_battery_candidates(
    bank_voltage_nominal: float,
    chemistry: Optional[str] = None,
) -> List[BatteryCatalog]:
    """
    Recommend mode: returns battery catalog entries whose nominal_voltage
    evenly divides the target bank voltage (a valid series-string
    candidate), optionally filtered by chemistry.

    NOTE: only pre-filters plausible candidates. Does NOT compute
    N_series/N_parallel or run the string self-check — that stays in
    backend/calculation/battery.py per Architecture Invariant 1.
    """
    from backend.db.client import get_battery_catalog_collection

    collection = get_battery_catalog_collection()
    query = {"chemistry": chemistry} if chemistry else {}

    candidates: List[BatteryCatalog] = []
    async for doc in collection.find(query):
        voltage = doc.get("nominal_voltage")
        if not voltage or voltage <= 0:
            continue
        # Same hard rule as sizing spec Part D3 (N_series must be integer),
        # applied here purely as a pre-filter.
        if bank_voltage_nominal % voltage == 0:
            candidates.append(BatteryCatalog(**doc))

    logger.info(
        "Battery candidate search: bank_voltage=%s chemistry=%s -> %d candidates",
        bank_voltage_nominal, chemistry, len(candidates),
    )
    return candidates


async def get_battery_by_id(battery_id: str) -> Optional[BatteryCatalog]:
    """Validate mode: fetch a single battery catalog entry by its _id."""
    from backend.db.client import get_battery_catalog_collection

    doc = await get_battery_catalog_collection().find_one({"_id": battery_id})
    if doc is None:
        logger.info("Battery lookup: '%s' not found in catalog.", battery_id)
        return None
    return BatteryCatalog(**doc)


# ---------------------------------------------------------------------------
# INVERTER MATCHING
# ---------------------------------------------------------------------------

async def find_inverter_candidates(
    s_continuous_required_va: float,
    s_surge_required_va: float,
    v_bank_actual: float,
    active_load_categories: List[str],
    grid_tie_required: bool = False,
    battery_end_of_discharge_voltage: Optional[float] = None,
) -> List[InverterCatalog]:
    """
    Recommend mode: returns inverter catalog entries that pass the hard
    gates defined in sizing spec Part E2:
      - continuous_va >= required
      - surge_va >= required
      - v_bank_actual falls within input_voltage_window, if the candidate
        declares one; falls back to an exact nominal_dc_voltage match for
        older/simpler catalog entries that don't declare a window
      - waveform is pure sine if any waveform-sensitive load is present
      - if grid_tie_required: grid_tie_capable is True AND both UL1741 and
        IEEE1547 are present in certifications
      - if battery_end_of_discharge_voltage is provided and the candidate
        declares lvd_threshold_v: lvd_threshold_v must be >= that voltage,
        so the inverter won't over-discharge the battery before disconnect

    This is a filter over existing catalog data, not a re-implementation
    of the selection formulas — backend/calculation/inverter.py still
    makes the authoritative pass/fail call per candidate.
    """
    from backend.db.client import get_inverter_catalog_collection

    requires_pure_sine = bool(set(active_load_categories) & _WAVEFORM_SENSITIVE_CATEGORIES)

    candidates: List[InverterCatalog] = []
    async for doc in get_inverter_catalog_collection().find({}):
        if doc.get("continuous_va", 0) < s_continuous_required_va:
            continue
        if doc.get("surge_va", 0) < s_surge_required_va:
            continue

        voltage_window = doc.get("input_voltage_window")
        if voltage_window and len(voltage_window) == 2:
            v_min, v_max = voltage_window
            if not (v_min <= v_bank_actual <= v_max):
                continue
        else:
            # No window declared — fall back to exact nominal match.
            if doc.get("nominal_dc_voltage") != v_bank_actual:
                continue

        if requires_pure_sine and not _is_pure_sine(doc.get("waveform", "")):
            continue

        if grid_tie_required:
            if not doc.get("grid_tie_capable"):
                continue
            certs = set(doc.get("certifications") or [])
            if not {"UL1741", "IEEE1547"}.issubset(certs):
                continue

        if battery_end_of_discharge_voltage is not None:
            lvd = doc.get("lvd_threshold_v")
            if lvd is not None and lvd < battery_end_of_discharge_voltage:
                continue

        candidates.append(InverterCatalog(**doc))

    logger.info(
        "Inverter candidate search: S_cont=%s S_surge=%s V_bank=%s grid_tie_required=%s -> %d candidates",
        s_continuous_required_va, s_surge_required_va, v_bank_actual, grid_tie_required, len(candidates),
    )
    return candidates


async def get_inverter_by_id(inverter_id: str) -> Optional[InverterCatalog]:
    """Validate mode: fetch a single inverter catalog entry by its _id."""
    from backend.db.client import get_inverter_catalog_collection

    doc = await get_inverter_catalog_collection().find_one({"_id": inverter_id})
    if doc is None:
        logger.info("Inverter lookup: '%s' not found in catalog.", inverter_id)
        return None
    return InverterCatalog(**doc)