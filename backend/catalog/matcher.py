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

_WAVEFORM_SENSITIVE_CATEGORIES = {
    "motor_pump",
    "motor_compressor",
    "electronics_it",
    "hvac",
}

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
    """
    from backend.db.client import get_battery_catalog_collection

    collection = get_battery_catalog_collection()
    query = {"chemistry": chemistry} if chemistry else {}

    candidates: List[BatteryCatalog] = []
    async for doc in collection.find(query):
        voltage = doc.get("nominal_voltage")
        if not voltage or voltage <= 0:
            continue
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
    gates defined in sizing spec Part E2.

    NOTE on implementation shape: this performs a full collection scan
    (`find({})`) and applies every gate — continuous/surge VA, voltage
    window, waveform, grid-tie certification, and LVD coordination — as
    Python-side filtering, not as MongoDB query predicates. This is a
    deliberate/acceptable tradeoff for the current catalog size (small,
    manually curated per architecture.md Invariant 6); if the catalog
    grows large enough for this to matter, continuous_va/surge_va are the
    first candidates to push into the query filter.

    Voltage matching:
      - If the candidate declares a well-formed input_voltage_window
        ([min, max], min < max), v_bank_actual must fall within it.
      - If input_voltage_window is declared but malformed (wrong length —
        this should be rare now that models.py validates on write, but
        may still occur for pre-existing/legacy documents), the candidate
        is EXCLUDED rather than silently falling back to an exact
        nominal_dc_voltage match — a malformed window is a data integrity
        problem, not the same thing as "no window declared."
      - If input_voltage_window is None (not declared at all), fall back
        to an exact nominal_dc_voltage match.

    LVD coordination (hard gate, fails closed):
      - If battery_end_of_discharge_voltage is provided, a candidate is
        REJECTED unless it declares an lvd_threshold_v AND that threshold
        is >= the battery's end-of-discharge voltage. A missing/unknown
        lvd_threshold_v is treated as a failed gate, not a pass — an
        inverter with an undocumented LVD threshold cannot be verified
        safe to pair with the battery, per spec Part E2's hard-gate rule
        ("all must pass — hard gate, not scoring").
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
        if voltage_window is None:
            # No window declared — fall back to exact nominal match.
            if doc.get("nominal_dc_voltage") != v_bank_actual:
                continue
        elif len(voltage_window) == 2:
            v_min, v_max = voltage_window
            if not (v_min <= v_bank_actual <= v_max):
                continue
        else:
            # Window declared but malformed (not exactly 2 values) —
            # exclude rather than fall back; do not guess intent.
            logger.warning(
                "Inverter '%s' has a malformed input_voltage_window (%r) — excluded from candidates.",
                doc.get("_id"), voltage_window,
            )
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
            # Fail closed: a missing/unknown LVD threshold cannot be
            # verified as coordinated with the battery, so it does not
            # pass this hard gate — it is not treated the same as "ok".
            if lvd is None or lvd < battery_end_of_discharge_voltage:
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