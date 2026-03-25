# Validated BOM v3 — Research-Backed Hardware Specification

> **Date**: 2026-03-16
> **Method**: Cross-referenced against ArduPilot docs, datasheets, competitor teardowns,
> research papers, and manufacturer specifications. Every change from v2 is justified below.

> If you are actively buying parts, start with [approved_sku_sheet.md](approved_sku_sheet.md)
> and [buying_guide.md](buying_guide.md).
> This file is the engineering rationale and validated baseline. The buying guide is the short
> answer for what to purchase now.

> This BOM is research-backed against datasheets, ArduPilot constraints, and competitor benchmarks.
> It is not a claim that the full robot has already been field-validated end-to-end.

> For a production-focused audit of which parts are merely cost-efficient versus genuinely
> best-in-class, see [parts_audit_best_possible.md](parts_audit_best_possible.md).

---

## Purchasing Note

- Buy from [approved_sku_sheet.md](approved_sku_sheet.md) and [buying_guide.md](buying_guide.md), not from [bom.md](bom.md).
- Use this file when you want the engineering justification behind those choices.
- Treat hoverboard drive, HC-SR04, and open buck modules as prototype-era compromises, not final commercial hardware.
- Keep UM982, Shurflo, TeeJet TP8004EVS, and the contactor-based e-stop architecture.

---

## CRITICAL CHANGE: UM980 → UM982 (Heading Problem)

