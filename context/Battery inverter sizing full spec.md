# Battery Bank & Inverter Sizing — Complete Engineering Specification
### Formulas, Constraints, Validation Rules, and Terminology for Backend Implementation

**Reference standards:** IEEE 485-2020 (Vented Lead-Acid Battery Sizing), IEEE 1013-2007 (Standalone PV Battery Sizing), IEEE 1188 (VRLA Battery Sizing), IEEE 1547 (Interconnection & Anti-Islanding), IEC 62109-1/-2 (Inverter Safety), UL 1741 (Grid-Interactive Inverter Certification), NEC Articles 110, 210, 215, 690, 705, 706 (Energy Storage Systems), IEC 60364 (Low-Voltage Electrical Installations).

---

## PART A — TERMINOLOGY (Glossary)

| Term | Definition |
|---|---|
| **Ah (Amp-hour)** | Unit of electric charge capacity; current × time a battery can deliver |
| **Wh (Watt-hour)** | Unit of energy; power × time |
| **DOD (Depth of Discharge)** | Fraction of rated capacity discharged, relative to full charge |
| **SOC (State of Charge)** | Remaining capacity as a fraction of full charge (SOC = 1 − DOD at any instant) |
| **C-rate** | Charge/discharge current expressed as a multiple of rated capacity (1C = full discharge in 1 hour; C/20 = full discharge in 20 hours) |
| **Peukert Exponent (k)** | Empirical constant describing capacity loss at higher discharge rates |
| **Autonomy / Reserve Days** | Days the battery bank must supply load without recharge |
| **Round-trip Efficiency** | Ratio of energy retrieved to energy put into a battery over one full cycle |
| **Cycle Life** | Number of charge/discharge cycles to a defined end-of-life capacity (usually 80% of nameplate) |
| **Float Voltage** | Voltage a battery is held at during standby/maintenance charging |
| **Equalization Charge** | Controlled periodic overcharge (flooded lead-acid) to reverse stratification/sulfation |
| **BMS (Battery Management System)** | Electronic system monitoring/protecting cells (voltage, temperature, balancing) — mandatory for lithium |
| **VA (Volt-Ampere)** | Apparent power = Voltage × Current, without power factor correction; inverters are rated in VA |
| **W (Watt)** | Real/active power = VA × PF |
| **PF (Power Factor)** | Ratio of real power to apparent power (W/VA); cos(φ) for linear loads |
| **THD (Total Harmonic Distortion)** | Measure of waveform distortion caused by non-linear loads or inverter output quality |
| **Surge/Inrush Current** | Momentary high current draw at motor/transformer start-up, typically 3–6× running current |
| **LVD (Low Voltage Disconnect)** | Threshold at which the inverter/controller disconnects the load to protect the battery from over-discharge |
| **Anti-Islanding** | Protection preventing a grid-tied inverter from energizing a de-energized utility line (safety for line workers) |
| **Ampacity** | Maximum current a conductor can carry continuously without exceeding its temperature rating |
| **Derating** | Reduction of a rated value to account for real-world conditions (temperature, altitude, bundling, aging) |
| **Simultaneity/Diversity Factor** | Fraction of connected load actually operating at the same time |
| **Nameplate Rating** | Manufacturer's stated rating under specific reference conditions — always check the reference conditions, not just the number |

---

## PART B — LOAD CHARACTERIZATION

### B1. Input parameters

| Parameter | Type | Constraint |
|---|---|---|
| `power_watts` | float | > 0; reject 0/negative |
| `qty` | int | ≥ 1 |
| `hours_per_day` | float | 0 ≤ x ≤ 24 |
| `load_category` | enum | must match predefined PF/surge table (Part C) |
| `simultaneity_factor` | float | 0 < x ≤ 1 |
| `voltage_rating` | float | must match declared system voltage (AC loads → system AC voltage; DC loads → bank voltage) — **reject mismatched voltage loads without an explicit converter stage declared** |

### B2. Formulas

