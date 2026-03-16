# Validated BOM v3 — Research-Backed Hardware Specification

> **Date**: 2026-03-16
> **Method**: Cross-referenced against ArduPilot docs, datasheets, competitor teardowns,
> research papers, and manufacturer specifications. Every change from v2 is justified below.

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
- ArduSimple simpleRTK3B Compass is a direct drop-in (~$210, vs $180 for UM980)
- Heading accuracy: 0.2°/1m baseline (better than any compass near hub motors)
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
| Price | ~$6,000/yr lease | ~$5,000/yr lease | $780 BOM / $299/yr RaaS |

**Sources:**
- [Turf Tank One Specs](https://turftank.com/us/turftankone/)
- [TinyMobileRobots Pro X](https://tinymobilerobots.us/robots/tinylinemarker-pro-x)

---

## VALIDATED BOM — Tier 2 (Recommended)

### 1. Controller: Pixhawk 6C Mini — $120 (UNCHANGED)
- **Validated**: Industry standard for ArduRover. No change needed.
- Runs ArduRover 4.5+, 4 serial ports, 6 relay outputs
- 2MB flash, adequate for 4 Lua scripts (120KB heap)

### 2. GPS: ArduSimple simpleRTK3B Compass (UM982) — $210 (CHANGED from UM980 $180)
- **Change**: UM980 → UM982 (+$30)
- **Why**: Dual-antenna heading eliminates GSF speed dependency
- **Specs validated from datasheet**:
  - Position: 8mm horizontal RTK, L1/L2/L5 triband
  - Heading: 0.2° at 1m baseline (antenna separation ≥30cm)
  - Works at standstill — no movement needed for heading
  - ArduPilot GPS_TYPE=25 (UnicoreMovingBaseline)
- **Requires**: Two GNSS antennas, mounted ≥30cm apart on robot frame
- **Config**: `GPS1_MB_TYPE=1`, `EK3_SRC1_YAW=2`
- **Source**: [ArduSimple simpleRTK3B Compass](https://www.ardusimple.com/product/simplertk3b-compass/)

### 3. Second GNSS Antenna — $15 (NEW)
- The UM982 needs two antennas for heading
- Same type as primary (L1/L2/L5 multiband patch)
- Mount on opposite end of robot frame, ≥30cm from primary
- Longer baseline = better heading accuracy (0.2° at 1m, 0.1° at 2m)

### 4. Motors: Used Hoverboard — $30 (UNCHANGED, with caveats)
- **Must be STM32F103R or GD32F103R** (NOT AT32) — this is load-bearing
- Gen1 single-board only
- FOC firmware (EFeru/hoverboard-firmware-hack-FOC)
- **Validated risk**: Low-speed torque stalling reported (GitHub Issue #97)
  - Mitigation: Use SPEED mode (not voltage mode) in FOC config
  - Set `SPEED_MIN=50 RPM` to prevent stall zone
  - `I_MOT_MAX=15A` (raised from 10A for hill/curb recovery)
- **Source**: [EFeru FOC Firmware](https://github.com/EFeru/hoverboard-firmware-hack-FOC)

### 5. Paint Pump: Shurflo 8000-543-236 — $90 (UNCHANGED)
- **Validated specs**:
  - 12V DC, 1.0 GPM at 50 PSI (demand switch at 50 PSI)
  - Viton valves + Santoprene diaphragm — compatible with water-based traffic paint
  - Self-priming, runs dry without damage
- **Paint coverage validated**: 1 gallon = 300-400 linear feet at 4" width, 15-mil wet thickness
- **At 0.5 m/s paint speed**: Need ~0.025 GPM flow — pump is 40x oversized
  - Control via duty-cycling solenoid, NOT pump speed
  - Pump maintains pressure; solenoid gates flow to nozzle
- **Source**: [Shurflo 8000-543-236](https://www.amazon.com/Pentair-8000-543-236-Automatic-Demand-Diaphragm-Santoprene/dp/B00E5UV0W8)

### 6. Solenoid: 3/8" 12V Direct-Acting — $20 (UNCHANGED, with timing data)
- **Must be direct-acting** (not pilot-operated — drips at low pressure)
- **Typical response time**: 15-30ms open, 10-20ms close (12V DC, no paint)
- **With paint**: Add 10-20ms for viscosity drag
- **Recommended Lua timing**: `LEAD_TIME_MS=40`, `LAG_TIME_MS=25` (start here, field-tune)
- **Flyback diode required**: 1N4007 across coil terminals

### 7. Nozzle: TeeJet TP8004EVS — $15 (UNCHANGED, with validated specs)
- **Validated specs**:
  - 80° even flat fan spray pattern
  - 0.4 GPM at 40 PSI (0.35-0.49 GPM range at 30-60 PSI)
  - **Spray height for 4" line**: 6-8 inches (15-20 cm) above pavement
  - EVS = VisiFlo color-coded (Red = 04 size), stainless steel core
  - Use with 50-mesh strainer to prevent clogging
- **Line width at 6" height**: ~4 inches (10 cm) with 80° fan angle
- **Source**: [TeeJet Catalog](https://www.teejet.com/-/media/dam/agricultural/usa/sales-material/catalog/technical_information.pdf)

### 8. Battery: 36V 18Ah e-bike battery — $160 (CHANGED from 10Ah $100)
- **Change**: 10Ah → 18Ah (+$60)
- **Why**: Competitors use 640Wh. Our original 360Wh (10Ah) was marginal.
  - 36V × 18Ah = 648 Wh — matches TinyMobileRobots' proven capacity
  - TinyMobileRobots gets 5 hours spray time from 640Wh
  - At 300W average draw: 648Wh ÷ 300W = 2.16 hours runtime
  - At 200W average draw: 648Wh ÷ 200W = 3.24 hours runtime
  - Conservative estimate: 90-120 minutes of active painting
- **Requires**: Same form factor (Hailong case, XT60 connector, 10S BMS with cell balancing)
- **BATT_LOW_VOLT=33V** (3.3V/cell), **BATT_CRT_VOLT=31V** (3.1V/cell)

### 9. Power Distribution — $37 (UNCHANGED)
- XL4015 5A buck converter (36V→12V) for pump, solenoid, Pixhawk — $12
- Holybro PM06 V2 power module (current/voltage sensing) — $25
- **Wire gauge**: 12 AWG main power (10A continuous at 36V = 360W)
- 30A blade fuse on battery output

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
- **Weight target**: 20-25 kg dry, 30-35 kg with 5 gal paint

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
| Pixhawk 6C Mini | $120 | $120 | — |
| GPS (UM980→UM982) | $180 | $210 | +$30 |
| Second GNSS antenna | — | $15 | NEW |
| Hoverboard | $30 | $30 | — |
| Shurflo pump | $90 | $90 | — |
| Solenoid | $20 | $20 | — |
| TeeJet nozzle | $15 | $15 | — |
| Battery (10Ah→18Ah) | $100 | $160 | +$60 |
| Power distribution | $37 | $37 | — |
| E-stop + contactor | $25 | $25 | — |
| RC transmitter | $50 | $50 | — |
| Frame + hardware | $80 | $80 | — |
| Paint tank + plumbing | — | $30 | NEW |
| Wiring, fuses, misc | $53 | $53 | — |
| **TOTAL** | **$780** | **$935** | **+$155** |

**Cost increase justified by:**
- UM982 eliminates the #1 technical risk (heading at paint speed)
- 18Ah battery matches proven competitor capacity (640Wh)
- Paint tank/plumbing was always needed but wasn't specified

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
WP_RADIUS=0.10            # was 0.20 → tighter waypoint hit (10cm)
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
- **Our paint speed**: 0.5 m/s ≈ 30 RPM (hoverboard wheel ~350mm diameter)
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

---

## PRE-BUILD VALIDATION CHECKLIST

Before spending $935, validate these on the bench:

- [ ] **UM982 heading test**: Order eval board, verify GPS_TYPE=25 heading at standstill
- [ ] **Hoverboard UART test**: Flash FOC firmware, verify motor_bridge.lua protocol works
- [ ] **Solenoid timing test**: Measure actual open/close time with water, then with paint
- [ ] **Pump pressure test**: Verify Shurflo 8000 maintains 40 PSI with paint viscosity
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
