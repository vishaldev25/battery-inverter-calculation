# Battery Bank & Inverter Sizing — Backend Calculation Specification

Reference standards: **IEEE 485** (Recommended Practice for Sizing Vented Lead-Acid Batteries), **IEEE 1013** (Standalone PV System Battery Sizing), **IEC 62109** (Inverter Safety), **UL 1741 / IEEE 1547** (Grid-Interactive Inverters, Anti-Islanding), **NEC Articles 210, 215, 690, 705** (Continuous Load Factor, Conductor Ampacity, PV Systems, Interconnected Systems).

This document defines every input parameter, its data type/source, the exact formula, and the output schema needed to implement a deterministic (non-LLM) calculation engine.

---

## 1. System Architecture

```
[Load Input Module] → [Energy/Ah Demand Calc] → [Battery Sizing Engine] → [Battery Catalog Match]
                                                          ↓
                    [Inverter Sizing Engine (VA/Surge)] → [Inverter Catalog Match]
                                                          ↓
                    [Cable/Protection Sizing Engine] → [Wire Gauge & Fuse Output]
```

Each module below maps to one backend function. Keep the calculation engine **pure/deterministic** (no external calls); keep the catalog-matching layer separate and data-driven.

---

## 2. Module 1 — Load Characterization

### 2.1 Input schema (per load item)

| Field | Type | Notes |
|---|---|---|
| `name` | string | e.g. "Water pump" |
| `power_watts` | float | Nameplate rated power |
| `qty` | int | Number of identical units |
| `hours_per_day` | float | Usage duration |
| `load_category` | enum | `resistive`, `lighting_led`, `lighting_incandescent`, `motor_pump`, `motor_compressor`, `electronics_it`, `hvac`, `heating_resistive` |
| `simultaneity_factor` | float (0–1) | Fraction of time this load coincides with peak — default 1.0 if unknown |
| `is_critical` | bool | For critical-load-only backup sizing |

### 2.2 Power Factor lookup table (server-side constant, not user input)

| `load_category` | PF (typical) | Surge multiplier (× rated W, if motor-type) |
|---|---|---|
| `resistive` / `heating_resistive` | 1.00 | 1× (no surge) |
| `lighting_incandescent` | 0.95–1.00 | 1× |
| `lighting_led` | 0.50–0.90 (driver-dependent; use 0.70 default if unspecified) | 1.2× (brief driver inrush) |
| `motor_pump` | 0.75–0.85 (use 0.80 default) | 4× running W for 0.5–2 s |
| `motor_compressor` | 0.70–0.85 (use 0.75 default) | 5–6× running W (locked-rotor) |
| `electronics_it` | 0.65–0.95 (SMPS-dependent; use 0.85 default) | 1.5× |
| `hvac` | 0.75–0.85 | 4–5× (compressor-driven) |

> Sector presets (household / hospital / college / industrial) = a saved **mix of these categories** with typical proportions, not a separate PF number. Do not expose raw PF as a free-text field to the end user — derive it from category selection to keep results defensible.

### 2.3 Formulas

**Daily energy per load:**
$$E_i = P_i \times qty_i \times t_i \times SF_i \quad \text{[Wh/day]}$$

**Total daily energy:**
$$E_{day} = \sum_i E_i$$

**Total & critical-only peak simultaneous demand (for inverter continuous rating):**
$$P_{peak} = \sum_i (P_i \times qty_i \times SF_i)$$

**Apparent power (VA) of peak demand — this is what drives inverter sizing, not raw watts:**
$$S_{peak} = \sum_i \frac{P_i \times qty_i \times SF_i}{PF_i}$$

**Surge VA requirement (worst-case single motor start + everything else already running):**
$$S_{surge} = \max_k \left[ (P_k \times M_k) + \sum_{j \neq k} \frac{P_j \times qty_j \times SF_j}{PF_j} \right]$$
where $M_k$ is the surge multiplier of load $k$ (evaluate this across every motor-type load $k$ to find the worst case, not just the largest one).

---

## 3. Module 2 — Battery Bank Sizing (IEEE 485 / IEEE 1013 methodology)

### 3.1 Input schema

| Field | Type | Notes |
|---|---|---|
| `bank_voltage_nominal` | float | e.g. 12, 24, 48 V |
| `autonomy_days` | float | Reserve days |
| `wire_efficiency` | float (0–1) | 1 − connection/cable loss fraction; default 0.97 |
| `battery_chemistry` | enum | `flooded_lead_acid`, `agm`, `gel`, `lifepo4` |
| `dod_max` | float | From chemistry table below, or user override within safe range |
| `aging_factor` | float | Default 0.80 (bank sized to still meet load at 80% of nameplate, i.e., end-of-life) |
| `ambient_temp_c` | float | **Explicit °C only — never accept unlabeled numeric temperature** |
| `design_margin` | float | Default 0.10–0.15 |
| `battery_option.voltage` | float | Candidate battery unit voltage |
| `battery_option.ah_rating` | float | At specified discharge rate (see 3.3) |
| `battery_option.rated_discharge_hours` | float | e.g., 20 (the "C" in C/20) |
| `battery_option.max_continuous_discharge_a` | float | From datasheet |
| `battery_option.peukert_exponent` | float | Chemistry default if not in datasheet (see 3.3) |