$$E_i = P_i \times qty_i \times t_i \times SF_i \ \text{[Wh/day]}, \qquad E_{day} = \sum_i E_i$$
$$P_{peak} = \sum_i P_i \times qty_i \times SF_i, \qquad S_{peak} = \sum_i \frac{P_i \times qty_i \times SF_i}{PF_i}$$
$$S_{surge} = \max_k \left[ P_k \times M_k + \sum_{j \neq k} \frac{P_j \times qty_j \times SF_j}{PF_j} \right]$$

### B3. Validation rules
- `E_day` must be recomputed, never user-overridden directly (prevents inconsistent inputs).
- If `sum(simultaneity_factor × qty × power) == sum(power × qty)` (i.e., all factors = 1), emit an **advisory**, not an error: "No diversity applied — this is a conservative (larger) design; consider reviewing actual simultaneous usage."
- Reject any load with `hours_per_day > 24` or negative values outright (hard validation error).

---

## PART C — POWER FACTOR & SURGE TABLE (server-side constants)

| `load_category` | PF (default) | Surge multiplier | Notes/Constraint |
|---|---|---|---|
| `resistive` | 1.00 | 1.0× | — |
| `lighting_incandescent` | 0.97 | 1.0× | — |
| `lighting_led` | 0.70 | 1.2× | Flag: verify driver PF from datasheet if available — range is 0.5–0.9 |
| `motor_pump` | 0.80 | 4.0× | Surge duration 0.5–2 s |
| `motor_compressor` | 0.75 | 5.5× | Locked-rotor current; surge duration 0.1–1 s |
| `electronics_it` | 0.85 | 1.5× | SMPS-based; verify with datasheet where possible |
| `hvac` | 0.80 | 4.5× | Compressor-dominated |
| `heating_resistive` | 1.00 | 1.0× | — |

**Sector presets** (household/hospital/college/industrial) = pre-weighted mixes of the above categories, stored as data, not separate PF constants. Industrial installations with uncorrected motor loads should default toward the low end of PF ranges; flag for capacitor bank / power factor correction recommendation if blended system PF < 0.85 (many utilities penalize PF below this threshold — a real, tariff-relevant constraint, not just a technical one).

---

## PART D — BATTERY BANK SIZING (IEEE 485 / IEEE 1013 / IEEE 1188)

### D1. Chemistry constraint table

| Chemistry | DOD max (design) | DOD absolute max (never exceed) | η (round-trip) | Peukert k | Cycle life @ design DOD (typical) | Operating temp range |
|---|---|---|---|---|---|---|
| Flooded lead-acid | 0.50 | 0.80 | 0.85 | 1.15–1.25 | 1200–1500 cycles | −20°C to 45°C (derate >30°C) |
| AGM | 0.50–0.60 | 0.80 | 0.90 | 1.10–1.15 | 500–800 cycles | −20°C to 40°C |
| Gel | 0.50–0.60 | 0.80 | 0.90 | 1.10–1.15 | 500–800 cycles | −20°C to 40°C |
| LiFePO₄ | 0.80–0.90 | 1.00 (BMS-limited) | 0.97 | ~1.00–1.02 | 2000–5000+ cycles | −10°C to 45°C (charge restricted below 0°C) |

**Hard constraint:** never allow `dod_max` input to exceed the "absolute max" column — reject/clamp with a warning. Charging LiFePO₄ below 0°C materially damages cells (lithium plating) — if `ambient_temp_c < 0` and `chemistry == lifepo4`, emit a **hard warning**: charge current must be curtailed or a battery heater is required; this is a safety constraint, not just a performance one.

### D2. Core formulas

**Peukert correction (apply first if discharge rate departs materially from rated C-rate):**
$$C_{actual} = C_{rated} \left(\frac{C_{rated}/T_{rated}}{I_{actual}}\right)^{k-1}$$

**Ah demand:**
$$Ah_{day} = \frac{E_{day}}{V_{bank}}, \qquad Ah_{autonomy} = Ah_{day} \times N_{days}$$

**Temperature correction ($k_t$, IEEE 485 table, ref. 25°C):**

