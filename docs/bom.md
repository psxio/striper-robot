# Striper Robot -- Bill of Materials (BOM)

Bill of materials for the autonomous parking-lot line-striping robot,
redesigned around **ArduRover on a Pixhawk flight controller** with
**hoverboard drive motors** running open-source FOC firmware.

Three tiers let you start cheap and upgrade as needed. Prices are
approximate USD as of early 2026 and exclude shipping/tax.

---

## Tier 1: $409 "Proof of Concept"

Minimum viable robot. Uses the hoverboard's built-in battery, an ESP32
instead of a Pixhawk, and the cheapest RTK GPS board available. Good
enough to prove the concept in a parking lot.

| # | Component | Specs / Notes | Qty | Cost | Source |
|---|-----------|---------------|-----|------|--------|
| 1 | Used hoverboard | Two 350W BLDC hub motors, 36V battery (2-4Ah), STM32 dual motor controller board. Flash with [hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC). | 1 | $30 | eBay / FB Marketplace |
| 2 | ST-Link V2 programmer | Needed to flash FOC firmware onto the hoverboard mainboard via SWD. | 1 | $6 | [Amazon](https://www.amazon.com/s?k=ST-Link+V2) |
| 3 | 3/4" plywood platform + casters | ~24"x18" plywood base. Two front casters (swivel, 3"). Hoverboard wheels are the rear drive wheels. | 1 | $25 | Home Depot |
| 4 | ESP32-S3 dev board | Runs custom firmware: reads GPS, sends UART speed commands to hoverboard, toggles solenoid relay. Substitute for Pixhawk in this tier. | 1 | $8 | [Amazon](https://www.amazon.com/s?k=ESP32-S3+dev+board) |
| 5 | ArduSimple simpleRTK2B Budget (ZED-F9P) | u-blox ZED-F9P RTK receiver. L1/L2 multi-band. 1-2 cm RTK accuracy. Includes patch antenna. Part: simpleRTK2B Budget Starter Kit. | 1 | $252 | [ArduSimple](https://www.ardusimple.com/product/simplertk2b/) |
| 6 | 12V diaphragm pump | Self-priming, 60-80 PSI, 1-2 GPM. Powers paint flow. | 1 | $30 | [Amazon](https://www.amazon.com/s?k=12V+diaphragm+pump) |
| 7 | 12V solenoid valve (N.C.) | 1/2" NPT, brass, normally closed. On/off paint control. | 1 | $15 | [Amazon](https://www.amazon.com/s?k=12V+solenoid+valve+1%2F2+NPT) |
| 8 | Flat fan spray nozzle + fittings | TeeJet 8004 or equivalent, 4" fan width. Include barb-to-NPT adapters and 3 ft of 1/2" vinyl tubing. | 1 | $15 | [Amazon](https://www.amazon.com/s?k=flat+fan+spray+nozzle) |
| 9 | DC-DC converters (36V to 12V, 36V to 5V) | Buck converters. 36V to 12V (3A min) for pump/solenoid. 36V to 5V (2A min) for ESP32/GPS. | 2 | $10 | [Amazon](https://www.amazon.com/s?k=36V+to+12V+DC+DC+converter) |
| 10 | E-stop button + relay | 22mm mushroom-head, twist-release, N.C. contacts. 30A relay to cut motor power. | 1 | $5 | [Amazon](https://www.amazon.com/s?k=emergency+stop+button+22mm) |
| 11 | Wiring, connectors, fuses | 14 AWG silicone wire, XT60 connectors, 30A blade fuse + holder, zip ties, heat shrink, ring terminals. | 1 lot | $13 | Amazon |

**Tier 1 Total: ~$409**

> **What you give up:** No Pixhawk (no ArduRover autopilot, no Mission
> Planner, no RC override, no geofencing). You must write your own
> waypoint-following firmware on the ESP32. Hoverboard battery gives
> only 20-40 minutes of runtime.

---

## Tier 2: $631 "Best Value" (RECOMMENDED)

The sweet spot. A real Pixhawk running ArduRover gives you autopilot,
Mission Planner, RC manual override, geofencing, and the built-in
AC_Sprayer library. The UM980 GPS is cheaper and more accurate than the
ZED-F9P. A separate e-bike battery gives 2-3 hours of runtime.

| # | Component | Specs / Notes | Qty | Cost | Source |
|---|-----------|---------------|-----|------|--------|
| 1 | Used hoverboard | Same as Tier 1. Motors + mainboard only; the built-in battery becomes a backup/bench-test supply. | 1 | $30 | eBay / FB Marketplace |
| 2 | ST-Link V2 programmer | Same as Tier 1. | 1 | $6 | [Amazon](https://www.amazon.com/s?k=ST-Link+V2) |
| 3 | 2020 aluminum extrusion frame + plywood deck | 500mm lengths of 20x20mm V-slot extrusion, corner brackets, T-nuts, M5 screws. 3/4" plywood deck screwed on top. | 1 | $50 | [Amazon](https://www.amazon.com/s?k=2020+aluminum+extrusion+500mm) / Home Depot |
| 4 | Pixhawk 6C Mini | Holybro Pixhawk 6C Mini. Runs ArduRover firmware. STM32H743, triple IMU, barometer, microSD. Part: Holybro 6C Mini Set. | 1 | $120 | [Holybro](https://holybro.com/products/pixhawk-6c-mini) |
| 5 | Unicore UM980 breakout + multiband antenna | UM980 RTK GNSS module. L1/L2/L5 triple-band, 8mm RTK accuracy. ArduPilot native support. Multiband (L1/L2) patch or helical antenna. | 1 | $165 | [ArduSimple](https://www.ardusimple.com/) / [SparkFun](https://www.sparkfun.com/) |
| 6 | 12V diaphragm pump | Same as Tier 1. | 1 | $30 | Amazon |
| 7 | 12V solenoid valve (N.C.) | Same as Tier 1. | 1 | $15 | Amazon |
| 8 | Flat fan spray nozzle + fittings | Same as Tier 1. Includes tubing, barb adapters, hose clamps. | 1 | $15 | Amazon |
| 9 | Spray system mounting hardware | Nozzle bracket, paint reservoir holder, tube routing clips. | 1 | $20 | Amazon / hardware store |
| 10 | 36V 10Ah e-bike battery | 36V lithium-ion, 10S or equivalent. 360Wh. Includes BMS. XT60 or Anderson connector. | 1 | $100 | [Amazon](https://www.amazon.com/s?k=36V+10Ah+ebike+battery) |
| 11 | DC-DC converters (36V to 12V, 36V to 5V) | Same specs as Tier 1. The 5V BEC powers the Pixhawk and GPS. | 2 | $10 | Amazon |
| 12 | E-stop button | Same as Tier 1. N.C. contacts cut motor power via relay. | 1 | $5 | Amazon |
| 13 | HC-SR04 ultrasonic sensors | 2-400 cm range, 5V. Front-left and front-right obstacle detection. | 2 | $5 | Amazon |
| 14 | RC transmitter + receiver (FlySky FS-i6X) | 6-channel, 2.4 GHz, IBUS/SBUS receiver. Manual override + mode switching. Part: FlySky FS-i6X with FS-iA6B receiver. | 1 | $30 | [Amazon](https://www.amazon.com/s?k=FlySky+FS-i6X) |
| 15 | Wiring, connectors, fuses, mounting | 14/18/22 AWG wire, XT60 connectors, 30A fuse, JST-GH cables for Pixhawk, M3 standoffs, zip ties, heat shrink. | 1 lot | $30 | Amazon |
| 16 | Relay module (2-channel, 5V) | For Pixhawk MAIN OUT to control solenoid and pump. Opto-isolated preferred. | 1 | $5 | Amazon |

**Tier 2 Total: ~$631** (add ~$5 for a 2nd relay channel if controlling pump separately)

---

## Tier 3: $905 "Production Prototype"

Built to run all day on real job sites. Better GPS antenna for multipath
rejection near buildings, bigger battery, weatherproof enclosure,
proper spray tip with filter, and a full-size Pixhawk for expansion.

| # | Component | Specs / Notes | Qty | Cost | Source |
|---|-----------|---------------|-----|------|--------|
| 1 | Used hoverboard | Same as Tier 1/2. Motors + mainboard. | 1 | $30 | eBay / FB Marketplace |
| 2 | ST-Link V2 programmer | Same. | 1 | $6 | Amazon |
| 3 | Aluminum frame + proper casters + paint tray mount | Welded or bolted aluminum tube/extrusion frame. 4" swivel casters (locking). Integrated paint reservoir tray. | 1 | $80 | Amazon / local metal shop |
| 4 | Pixhawk 6C (full size) | Holybro Pixhawk 6C. Full-size with all ports. More serial ports, CAN bus, dual redundant power. Part: Holybro Pixhawk 6C Standard Set. | 1 | $180 | [Holybro](https://holybro.com/products/pixhawk-6c) |
| 5 | Unicore UM980 breakout | Same module as Tier 2. | 1 | $120 | ArduSimple / SparkFun |
| 6 | Quality multiband GNSS antenna | Survey-grade L1/L2/L5 antenna with ground plane. Better multipath rejection for parking lots near buildings. (e.g., u-blox ANN-MB-00 or Beitian BT-800D). | 1 | $65 | [SparkFun](https://www.sparkfun.com/) / [DigiKey](https://www.digikey.com/) |
| 7 | Graco-style spray tip + filter + fittings | Graco RAC 5 LL5319 reversible tip, inline filter (60-mesh), tip guard. Professional-grade line quality. | 1 | $100 | Amazon / [Graco](https://www.graco.com/) / paint supply |
| 8 | 36V 15Ah e-bike battery + charger | 36V lithium-ion, 15Ah (540Wh). Includes BMS. Bundled 42V 2A charger. 4-6 hours runtime. | 1 | $140 | [Amazon](https://www.amazon.com/s?k=36V+15Ah+ebike+battery+charger) |
| 9 | DC-DC converters + fuse panel | 36V to 12V (5A), 36V to 5V (3A). ATC fuse panel (4-way) for organized power distribution. | 1 | $20 | Amazon |
| 10 | E-stop button | Same as Tier 1/2. | 1 | $5 | Amazon |
| 11 | HC-SR04 ultrasonic sensors | Same as Tier 2. | 2 | $5 | Amazon |
| 12 | FlySky FS-i6X (full 10-channel) | 10-channel transmitter. Extra channels for spray on/off toggle, speed dial, mode switch. Part: FlySky FS-i6X + FS-iA10B receiver. | 1 | $50 | [Amazon](https://www.amazon.com/s?k=FlySky+FS-i6X+10+channel) |
| 13 | Weatherproof enclosure | IP65, ~300x200x120mm. Houses Pixhawk, DC-DC converters, relay module, fuse panel. | 1 | $20 | [Amazon](https://www.amazon.com/s?k=IP65+enclosure+300x200) |
| 14 | 12V diaphragm pump | Same as Tier 1/2. Higher quality (Shurflo or equivalent) for consistent pressure. | 1 | $40 | Amazon |
| 15 | 12V solenoid valve (N.C.) | Same as Tier 1/2. | 1 | $15 | Amazon |
| 16 | Wiring, connectors, mounting hardware | Same categories as Tier 2, plus waterproof connectors (aviation plugs), cable glands for enclosure. | 1 lot | $30 | Amazon |

**Tier 3 Total: ~$905**

---

## Tier Comparison

| Feature | Tier 1 ($409) | Tier 2 ($631) | Tier 3 ($905) |
|---------|---------------|---------------|---------------|
| Autopilot | ESP32 (custom FW) | Pixhawk 6C Mini (ArduRover) | Pixhawk 6C Full (ArduRover) |
| GPS module | ZED-F9P (1-2 cm) | UM980 (8 mm) | UM980 (8 mm) + quality antenna |
| Runtime | 20-40 min (hoverboard battery) | 2-3 hrs (36V 10Ah) | 4-6 hrs (36V 15Ah) |
| RC override | No | Yes (FlySky 6ch) | Yes (FlySky 10ch) |
| Mission Planner | No | Yes | Yes |
| Geofencing | No | Yes (ArduRover) | Yes (ArduRover) |
| Spray quality | Basic nozzle | Basic nozzle | Graco reversible tip + filter |
| Obstacle detection | No | 2x ultrasonic | 2x ultrasonic |
| Weatherproofing | None | None | IP65 enclosure |
| Frame | Plywood | Aluminum extrusion + plywood | Aluminum + proper casters |

---

## What You Get from a Used Hoverboard

A single used hoverboard ($20-50) provides all of the following:

- **Two 350W BLDC hub motors** with built-in hall sensors (replace $80+ in motors)
- **A 36V battery pack** (2-4Ah, fine for bench testing)
- **An STM32-based dual motor controller board** (replace $25-80 in motor drivers + ESP32 PID controller)
- **Wheels and tires** already attached to the motors

Flash the mainboard with [hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC) using an ST-Link V2 ($6). The FOC firmware accepts UART speed commands for each motor independently -- exactly what ArduRover (or an ESP32) sends for differential/skid steering.

**Proven in:** HoverMower, ESP32-Hoverboard-Lawnmower, HoverBot, CHEAP-LAWNMOWER-ROBOT-FROM-HOVERBOARD, and dozens of other open-source robot projects.

---

## Where to Buy

| Vendor | URL | What to Buy |
|--------|-----|-------------|
| ArduSimple | https://www.ardusimple.com | simpleRTK2B (ZED-F9P), UM980 boards, GNSS antennas, RTK kits |
| Holybro | https://holybro.com | Pixhawk 6C / 6C Mini, PM02 power module, GPS modules |
| SparkFun | https://www.sparkfun.com | GPS-RTK boards (ZED-F9P), UM980 breakout, GNSS antennas, breakouts |
| Amazon | https://www.amazon.com | Hoverboard batteries, DC-DC converters, pumps, solenoids, wire, FlySky RC, extrusions, enclosures, everything else |
| AliExpress | https://www.aliexpress.com | Budget alternative for UM980 boards, ST-Link clones, ESP32 boards, DC-DC converters, relay modules (longer shipping) |
| eBay / FB Marketplace | https://www.ebay.com | Used hoverboards ($20-50) |
| Home Depot | https://www.homedepot.com | Plywood, casters, tubing, fittings, spray paint (for demos) |
| DigiKey | https://www.digikey.com | Discrete components, connectors, GNSS antennas (u-blox ANN-MB-00) |
| OpenBuilds | https://openbuildspartstore.com | 2020 V-slot extrusion, corner brackets, T-nuts |
| Graco | https://www.graco.com | Professional spray tips (RAC 5 series), filters, tip guards |

---

## Part Numbers Quick Reference

| Part | Part Number / Search Term |
|------|--------------------------|
| Pixhawk 6C Mini | Holybro Pixhawk 6C Mini Set |
| Pixhawk 6C (full) | Holybro Pixhawk 6C Standard Set |
| simpleRTK2B Budget | ArduSimple simpleRTK2B Budget Starter Kit LR |
| Unicore UM980 | UM980 (search ArduSimple or SparkFun for breakout boards) |
| u-blox ZED-F9P | ZED-F9P (on simpleRTK2B board) |
| GNSS antenna (budget) | u-blox ANN-MB-00 or patch antenna included with simpleRTK2B |
| GNSS antenna (quality) | Beitian BT-800D / u-blox ANN-MB-00 |
| FlySky RC (6ch) | FS-i6X + FS-iA6B receiver |
| FlySky RC (10ch) | FS-i6X + FS-iA10B receiver |
| Hoverboard FOC firmware | https://github.com/EFeru/hoverboard-firmware-hack-FOC |
| Graco spray tip | RAC 5 LL5319 (4" line, 0.019" orifice) |
| ST-Link V2 | ST-Link V2 (generic clone, SWD programmer) |

---

## Notes

- **RTK corrections:** You need an RTK correction source for centimeter
  accuracy. Options: own base station ($60-150 one-time with a second
  UM980 or LC29H), RTK2Go (free community NTRIP), or Point One Polaris
  ($50/month commercial). Budget for this separately.
- **Paint:** Water-based latex traffic paint, ~$15-25/gallon,
  ~350 linear feet per gallon. A 50-space lot needs 4-5 gallons.
- **Charger:** Tier 1 uses the hoverboard's included charger. Tiers 2/3
  need a 42V (10S) lithium-ion charger if not bundled with the battery.
- **Tools needed:** Soldering iron, multimeter, hex keys, drill, wire
  strippers, crimping tool. ST-Link V2 and a laptop with
  STM32CubeProgrammer for flashing hoverboard firmware.