### 3.2 Chemistry defaults table

| Chemistry | DOD max | Round-trip efficiency ($\eta_{batt}$) | Peukert exponent (typical) |
|---|---|---|---|
| Flooded lead-acid | 0.50 | 0.85 | 1.15–1.25 |
| AGM | 0.50–0.80 | 0.90 | 1.10–1.15 |
| Gel | 0.50–0.80 | 0.90 | 1.10–1.15 |
| LiFePO₄ | 0.80–0.95 | 0.97 | ~1.00–1.02 (negligible; often skip Peukert for lithium) |

### 3.3 Peukert's Law — capacity correction for real discharge rate

Nameplate Ah is only valid at the rated discharge hour-rate (commonly C/20). Actual usable Ah at your real discharge current is lower:

$$C_{actual} = C_{rated} \times \left(\frac{C_{rated}/T_{rated}}{I_{actual}}\right)^{k-1}$$

where $k$ = Peukert exponent, $T_{rated}$ = rated discharge hours (e.g. 20), $I_{actual}$ = your system's actual average discharge current. Apply this **before** the DOD/aging/temperature corrections below if $I_{actual}$ materially exceeds the C/20 rate (common in short-autonomy, high-power systems).

### 3.4 Temperature correction table ($k_t$), referenced to 25 °C (IEEE 485)

| Temp (°C) | $k_t$ (capacity correction, multiply required Ah) |
|---|---|
| 25 | 1.00 |
| 20 | 1.04 |
| 10 | 1.11 |
| 0 | 1.19 |
| −10 | 1.30 |
| −20 | 1.40 |

Linear-interpolate between table points. **Reject any ambient_temp_c input outside −20 °C to 50 °C** without explicit datasheet confirmation — this table (and most standard lead-acid ratings) doesn't extrapolate reliably beyond it. Above 30–35 °C, apply the separate **life-derating** warning (not a capacity correction, a longevity one — see 3.7).

### 3.5 Core sizing formulas

**Step 1 — Ah demand at bank voltage:**
$$Ah_{day} = \frac{E_{day}}{V_{bank}}$$

**Step 2 — Autonomy:**
$$Ah_{autonomy} = Ah_{day} \times N_{days}$$

**Step 3 — Full correction chain:**
$$Ah_{required} = Ah_{autonomy} \times \frac{k_t}{\eta_{batt} \times \eta_{wire} \times F_{aging} \times DOD_{max}} \times (1 + M)$$

**Step 4 — Peak/average discharge current (for C-rate check):**
$$I_{discharge,avg} = \frac{P_{peak}}{V_{bank} \times \eta_{inverter}}, \qquad I_{discharge,surge} = \frac{S_{surge}}{V_{bank} \times \eta_{inverter}}$$

### 3.6 String solver (series-parallel)

$$N_{series} = \frac{V_{bank}}{V_{battery}} \quad \text{(must be an integer — reject/flag non-integer results)}$$

$$N_{parallel} = \max \left( \left\lceil \frac{Ah_{required}}{Ah_{battery}} \right\rceil,\ \left\lceil \frac{I_{discharge,avg}}{I_{max,continuous} \times N_{series,irrelevant}} \right\rceil \right)$$

> Note: `max_continuous_discharge_a` is a per-battery rating; when batteries are in series the string's max current is the *same* as one battery's rating (current is common through a series string), so the parallel count for the current check is:
> $$N_{parallel,current} = \left\lceil \frac{I_{discharge,avg}}{I_{max,continuous}} \right\rceil$$
> Take $N_{parallel} = \max(N_{parallel,Ah},\ N_{parallel,current})$.

**Output:**
$$N_{total} = N_{series} \times N_{parallel}, \quad V_{bank,actual} = V_{battery} \times N_{series}, \quad Ah_{bank,actual} = Ah_{battery} \times N_{parallel}$$

**Self-check (mandatory — the failure mode of the original spreadsheet):**
```
IF Ah_bank_actual < Ah_required:
    REJECT config, recompute N_parallel += 1, repeat
```

### 3.7 Output flags (non-numeric, advisory)

- If `ambient_temp_c > 30`: emit warning — every ~8–10 °C above 25 °C roughly halves lead-acid cycle life (Arrhenius-type aging); recommend ventilation/cooling review.
- If `battery_chemistry == lifepo4`: emit mandatory flag — **BMS (Battery Management System) required**, not optional.
- If `battery_chemistry == flooded_lead_acid`: emit flag — ventilation sizing required (hydrogen off-gassing during charge) and periodic equalization charge required.

---

## 4. Module 3 — Inverter Sizing

### 4.1 Formulas

**Continuous rating (VA):**
$$S_{continuous} = S_{peak} \times (1 + F_{future})$$
(default $F_{future}$ = 0.20)

**Surge rating (VA):** use $S_{surge}$ from §2.3 directly (already worst-case).