| °C | 25 | 20 | 15 | 10 | 5 | 0 | −10 | −20 |
|---|---|---|---|---|---|---|---|---|
| $k_t$ | 1.00 | 1.04 | 1.07 | 1.11 | 1.15 | 1.19 | 1.30 | 1.40 |

Linear interpolation between listed points. **Constraint: reject temperature inputs outside −20°C to 50°C** unless a chemistry-specific datasheet value is supplied.

**Full correction chain:**
$$Ah_{required} = Ah_{autonomy} \times \frac{k_t}{\eta_{batt} \times \eta_{wire} \times F_{aging} \times DOD_{max}} \times (1+M)$$

**Discharge current:**
$$I_{avg} = \frac{P_{peak}}{V_{bank}\times \eta_{inv}}, \qquad I_{surge} = \frac{S_{surge}}{V_{bank}\times \eta_{inv}}$$

### D3. String configuration solver

$$N_{series} = \frac{V_{bank}}{V_{battery}}$$
**Constraint:** must be a positive integer. If not → reject candidate battery, do not round.

$$N_{parallel} = \max\left(\left\lceil \frac{Ah_{required}}{Ah_{battery}}\right\rceil,\ \left\lceil \frac{I_{avg}}{I_{max,cont}}\right\rceil,\ \left\lceil \frac{I_{surge}}{I_{max,surge,battery}}\right\rceil \right)$$

**Constraint — string uniformity:** all batteries in the bank must share identical chemistry, voltage, Ah rating, and (ideally) manufacture batch/date within the same procurement lot. Reject mixed-spec configurations outright — this is a hard safety/reliability rule, not a soft preference.

**Constraint — maximum strings in parallel:** most manufacturers cap recommended parallel strings (commonly ≤ 3–4 for flooded/AGM without active balancing, higher for lithium with BMS current sharing) — pull this from `battery_option.max_recommended_parallel_strings` if provided; otherwise flag for manual verification above 4 strings due to current-sharing/circulating-current risk.

**Self-check (mandatory, iterative):**
```
WHILE Ah_bank_actual < Ah_required OR I_max_bank < I_surge:
    N_parallel += 1
    recompute Ah_bank_actual, I_max_bank
```

### D4. Output flags / mandatory advisories

- `chemistry == lifepo4` → BMS mandatory (hard constraint, not advisory).
- `chemistry == flooded_lead_acid` → ventilation sizing mandatory per hydrogen gas generation rate: $V_{gas} \propto I_{charge}$ (consult manufacturer gassing-current spec); confined/unventilated spaces are a code violation, not just inefficient.
- `ambient_temp_c > 30` → cycle-life derating warning (roughly halves per 8–10°C rise above 25°C — verify against specific datasheet).
- `N_parallel > manufacturer max` → current-sharing risk warning.
- Any battery age/SOH input for an *existing* bank being expanded → capacity must be based on measured/estimated current capacity, not nameplate.

---

## PART E — INVERTER SIZING

### E1. Formulas

$$S_{continuous} = S_{peak} \times (1+F_{future}), \qquad F_{future,default}=0.20$$
$$S_{surge} = \text{(from Part B3, worst-case single motor start + concurrent load)}$$
$$I_{DC,cont} = \frac{S_{continuous}\times PF_{avg}}{V_{bank,actual}\times \eta_{inv}(load\%)}$$

### E2. Selection constraints (all must pass — hard gate, not scoring)