**Finding**: The current BOM uses UM980 with GSF (Gaussian Sum Filter) for heading.
GSF requires the vehicle to be moving above `GPS_VEL_YAW_ALIGN_MIN_SPD`, which
**defaults to 5 m/s** in ArduPilot (ArduPilot Issue #24183). Even lowered to 1 m/s,
our paint speed is **0.5 m/s** — below the threshold. GSF heading will be unreliable
or unavailable during painting.

**The UM982 solves this completely:**
- Dual-antenna heading works at standstill (no movement required)
- ArduPilot GPS_TYPE=25 (UnicoreMovingBaseline), officially documented for Rover
- ArduSimple simpleRTK3B Compass is 299 EUR (~$325); Holybro H-RTK UM982 at $250 is the better deal (includes dual antennas + cables)
- Heading accuracy: 0.1°/1m baseline (better than any compass near hub motors)
- Same RTK position accuracy as UM980 (8mm horizontal)

**Sources:**
- [ArduPilot Rover: UM982 Dual Antenna Heading](https://ardupilot.org/rover/docs/common-ardusimple-rtk-gps-simplertk3b-compass.html)
- [ArduPilot: GSF 5m/s minimum](https://github.com/ArduPilot/ardupilot/issues/24183)
- [ArduPilot: Compass-less Rover Docs](https://ardupilot.org/rover/docs/common-compassless.html)
- [ArduSimple UM982 Setup Guide](https://www.ardusimple.com/how-to-set-up-simplertk3b-compass-with-the-unicore-um982-in-ardupilot-for-high-precision-gnss-heading/)

---

## COMPETITOR BENCHMARKS (validated specifications)

| Spec | Turf Tank One | TinyMobileRobots Pro X | Our Target |
|------|--------------|----------------------|------------|
| RTK accuracy | ±0.76 cm (local base) | ±2 cm (network RTK) | ±2 cm |
| Paint speed | ~1.0 m/s | 1.1 m/s (4 kph) | 0.5-1.0 m/s |
| Weight | 56 kg (123 lbs) | 35 kg | 25-30 kg |
| Battery | Not published | 640 Wh (5 hr spray) | 640 Wh |
| Paint capacity | 5.5 gal | 10 L (2.6 gal) | 5 gal |
| Line width | Adjustable | 5-10 cm (2-4") | 4" (10 cm) |
| Price | ~$6,000/yr lease | ~$5,000/yr lease | $1,027 BOM / $299/yr RaaS |

**Sources:**
- [Turf Tank One Specs](https://turftank.com/us/turftankone/)
- [TinyMobileRobots Pro X](https://tinymobilerobots.us/robots/tinylinemarker-pro-x)

---

## VALIDATED BOM — Tier 2 (Recommended)

### 1. Controller: Pixhawk 6C Mini — $120 (UNCHANGED)
- **Validated**: Industry standard for ArduRover. No change needed.
- Runs ArduRover 4.5+, 4 serial ports, 6 relay outputs
- 2MB flash, adequate for 4 Lua scripts (120KB heap)

### 2. GPS: Holybro H-RTK Unicore UM982 — $250 (CHANGED from UM980 $180)
- **Change**: UM980 → UM982 (+$70)
- **Why**: Dual-antenna heading eliminates GSF speed dependency
- **Actual price verified**: Holybro official store $249.99 (includes dual antennas + cables)
- **Specs validated from datasheet**:
  - Position: 8mm horizontal RTK, L1/L2/L5 triband
  - Heading: 0.1° at 1m baseline (at 0.4m baseline: 0.25° accuracy; antenna separation ≥30cm)
  - Works at standstill — no movement needed for heading
  - ArduPilot GPS_TYPE=25 (UnicoreMovingBaseline)
- **Includes**: Two GNSS antennas + JST Pixhawk cable (no separate antenna purchase needed)
- **Config**: `GPS1_MB_TYPE=1`, `EK3_SRC1_YAW=2`
- **Serial ports**: Requires two serial ports on Pixhawk (GPS1 + GPS2). Use Serial3 for master, Serial5 for slave.
- **Source**: [Holybro H-RTK UM982](https://holybro.com/products/h-rtk-unicore-um982)

### 4. Motors: Used Hoverboard — $30 (UNCHANGED, with caveats)
- **Must be STM32F103R or GD32F103R** (NOT AT32) — this is load-bearing
- Gen1 single-board only
- FOC firmware (EFeru/hoverboard-firmware-hack-FOC)
- **Validated risk**: Low-speed torque stalling reported (GitHub Issue #97)
  - Mitigation: Use SPEED mode (not voltage mode) in FOC config
  - Set `SPEED_MIN=20 RPM` to prevent stall zone (paint speed = 58 RPM, need margin)
  - `I_MOT_MAX=15A` (raised from 10A for hill/curb recovery)
- **Source**: [EFeru FOC Firmware](https://github.com/EFeru/hoverboard-firmware-hack-FOC)

### 5. Paint Pump: Shurflo 8000-543-236 — $90 (UNCHANGED)
- **Validated specs**:
  - 12V DC, 1.8 GPM open flow, 60 PSI demand switch
  - Viton valves + Santoprene diaphragm — compatible with water-based traffic paint
  - Self-priming, runs dry without damage
- **Paint coverage validated**: 1 gallon = 300-400 linear feet at 4" width, 15-mil wet thickness
- **At 0.5 m/s paint speed**: Need ~0.28 GPM flow — pump at 1.8 GPM has ~6x headroom
  - Pump maintains pressure; solenoid gates flow to nozzle
  - Nozzle is the flow limiter, not the pump — use PWM to control duty cycle
- **Source**: [Shurflo 8000-543-236](https://www.amazon.com/Pentair-8000-543-236-Automatic-Demand-Diaphragm-Santoprene/dp/B00E5UV0W8)

### 6. Solenoid: 3/8" 12V Direct-Acting — $20 (UNCHANGED, with timing data)
- **Must be direct-acting** (not pilot-operated — drips at low pressure)
- **Typical response time**: 15-30ms open, 10-20ms close (12V DC, no paint)
- **With paint**: Add 10-20ms for viscosity drag
- **Recommended Lua timing**: `LEAD_TIME_MS=40`, `LAG_TIME_MS=25` (start here, field-tune)
- **Flyback diode required**: 1N4007 across coil terminals

### 7. Nozzle: TeeJet TP8004EVS — $15 (UNCHANGED, validated correct)
- **Validated flow rate match** (see analysis section below):
  - At 0.5 m/s, robot needs 0.281 GPM of paint
  - TP8004 minimum rated pressure is 30 PSI; at 30 PSI delivers 0.40 × sqrt(30/40) = 0.346 GPM
  - Duty cycle = 0.281/0.346 = **81%** — good duty cycle for PWM control
  - At 40 PSI (0.40 GPM), solenoid PWM at ~70% duty provides exact flow
- **No pressure regulator needed** — use AC_Sprayer PWM at ~81% duty cycle instead
  - Paint-compatible pressure regulators cost $800+; cheap ones clog with paint
  - PWM is free and provides better speed-proportional flow control
- **Validated specs**:
  - 80° even flat fan spray pattern
  - 0.40 GPM at 40 PSI, 0.346 GPM at 30 PSI (minimum rated pressure)
  - **Spray height for 4" line**: ~2.4 inches (6 cm) — geometry: `width = 2 × height × tan(40°)`
  - EVS = VisiFlo color-coded (Red = 04 size), stainless steel core
  - Use with 50-mesh strainer to prevent clogging
- **Source**: [TeeJet Catalog](https://www.teejet.com/-/media/dam/agricultural/usa/sales-material/catalog/technical_information.pdf)

### 8. Battery: 36V 18Ah e-bike battery — $160 (CHANGED from 10Ah $100)
- **Change**: 10Ah → 18Ah (+$60)
- **Why**: Competitors use 640Wh. Our original 360Wh (10Ah) was marginal.
  - 36V × 18Ah = 648 Wh — matches TinyMobileRobots' proven capacity
  - TinyMobileRobots gets 5 hours spray time from 640Wh
  - At typical 200W draw: 648Wh ÷ 200W = ~3 hours runtime
  - At heavy 300W draw: 648Wh ÷ 300W = ~2 hours runtime
  - Range with 150-250W average: 2.6-4.3 hours
  - Conservative for budgeting: 90-120 minutes of active painting (accounts for terrain, wind, paint viscosity overhead)
- **Requires**: Same form factor (Hailong case, XT60 connector, 10S BMS with cell balancing)
- **Buying rule**: Do not buy the cheapest generic 18Ah listing. Buy from a vendor that discloses
  cell brand, BMS rating, continuous current rating, and connector type.
- **BATT_LOW_VOLT=33V** (3.3V/cell), **BATT_CRT_VOLT=31V** (3.1V/cell)

### 9. Power Distribution — $65 (UPDATED default shopping recommendation)
- **Change**: The default purchase recommendation is now separate sealed DC-DC rails rather than
  open XL4015 modules.
- **Why**: The engineering analysis already proved the pump needs its own rail. The remaining problem
  is durability. Open hobby buck modules are acceptable on the bench, but not the cleanest purchase
  choice for an outdoor production-minded build.
- Buy now:
  - sealed 36V→12V pump converter with at least 10A continuous rating
  - separate control/avionics rail so pump startup cannot brown out Pixhawk, GNSS, or RC
  - Holybro PM06 V2 as the default regulated Pixhawk power module
- **Selection rule until exact SKUs are frozen**: choose sealed converters with 8-60V input,
  12V fixed output, documented continuous current rating, and outdoor/automotive mounting suitability.
  Do not use open bench buck modules as the final installed power hardware.
- Holybro PM06 V2 power module (current/voltage sensing) — $25
- **Wire gauge**: 12 AWG main power (handles 20A continuous, fused at 30A)
- 30A blade fuse on battery output

### 9a. Obstacle Sensing — Prototype Only Unless Upgraded
- **Prototype option**: HC-SR04 is acceptable for bench testing and very early field trials.
- **Buying rule**: Do not treat HC-SR04 as the final field safety layer. If you want a safer outdoor
  build, buy an outdoor-rated distance sensor or physical bumper stop before relying on autonomous stop behavior.

### 10. E-Stop System — $25 (UNCHANGED)
- 22mm mushroom button → 40A DC contactor
- Button alone cannot break 40A DC — contactor is mandatory
- RC backup: `RC6_OPTION=31` (Motor Emergency Stop) on transmitter SwC

### 11. RC Transmitter: FlySky FS-i6X — $50 (UNCHANGED)
- 10-channel, AFHDS 2A protocol
- Channels: throttle, steering, mode switch, E-stop, pump toggle
- Range: 500m+ (adequate for parking lot operations)

### 12. Frame: 2020 Aluminum Extrusion — $80 (UPDATED with specs)
- **Base**: 600mm × 400mm 2020 extrusion rectangle
- **Must document**: Actual track width measurement → update `WHL_TRACK` parameter
- Motor mount: Harvest original hoverboard brackets, secure with M8 bolts
- GPS antenna mount: 200mm aluminum standoff, centered, ≥30cm between dual antennas
- Paint tank mount: Centered over axle line (CG over drive wheels)
- Nozzle mount: Adjustable height arm, 6-8" above ground, trailing behind robot
- **Weight target**: 20-25 kg dry, ~44-48 kg with 5 gal paint (5 gal = 18.9L; at 1.2-1.4 g/cm³ density = 23-27 kg)

### 13. Paint Tank & Plumbing — $30 (NEW, previously unspecified)
- 5-gallon HDPE pressure tank with lid (not open bucket — prevents splash)
- 3/8" ID reinforced hose from tank → pump → solenoid → nozzle
- Inline 50-mesh strainer before pump intake
- Quick-disconnect fittings for flush system
- Flush procedure: Run 1 quart water through system after each job

---

## TOTAL BOM COST

| Item | v2 Price | v3 Price | Change |
|------|----------|----------|--------|
| Pixhawk 6C Mini | $120 | $106 | -$14 (actual Holybro price) |
| GPS (UM980→Holybro UM982) | $180 | $250 | +$70 (includes dual antennas) |
| Second GNSS antenna | — | — | Included with Holybro UM982 |
| Hoverboard | $30 | $30 | — |
| Shurflo pump | $90 | $90 | — |
| Solenoid | $20 | $20 | — |
| TeeJet nozzle | $15 | $15 | — |
| Battery (10Ah→18Ah) | $100 | $160 | +$60 |
| Power distribution | $37 | $65 | +$28 (separate sealed rails + pump surge margin) |
| E-stop + contactor | $25 | $25 | — |
| RC transmitter | $50 | $50 | — |
| Frame + hardware | $80 | $80 | — |
| Paint tank + plumbing | — | $30 | NEW |
| Wiring, fuses, misc | $53 | $106 | +$53 (see additional parts below) |
| **TOTAL** | **$780** | **$1,027** | **+$247** |

### Additional Parts Not in Line Items

Included in the "Wiring, fuses, misc" line ($106):

| Part | Est. Cost |
|------|-----------|
| ST-Link V2 programmer (for hoverboard flash) | $12 |
| USB-serial adapter (for UM982 config) | $8 |
| 50-mesh inline strainer | $10 |
| Quick-disconnect fittings | $10 |
| 1000uF capacitor for 12V rail | $3 |
| Hose + clamps | $10 |
| Wiring, fuses, connectors, heatshrink | $53 |
| **Subtotal** | **$106** |

**Note**: This is component cost only. Tools (soldering iron, multimeter, drill), shipping, and spare parts add $100-300 depending on what you already own. Realistic all-in cost for a first build: **$1,200-1,500**.

**Cost increase justified by:**
- UM982 eliminates the #1 technical risk (heading at paint speed)
- 18Ah battery matches proven competitor capacity (640Wh)
- Separate sealed power rails reduce brownouts and improve durability
- Paint tank/plumbing was always needed but wasn't specified
- Pixhawk actual price is lower than originally estimated

---

## KEY PARAMETER CHANGES (striper.param)

```
# GPS — UM982 dual-antenna heading
GPS_TYPE=25              # was 24 (UnicoreNMEA) → 25 (UnicoreMovingBaseline)
GPS1_MB_TYPE=1           # NEW: Moving baseline master→slave
GPS1_MB_OFS_X=0.0        # NEW: Measure actual antenna offset (meters)
GPS1_MB_OFS_Y=0.40       # NEW: ~40cm lateral separation (measure actual)
GPS1_MB_OFS_Z=0.0        # NEW: Same height
EK3_SRC1_YAW=2           # was 8 (GSF) → 2 (GPS heading)
COMPASS_ENABLE=0          # Still disabled (hub motor interference)

# Battery — 18Ah capacity
BATT_CAPACITY=18000       # was 10000 → 18000 mAh
BATT_LOW_VOLT=33.0        # 3.3V/cell (10S)
BATT_CRT_VOLT=31.0        # 3.1V/cell emergency

# Navigation — tuned for paint accuracy
WP_RADIUS=0.15            # was 0.05 → safe minimum (5cm causes looping)
WP_OVERSHOOT=0.05         # Prevent overshoot on turns
NAVL1_PERIOD=4            # L1 navigation period (lower = more responsive)
ATC_STR_RAT_P=0.30        # Steering rate P gain (tune on field)
```

---

## VALIDATED RISKS (ranked by impact)

### 1. GPS Multipath Near Buildings — HIGH RISK, NO MITIGATION
- **Data**: Urban canyon effects cause 5-50cm position jitter even with RTK Fixed
- **Our case**: Parking lots are adjacent to buildings — this is unavoidable
- **Mitigation attempts**: Ground plane antenna disc (partial), `GPS_MIN_ELEV=10` (partial)
- **Honest assessment**: Lines near buildings will be less accurate. Budget ±5cm near structures.
- **Competitor approach**: Turf Tank uses local base station (±0.76cm) which helps but doesn't eliminate multipath

### 2. Hoverboard Low-Speed Torque — MEDIUM RISK
- **Data**: FOC firmware Issue #97 reports motor stalling at very low RPM
- **Our paint speed**: 0.5 m/s ≈ 58 RPM (6.5" wheel, circumference 0.518m)
- **Mitigation**: Use SPEED mode, set `SPEED_MIN=50`, raise `I_MOT_MAX=15A`
- **Backup plan**: If hoverboard motors fail at low speed, replace with 24V gearmotors (~$60/pair)

### 3. Paint Timing Calibration — MEDIUM RISK, FIELD-SOLVABLE
- **Data**: Solenoid response 15-30ms, paint adds 10-20ms viscosity delay
- **Total latency**: ~40-60ms open, ~25-40ms close
- **At 0.5 m/s**: 40ms = 2cm lead error, 25ms = 1.25cm lag error
- **Acceptable**: Tune `LEAD_TIME_MS` and `LAG_TIME_MS` per paint brand. Budget 3-5 test runs.

### 4. Battery Runtime Under Real Load — LOW-MEDIUM RISK
- **With 18Ah (648Wh)**: Even at 400W continuous, runtime = 97 minutes
- **Competitors prove 640Wh works**: TinyMobileRobots claims 5hr spray time at lower continuous draw
- **Safety margin**: Adequate for 1-2 parking lots per charge

### 5. RTK Corrections (NTRIP) — REQUIRED FOR 2CM ACCURACY
- RTK corrections (NTRIP) are required for 2cm accuracy. Options:
  - Free community base stations (RTK2GO, if available near your site)
  - Paid service ($40/month from RTKdata or Point One Polaris)
  - Own base station ($300-500 additional hardware cost)

---

## PAINT SYSTEM: FLOW RATE ANALYSIS (corrected)

**Paint consumption at robot speed:**
- Industry standard: 1 gallon = 350 linear feet at 4" width, 15-mil wet thickness
- At 0.5 m/s = 1.64 ft/s = 98.4 ft/min
- Paint consumption: 98.4 ft/min ÷ 350 ft/gal = **0.281 GPM**

**Nozzle sizing validation:**

| Nozzle | Flow @ 40 PSI | Flow @ 30 PSI (min rated) | Duty cycle needed |
|--------|--------------|--------------------------|-------------------|
| TP8004EVS | 0.40 GPM | 0.346 GPM | 70% @ 40 PSI, **81% @ 30 PSI** |
| TP80015EVS | 0.15 GPM | 0.130 GPM | **187% — UNDERSIZED** |

**Result: TP8004EVS is the correct nozzle.** Minimum rated pressure is 30 PSI.
At 30 PSI it delivers 0.346 GPM; duty cycle = 0.281/0.346 = 81% — a good operating
point for PWM control via AC_Sprayer. At 40 PSI, use ~70% duty cycle.
No pressure regulator needed — PWM provides speed-proportional flow control for free.

**Robot-specific paint recommended:**
- US Specialty Coatings "RoboTraffic RTS" — pre-thinned for robotic low-pressure spray
- Standard traffic paint (80-90 KU viscosity) needs 10-20% water thinning for nozzle spray
- Target: 60-70 KU viscosity for reliable atomization at 30-40 PSI

---

## MOTOR PERFORMANCE: VALIDATED NUMBERS

From measured data (ODrive calibration, FOC firmware testing, published papers):

| Parameter | Value | Source |
|-----------|-------|--------|
| Phase resistance | 0.179 Ω | ODrive calibration |
| Phase inductance | 0.336 mH | ODrive calibration |
| Torque at 15A | 6-15 Nm | FFbeast testing, SimpleFOC community |
| Stall current (unprotected) | ~100A | V/R calculation |
| Robot locomotion (40kg, flat) | 50-100W | MDPI Sensors paper |
| Total with paint system | 150-250W | Engineering estimate |
| Battery runtime at 200W avg | ~3 hours (18Ah/648Wh) | Discharge calculation |

**FOC firmware recommendations for this robot:**
- Use **SPEED mode** (not voltage mode) — active current control prevents stall
- `I_MOT_MAX=15A` (safe continuous for 6.5" motors)
- `I_DC_MAX=17A` (safety margin above motor limit)
- `N_MOT_MAX=400 RPM` (limit top speed to ~1.5 m/s)
- The 15A limit provides ~6-10 Nm per wheel — sufficient for a 40kg robot that only
  needs ~3 Nm per wheel for acceleration on flat ground

---

## ARDUROVER CROSS-TRACK ACCURACY: REAL-WORLD DATA

Position accuracy ≠ path-following accuracy. Field reports from ArduRover users:

| Setup | Cross-Track Error | Source |
|-------|------------------|--------|
| RTK Float, tractor, 1.3 m/s | ±19-20 cm | ArduPilot forum |
| RTK Fixed, mower, repeated loops | ~10 cm drift | The Mower Project |
| RTK Fixed, slow rover, tuned PIDs | 2-5 cm | Community consensus |
| Near buildings (multipath) | 5-15 cm | NovAtel multipath studies |

**Our realistic target: ±2-5 cm in open areas, ±5-10 cm near buildings.**
Parking lot line tolerance is ±5-7 cm ("looks straight"), so this is adequate.

---

## PRE-BUILD VALIDATION CHECKLIST

Before spending $1,027, validate these on the bench:

- [ ] **UM982 heading test**: Order eval board, verify GPS_TYPE=25 heading at standstill
- [ ] **Hoverboard UART test**: Flash FOC firmware, verify motor_bridge.lua protocol works
- [ ] **Solenoid timing test**: Measure actual open/close time with water, then with paint
- [ ] **Pump pressure test**: Verify Shurflo 8000 maintains 60 PSI demand switch with paint viscosity
- [ ] **Nozzle pattern test**: Verify 4" line width at 6-8" spray height with TeeJet TP8004EVS
- [ ] **Battery discharge test**: Measure actual current draw of motors under load on pavement
- [ ] **NTRIP connectivity test**: Verify RTK Fix at your test site with chosen NTRIP provider

---

## SOURCES

- [ArduPilot Rover: UM982 Heading Setup](https://ardupilot.org/rover/docs/common-ardusimple-rtk-gps-simplertk3b-compass.html)
- [ArduPilot: GSF 5m/s Minimum Speed Issue](https://github.com/ArduPilot/ardupilot/issues/24183)
- [ArduPilot: Compass-less Rover](https://ardupilot.org/rover/docs/common-compassless.html)
- [ArduPilot: GPS for Yaw](https://ardupilot.org/rover/docs/common-gps-for-yaw.html)
- [ArduSimple UM982 Guide](https://www.ardusimple.com/how-to-set-up-simplertk3b-compass-with-the-unicore-um982-in-ardupilot-for-high-precision-gnss-heading/)
- [EFeru FOC Firmware](https://github.com/EFeru/hoverboard-firmware-hack-FOC)
- [EFeru FOC Low-Speed Stall Issue #97](https://github.com/EFeru/hoverboard-firmware-hack-FOC/issues/97)
- [Shurflo 8000-543-236 Specs](https://www.amazon.com/Pentair-8000-543-236-Automatic-Demand-Diaphragm-Santoprene/dp/B00E5UV0W8)
- [TeeJet Technical Catalog](https://www.teejet.com/-/media/dam/agricultural/usa/sales-material/catalog/technical_information.pdf)
- [Turf Tank Specs](https://turftank.com/us/turftankone/)
- [TinyMobileRobots Pro X](https://tinymobilerobots.us/robots/tinylinemarker-pro-x)
- [ArduRover RTK Field Test](https://www.diyrobocars.com/2021/01/18/using-ardurover-with-an-rtk-gps/)
- [ArduPilot Waypoint Radius Discussion](https://discuss.ardupilot.org/t/waypoint-radius-using-rtk/9732)
- [Parking Lot Paint Coverage](https://bitumio.com/accurate-estimating-how-to-calculate-linear-feet-of-parking-lot-striping/)
- [IEEE: Power Estimation for Differential Drive Robots](https://ieeexplore.ieee.org/document/8675609/)