**DC input current from inverter (for battery-side cable sizing):**
$$I_{DC,continuous} = \frac{S_{continuous} \times PF_{avg,system}}{V_{bank,actual} \times \eta_{inverter}}$$

Use manufacturer's efficiency **at the expected load percentage and at low-battery voltage cutoff**, not a flat nameplate number — pull $\eta_{inverter}$ from the datasheet's efficiency curve at $S_{continuous}/S_{rated,inverter}$ load fraction.

### 4.2 Input schema

| Field | Type | Notes |
|---|---|---|
| `inverter_option.continuous_va` | float | Datasheet |
| `inverter_option.surge_va` | float | Datasheet, with duration (e.g. "150% for 60s, 300% for 3s") |
| `inverter_option.waveform` | enum | `pure_sine`, `modified_sine` — reject modified_sine if any load_category is motor/electronics-sensitive |
| `inverter_option.input_voltage_window` | [min, max] | Must contain $V_{bank,actual}$ across full charge/discharge swing |
| `inverter_option.efficiency_curve` | array of (load%, η) | For accurate $I_{DC}$ calc |
| `inverter_option.certifications` | list | UL1741 / IEC62109 / IEEE1547 (grid-tie only) |

### 4.3 Selection rule

```
candidate valid IF:
    continuous_va >= S_continuous
    AND surge_va >= S_surge
    AND (waveform == pure_sine OR no motor/electronics loads present)
    AND V_bank_actual within input_voltage_window
```

---

## 5. Module 4 — Cable & Protection Sizing (NEC-based)

### 5.1 Ampacity check
$$I_{design} = I_{continuous} \times 1.25 \quad \text{(NEC 210.19 / 215.2 continuous-load factor)}$$
Look up minimum AWG/mm² from standard ampacity tables (insulation type + installation method: free air / conduit / bundled, each with its own derate).

### 5.2 Voltage-drop check
$$V_{drop} = \frac{2 \times L \times I \times R_{cable}}{1000} \quad [L \text{ in m},\ R \text{ in } \Omega/\text{km}]$$
Constraint: $V_{drop} \le 0.02\text{–}0.03 \times V_{bank,actual}$ (2–3%). **This is frequently the binding constraint on low-voltage (12/24V) DC runs, not ampacity** — always compute both and select the larger resulting gauge.

### 5.3 Overcurrent protection
$$I_{fuse} = 1.25 \times I_{continuous}$$
Breaking capacity must exceed the bank's calculated worst-case short-circuit current (from battery datasheet internal resistance, or use manufacturer's max short-circuit current rating directly if published — do not estimate this from Ah rating alone).

### 5.4 Output schema
```json
{
  "min_awg_or_mm2": ...,
  "binding_constraint": "ampacity" | "voltage_drop",
  "fuse_rating_a": ...,
  "required_breaking_capacity_a": ...
}
```

---

## 6. Master Output Schema (single API response)

```json
{
  "load_summary": { "E_day_wh": ..., "P_peak_w": ..., "S_peak_va": ..., "S_surge_va": ... },
  "battery": {
    "Ah_required": ..., "N_series": ..., "N_parallel": ..., "N_total_batteries": ...,
    "V_bank_actual": ..., "Ah_bank_actual": ...,
    "flags": ["ventilation_required", "bms_required", ...]
  },
  "inverter": {
    "S_continuous_required_va": ..., "S_surge_required_va": ...,
    "recommended_waveform": "pure_sine" | "modified_sine_acceptable"
  },
  "cabling": {
    "battery_to_inverter": { "min_awg_or_mm2": ..., "binding_constraint": ..., "fuse_rating_a": ... }
  },
  "warnings": [ "..." ]
}
```

---

## 7. Standards & Reference Cross-Index

| Topic | Standard/Reference |
|---|---|
| Vented lead-acid battery sizing methodology | IEEE 485-2020 |
| Standalone PV battery sizing | IEEE 1013-2007 (R2018) |
| Continuous load factor (125%) | NEC 210.19(A), 215.2(A) |
| PV system wiring, grounding, ground-fault protection | NEC Article 690 |
| Interconnected (grid-tie) systems | NEC Article 705 |
| Inverter safety/performance | IEC 62109-1/-2 |
| Grid-interactive inverter certification & anti-islanding | UL 1741, IEEE 1547 |
| Peukert's Law (capacity vs. discharge rate) | W. Peukert, 1897 (still the standard empirical model used across lead-acid datasheets) |
| Battery temperature/life relationship (Arrhenius-based aging) | Standard electrochemical aging literature; also reflected in most VRLA manufacturer technical manuals (e.g., life-halving per ~8–10°C rise above 25°C is a commonly cited manufacturer rule of thumb — verify against your specific chosen battery's datasheet, as the exact multiplier is chemistry/design-specific) |

**Implementation note:** every "default" value in this document (PF by category, DOD by chemistry, Peukert exponents, temperature correction table) should be stored as **editable, versioned config data** in your backend — not hardcoded constants — so you can update them against a specific manufacturer's datasheet when a user selects a real product, without touching calculation logic.