| Check | Rule |
|---|---|
| Continuous capacity | `inverter.continuous_va ≥ S_continuous` |
| Surge capacity | `inverter.surge_va ≥ S_surge` **and** surge duration capability ≥ actual motor start duration |
| Input voltage window | `V_bank_actual` (across full charge–discharge swing, not just nominal) falls within `inverter.input_voltage_window` |
| Waveform | `waveform == pure_sine` **required** if any load_category ∈ {motor_pump, motor_compressor, electronics_it, hvac}; modified sine only acceptable for pure resistive loads |
| LVD coordination | `inverter.LVD_threshold` must be ≥ battery's `end_of_discharge_voltage` (per cell × series count) — reject inverter configs where LVD would over-discharge the battery |
| Efficiency point | Use `η` from datasheet curve at `S_continuous / inverter.rated_va` load fraction, not flat nameplate value |
| Certification (grid-tie only) | `UL1741` and `IEEE1547` compliance mandatory if `grid_tie == true` (anti-islanding is a legal/safety requirement, not optional) |
| Ambient temperature derating | If `ambient_temp_c > inverter.rated_temp_max`, apply manufacturer's thermal derating curve to `continuous_va` before comparing against `S_continuous` |
| Altitude derating | Above ~1000 m, apply manufacturer altitude derating (reduced convective cooling) |

### E3. Standby/parasitic load
$$E_{standby,day} = P_{standby} \times 24$$
Add to `E_day` for autonomy calculations in systems that run 24/7 off battery — commonly overlooked and can be a meaningful fraction of small systems' total draw.

---

## PART F — CABLE & PROTECTION SIZING (NEC / IEC 60364)

### F1. Constraints

$$I_{design} = 1.25 \times I_{continuous} \quad \text{(NEC 210.19/215.2 continuous-load factor — hard rule, not optional margin)}$$

**Ampacity table lookup** — depends on:
- Conductor material (copper vs. aluminum — different ampacity tables)
- Insulation temperature rating (60°C/75°C/90°C)
- Installation method (free air / conduit / raceway / bundled) — bundling beyond 3 current-carrying conductors requires derating per NEC Table 310.15(C)(1)
- Ambient temperature at install location (further derating above 30°C ambient)

**Voltage drop constraint:**
$$V_{drop} = \frac{2LI R_{cable}}{1000} \le 0.02\text{–}0.03 \times V_{system}$$
Take the **larger conductor size** from ampacity vs. voltage-drop checks — do not average or split the difference.

**Overcurrent protection:**
$$I_{fuse} = 1.25 \times I_{continuous}$$
Breaking capacity ≥ battery bank's maximum available short-circuit current (from datasheet; lead-acid banks can source very high fault current for brief durations — this is a distinct rating from continuous discharge current and must be checked separately).

**Constraint — string-level fusing:** each parallel string must carry its own overcurrent device at the point it joins the common bus (prevents one faulted string from being back-fed by the rest of the bank).

**Constraint — disconnect requirement:** an accessible, rated disconnect switch is required between battery bank and inverter (NEC 690.13/706 for ESS) — not a sizing calculation, but a mandatory system element to flag in output.

### F2. Grounding/bonding
System and equipment grounding per NEC 690.41/690.45 (or local equivalent, e.g. IEC 60364-4-41) — flag as a required design element; not a numeric output, but should appear in the compliance checklist (Part H).

---

## PART G — CROSS-MODULE VALIDATION RULES (system-level constraints)

These catch design errors that no single module would catch alone:

1. **Voltage consistency:** `V_bank_actual` (Part D output) must equal the declared `bank_voltage_nominal` input to Part B/E, or the whole calculation chain is invalid — re-run downstream modules if the string solver settles on a different achievable voltage.
2. **Current path check:** `I_surge` (Part D) must not exceed the smaller of: battery bank surge current capability, inverter DC input surge rating, and cable/fuse surge withstand — the weakest link determines system surge capability, not any single component's rating.
3. **Recharge feasibility:** if a charge source (solar array, generator, grid charger) is specified, verify:
$$T_{recharge} = \frac{Ah_{discharged} \times 1.1}{I_{charge,available}} \le T_{available (daylight/generator run window)}$$
   If this fails, autonomy days will not actually be replenished in the assumed cycle — flag as a design-breaking warning, not just an advisory.
4. **Thermal co-location check:** if battery and inverter share an enclosure, combined heat dissipation must be checked against enclosure ventilation — a passing individual thermal derating for each component doesn't guarantee a passing combined installation.
5. **Standby load inclusion:** confirm `E_standby,day` (Part E3) has been folded into `E_day` before the battery sizing chain runs — a common integration bug is sizing the battery off load-only energy and separately computing inverter standby draw without feeding it back.

---

## PART H — COMPLIANCE CHECKLIST (non-numeric, output as a checklist alongside results)

- [ ] Continuous load factor (125%) applied to all conductor/OCPD sizing (NEC 210.19/215.2)
- [ ] Ground-fault protection present for PV-sourced systems (NEC 690.5)
- [ ] Anti-islanding / IEEE 1547 compliance confirmed for any grid-tied inverter
- [ ] Accessible battery disconnect installed (NEC 690.13/706)
- [ ] System and equipment grounding per NEC 690.41/690.45 or local equivalent
- [ ] BMS present and functioning for any lithium chemistry
- [ ] Ventilation adequate for flooded lead-acid hydrogen off-gassing
- [ ] String-level overcurrent protection present for parallel battery strings
- [ ] Inverter certification (UL 1741/IEC 62109) matches installation type (grid-tie vs. standalone)
- [ ] All batteries in bank verified identical spec and same procurement lot
- [ ] Waveform (pure sine) confirmed adequate for all connected load types

---

## PART I — MASTER OUTPUT SCHEMA

```json
{
  "load_summary": {
    "E_day_wh": 0, "P_peak_w": 0, "S_peak_va": 0, "S_surge_va": 0,
    "blended_power_factor": 0
  },
  "battery": {
    "Ah_required": 0, "N_series": 0, "N_parallel": 0, "N_total_batteries": 0,
    "V_bank_actual": 0, "Ah_bank_actual": 0,
    "I_max_bank_continuous": 0, "I_max_bank_surge": 0,
    "flags": [],
    "chemistry_constraints_applied": {}
  },
  "inverter": {
    "S_continuous_required_va": 0, "S_surge_required_va": 0,
    "waveform_required": "pure_sine",
    "candidates_passing_hard_gates": []
  },
  "cabling": {
    "battery_to_inverter": {
      "min_awg_or_mm2": 0, "binding_constraint": "ampacity|voltage_drop",
      "fuse_rating_a": 0, "required_breaking_capacity_a": 0
    }
  },
  "recharge_feasibility": { "T_recharge_hr": 0, "T_available_hr": 0, "feasible": true },
  "compliance_checklist": {},
  "warnings": [],
  "hard_errors": []
}
```

**Distinction between `warnings` and `hard_errors`:** warnings are advisory (e.g., "PF below 0.85, consider correction"); hard_errors block a valid result from being returned at all (e.g., non-integer series count, LiFePO₄ below 0°C without heater, mixed battery specs, inverter surge rating below required surge). Your backend should refuse to output a "final" recommendation while any `hard_errors` entry exists — this is the mechanism that keeps the app from silently returning an unsafe or non-compliant design.

---

## PART J — STANDARDS CROSS-INDEX

| Topic | Reference |
|---|---|
| Vented lead-acid battery sizing | IEEE 485-2020 |
| Standalone PV battery sizing | IEEE 1013-2007 (R2018) |
| VRLA (sealed lead-acid) sizing | IEEE 1188 |
| Interconnection, anti-islanding | IEEE 1547 |
| Inverter safety | IEC 62109-1/-2 |
| Grid-interactive inverter certification | UL 1741 |
| Continuous load factor, conductor sizing | NEC 210.19, 215.2, Table 310.15 |
| PV system wiring/grounding/ground-fault | NEC Article 690 |
| Interconnected systems | NEC Article 705 |
| Energy storage systems | NEC Article 706 |
| Low-voltage installations (international equivalent) | IEC 60364 |
| Peukert's Law | W. Peukert, 1897 — universally used empirical model in lead-acid datasheets |

**Implementation reminder:** all numeric defaults in this document (PF, DOD, Peukert k, temperature table, surge multipliers) are **typical industry values** meant as safe starting defaults — store them as versioned, editable configuration, and override with manufacturer datasheet values whenever a specific real product is selected in the catalog-matching layer.