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
| 6 | 12V diaphragm pump | Self-priming, 60-80 PSI, 1-2 GPM. For Tier 1 proof-of-concept, a cheap pump works with water. For real paint, upgrade to Shurflo 8000 (see Tier 2). | 1 | $30 | [Amazon](https://www.amazon.com/s?k=12V+diaphragm+pump) |
| 7 | 12V solenoid valve (N.C.) | **3/8" NPT, brass, direct-acting** (not pilot-operated). Normally closed. | 1 | $20 | [Amazon](https://www.amazon.com/s?k=3%2F8+12V+solenoid+valve+brass+direct+acting) |
| 8 | Flat fan spray nozzle + fittings | TeeJet TP8004EVS (even spray variant), 4" fan width. Include 60-mesh inline strainer, barb-to-NPT adapters and 3 ft of 3/8" vinyl tubing. | 1 | $15 | [Amazon](https://www.amazon.com/s?k=TeeJet+TP8004EVS) |
| 9 | DC-DC converters (36V to 12V, 36V to 5V) | Buck converters. 36V to 12V (**5A min**) for pump/solenoid. 36V to 5V (2A min) for ESP32/GPS. | 2 | $15 | [Amazon](https://www.amazon.com/s?k=36V+to+12V+DC+DC+converter+5A) |
| 10 | E-stop button + relay | 22mm mushroom-head, twist-release, N.C. contacts. 30A relay to cut motor power. | 1 | $5 | [Amazon](https://www.amazon.com/s?k=emergency+stop+button+22mm) |
| 11 | Wiring, connectors, fuses | **12 AWG** silicone wire (main power), XT60 connectors, 30A blade fuse + holder, 1N4007 flyback diodes, zip ties, heat shrink, ring terminals. | 1 lot | $15 | Amazon |

**Tier 1 Total: ~$424**

> **What you give up:** No Pixhawk (no ArduRover autopilot, no Mission
> Planner, no RC override, no geofencing). You must write your own
> waypoint-following firmware on the ESP32. Hoverboard battery gives
> only 20-40 minutes of runtime.

---

## Tier 2: $780 "Best Value" (RECOMMENDED)

The sweet spot. A real Pixhawk running ArduRover gives you autopilot,
Mission Planner, RC manual override, geofencing, and the built-in
AC_Sprayer library. The UM980 GPS is cheaper and more accurate than the
ZED-F9P. A separate e-bike battery gives 45-70 minutes of runtime
(realistic, accounting for average motor + paint system draw).

> **Important: Hoverboard compatibility.** The mainboard **must** have an
> **STM32F103RCT6** or **GD32F103RCT6** chip. Boards with **AT32** chips
> (common on cheap new hoverboards) are **NOT compatible** with the FOC
> firmware. Gen2 "split boards" (two separate PCBs) are also incompatible.
> Check the chip markings before buying. Prefer used Gen1 single-board
> hoverboards from 2017-2020.

| # | Component | Specs / Notes | Qty | Cost | Source |
|---|-----------|---------------|-----|------|--------|
| 1 | Used hoverboard | Two 350W BLDC hub motors + STM32F103R single mainboard. **Verify chip is STM32F103RCT6 or GD32F103RCT6** (NOT AT32). Gen1 single-board only. The built-in battery becomes a backup/bench-test supply. | 1 | $30 | eBay / FB Marketplace |
| 2 | ST-Link V2 programmer | Same as Tier 1. | 1 | $6 | [Amazon](https://www.amazon.com/s?k=ST-Link+V2) |
| 3 | 2020 aluminum extrusion frame + plywood deck | 500mm lengths of 20x20mm V-slot extrusion, corner brackets, T-nuts, M5 screws. 3/4" plywood deck as stressed skin. Harvest original hub motor brackets from the hoverboard shell for mounting. | 1 | $50 | [Amazon](https://www.amazon.com/s?k=2020+aluminum+extrusion+500mm) / Home Depot |
| 4 | Pixhawk 6C Mini | Holybro Pixhawk 6C Mini. Runs ArduRover firmware. STM32H743, triple IMU, barometer, microSD. Part: Holybro 6C Mini Set. | 1 | $120 | [Holybro](https://holybro.com/products/pixhawk-6c-mini) |
| 5 | Unicore UM980 breakout + triband antenna | ArduSimple simpleRTK3B Budget (recommended). UM980 RTK GNSS module. L1/L2/L5 triple-band, 8mm RTK accuracy. ArduPilot native support (`GPS_TYPE=24`). Includes JST-GH cable for Pixhawk GPS port. Pair with a triband L1/L2/L5 antenna for full benefit. | 1 | $180 | [ArduSimple](https://www.ardusimple.com/product/simplertk3b-budget/) |
| 6 | Shurflo 8000 diaphragm pump | **Shurflo 8000-543-236** (or 8000-543-238). 12V, 60 PSI, 1.0 GPM. Self-priming. Handles traffic paint viscosity (thin 10-15% with water). Cheap Amazon pumps will clog or fail with real traffic paint. | 1 | $90 | [Amazon](https://www.amazon.com/s?k=Shurflo+8000+diaphragm+pump+12V) |
| 7 | 12V solenoid valve (N.C., direct-acting) | **3/8" NPT, brass, direct-acting** (NOT pilot-operated). Direct-acting valves work at zero pressure differential. Pilot-operated valves require minimum flow pressure to seal and will drip at low pump speeds. | 1 | $20 | [Amazon](https://www.amazon.com/s?k=3%2F8+12V+solenoid+valve+brass+normally+closed+direct+acting) |
| 8 | TeeJet TP8004EVS nozzle + fittings | **TeeJet TP8004EVS** (Even Spray variant). The standard 8004 has tapered edges producing uneven line width. The EVS variant delivers uniform distribution across the full fan. At 60mm nozzle height = ~100mm (4") line width. Include 60-mesh inline strainer, barb-to-NPT adapters, and 3ft of 3/8" vinyl tubing. | 1 | $15 | [Amazon](https://www.amazon.com/s?k=TeeJet+TP8004EVS) / [SpraySmarter](https://www.spraysmarter.com/) |
| 9 | Paint flush system + mounting hardware | 500ml water reservoir + 3-way T-valve for automatic nozzle flush (prevents clogging during pauses >30 seconds). Nozzle bracket, paint reservoir holder, tube routing clips. Use normal-dry traffic paint only (fast-dry clogs nozzle in <2 min). | 1 | $25 | Amazon / hardware store |
| 10 | 36V 10Ah e-bike battery | 36V lithium-ion, 10S or equivalent. 360Wh. Includes 30A BMS. XT60 or Anderson connector. **Realistic runtime: 45-70 minutes** (not 2-3 hours — motors draw 200-400W average, pump draws 36W). | 1 | $100 | [Amazon](https://www.amazon.com/s?k=36V+10Ah+ebike+battery) |
| 11 | 36V→12V DC-DC converter (5A) | **5A minimum, 10A preferred** (XL4015 or LM2596HV). The Shurflo pump has 15-24A inrush on startup; a 3A converter will brownout. 5A handles steady-state; 10A handles inrush with margin. | 1 | $12 | [Amazon](https://www.amazon.com/s?k=36V+to+12V+DC+DC+converter+5A) |
| 12 | Holybro PM06 V2 power module | Replaces generic 5V BEC. Provides regulated 5.2V/3A to Pixhawk with **built-in battery voltage and current monitoring** (INA226 sensor). Plugs directly into Pixhawk POWER port via JST-GH. Input range: 7-42V. | 1 | $25 | [Holybro](https://holybro.com/products/pm06-v2) |
| 13 | E-stop button + DC contactor | 22mm mushroom-head twist-release button (N.C. contacts). **Route through a 40A DC contactor** (e.g., Hella 4RA relay or EV200 style). The 22mm button's contacts energize the contactor coil; the contactor breaks the 36V/40A main power. A bare e-stop button cannot reliably break 40A DC. | 1 | $25 | Amazon |
| 14 | HC-SR04 ultrasonic sensors | 2-400 cm range, 5V. Front-left and front-right obstacle detection. Connected via Arduino Nano bridge to Pixhawk SERIAL4. | 2 | $5 | Amazon |
| 15 | RC transmitter + receiver (FlySky FS-i6X) | 6-channel, 2.4 GHz, IBUS/SBUS receiver. Manual override + mode switching. Part: FlySky FS-i6X with FS-iA6B receiver. | 1 | $30 | [Amazon](https://www.amazon.com/s?k=FlySky+FS-i6X) |
| 16 | Wiring, connectors, fuses, mounting | **12 AWG** silicone wire (main power, not 14 AWG), 18 AWG (12V rail), 22 AWG (signals). XT60 connectors, 30A blade fuse + holder, JST-GH cables for Pixhawk, M3 standoffs, zip ties, heat shrink. **Include 2x 1N4007 flyback diodes** for solenoid and pump. | 1 lot | $30 | Amazon |
| 17 | Relay module (2-channel, 5V) | For Pixhawk AUX OUT to control solenoid and pump. Opto-isolated preferred. | 1 | $5 | Amazon |
| 18 | 60-mesh inline paint strainer | Prevents nozzle clogs from paint solids. Install between pump outlet and solenoid inlet. | 1 | $5 | Amazon |
| 19 | 1N4007 flyback diodes (2x) | Suppress voltage spikes when relay opens solenoid/pump. Cathode to positive, anode to negative terminal. | 2 | $2 | Amazon |

**Tier 2 Total: ~$780**

> **What changed from original $631 estimate:** Pump upgraded from $30
> generic to $90 Shurflo (traffic paint needs it). BEC upgraded from $5
> generic to $25 Holybro PM06 V2 (battery monitoring). E-stop needs $20
> contactor (button alone can't break 40A). 12V converter needs 5A ($12
> not $5). Solenoid changed to direct-acting ($20 not $15). Added flush
> system, strainer, and flyback diodes. UM980 breakout realistic price
> $180. These are corrections from deep hardware research — cutting
> corners here will cause field failures.

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
| 9 | DC-DC converter (36V→12V, 10A) + Holybro PM06 V2 | 36V to 12V (10A, XL4015) for pump/solenoid. Holybro PM06 V2 for 5V with battery monitoring. ATC fuse panel (4-way). | 1 | $45 | Amazon / Holybro |
| 10 | E-stop button + DC contactor | Same as Tier 2. 22mm button drives 40A DC contactor coil. | 1 | $25 | Amazon |
| 11 | HC-SR04 ultrasonic sensors | Same as Tier 2. | 2 | $5 | Amazon |
| 12 | FlySky FS-i6X (full 10-channel) | 10-channel transmitter. Extra channels for spray on/off toggle, speed dial, mode switch. Part: FlySky FS-i6X + FS-iA10B receiver. | 1 | $50 | [Amazon](https://www.amazon.com/s?k=FlySky+FS-i6X+10+channel) |
| 13 | Weatherproof enclosure | IP65, ~300x200x120mm. Houses Pixhawk, DC-DC converters, relay module, fuse panel. | 1 | $20 | [Amazon](https://www.amazon.com/s?k=IP65+enclosure+300x200) |
| 14 | Shurflo 8000 diaphragm pump | Same as Tier 2. Shurflo 8000-543-236, 12V, 60 PSI. Handles traffic paint. | 1 | $90 | Amazon |
| 15 | 12V solenoid valve (N.C., direct-acting) | Same as Tier 2. 3/8" brass, direct-acting. | 1 | $20 | Amazon |
| 16 | Paint flush system | 500ml water reservoir + 3-way T-valve + 60-mesh inline strainer. | 1 | $25 | Amazon / hardware store |
| 17 | Wiring, connectors, mounting hardware | 12 AWG main power, plus waterproof connectors (aviation plugs), cable glands for enclosure, 1N4007 flyback diodes. | 1 lot | $30 | Amazon |

**Tier 3 Total: ~$1,050**

---

## Tier Comparison

| Feature | Tier 1 ($409) | Tier 2 ($780) | Tier 3 ($1,050) |
|---------|---------------|---------------|---------------|
| Autopilot | ESP32 (custom FW) | Pixhawk 6C Mini (ArduRover) | Pixhawk 6C Full (ArduRover) |
| GPS module | ZED-F9P (1-2 cm) | UM980 (8 mm) | UM980 (8 mm) + survey antenna |
| Runtime | 20-40 min (hoverboard battery) | 45-70 min (36V 10Ah) | 90-120 min (36V 15Ah) |
| Pump | Generic diaphragm | Shurflo 8000 (traffic paint) | Shurflo 8000 (traffic paint) |
| Nozzle | Basic flat fan | TeeJet TP8004EVS (even spray) | Graco RAC 5 reversible tip |
| RC override | No | Yes (FlySky 6ch) | Yes (FlySky 10ch) |
| Mission Planner | No | Yes | Yes |
| Geofencing | No | Yes (ArduRover) | Yes (ArduRover) |
| Obstacle detection | No | 2x ultrasonic | 2x ultrasonic |
| Weatherproofing | None | None | IP65 enclosure |
| Frame | Plywood | Aluminum extrusion + plywood | Aluminum + proper casters |
| E-stop | Button + relay | Button + DC contactor | Button + DC contactor |

---

## What You Get from a Used Hoverboard

A single used hoverboard ($20-50) provides all of the following:

- **Two 350W BLDC hub motors** with built-in hall sensors (replace $80+ in motors)
- **A 36V battery pack** (2-4Ah, fine for bench testing)
- **An STM32-based dual motor controller board** (replace $25-80 in motor drivers + ESP32 PID controller)
- **Wheels and tires** already attached to the motors

Flash the mainboard with [hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC) using an ST-Link V2 ($6). The FOC firmware accepts UART speed commands for each motor independently -- exactly what ArduRover (or an ESP32) sends for differential/skid steering.

**Proven in:** HoverMower, ESP32-Hoverboard-Lawnmower, HoverBot, CHEAP-LAWNMOWER-ROBOT-FROM-HOVERBOARD, and dozens of other open-source robot projects.

### Hoverboard Compatibility — CRITICAL

**Not all hoverboards work.** The FOC firmware only supports specific MCU chips:

| Chip | Compatible? | Notes |
|------|-------------|-------|
| **STM32F103RCT6** | YES | Most common on 2017-2020 boards. The standard. |
| **GD32F103RCT6** | YES | GigaDevice clone of STM32F103. Works identically. |
| **AT32F403A** | **NO** | Common on cheap new (2023+) boards. Different register map. |
| **AT32F421** | **NO** | Another incompatible Artery chip. |
| **GD32F130** | **NO** | Lower-tier GD chip, insufficient peripherals. |

**How to check before buying:**
1. Ask the seller for a photo of the mainboard
2. Look for the largest IC on the board (usually 64-pin LQFP)
3. The chip marking must start with **STM32F103** or **GD32F103**
4. If it says **AT32** or you can't read it, pass on that board

**Board topology:** Must be a **single-board** design (one large PCB controls
both motors). "Gen2" hoverboards with **two separate smaller boards**
(one per wheel) are NOT compatible — the FOC firmware expects a single
board controlling both motors.

**UART for Pixhawk:** Use **USART3** (right sideboard connector). This pin
is 5V-tolerant and works directly with Pixhawk 3.3V UART. The FOC UART
protocol sends 8-byte packets: `[0xABCD header][int16 steer][int16 speed][XOR checksum]`
at 115200 baud.

**Power latch bypass:** Hoverboards have a momentary-press power button
with a latch circuit. For continuous robot operation, bypass the latch by
connecting the power button pads permanently (solder bridge or jumper wire).

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
| Holybro PM06 V2 | Holybro PM06 V2 Power Module |
| simpleRTK3B Budget (UM980) | ArduSimple simpleRTK3B Budget |
| simpleRTK2B Budget (ZED-F9P) | ArduSimple simpleRTK2B Budget Starter Kit LR |
| Triband GNSS antenna | ArduSimple Budget Survey Tripleband Antenna (IP66) |
| FlySky RC (6ch) | FS-i6X + FS-iA6B receiver |
| FlySky RC (10ch) | FS-i6X + FS-iA10B receiver |
| Diaphragm pump | **Shurflo 8000-543-236** (12V, 60 PSI, 1.0 GPM) |
| Spray nozzle | **TeeJet TP8004EVS** (even spray, 4" fan at 60mm height) |
| Solenoid valve | 3/8" NPT brass, 12V NC, **direct-acting** |
| Graco spray tip (Tier 3) | RAC 5 LL5319 (4" line, 0.019" orifice) |
| DC contactor (E-stop) | 40A DC contactor / Hella 4RA style relay |
| Hoverboard FOC firmware | https://github.com/EFeru/hoverboard-firmware-hack-FOC |
| ST-Link V2 | ST-Link V2 (generic clone, SWD programmer) |

---

## Notes

- **RTK corrections:** You need an RTK correction source for centimeter
  accuracy. Options: own base station ($60-150 one-time with a second
  UM980 or LC29H), RTK2Go (free community NTRIP), or Point One Polaris
  ($50/month commercial). Budget for this separately.
- **Paint:** Water-based **normal-dry** latex traffic paint, ~$15-25/gallon,
  ~350 linear feet per gallon. A 50-space lot needs 4-5 gallons.
  **Thin 10-15% with water** for diaphragm pump compatibility. **Do NOT use
  fast-dry paint** — it clogs the nozzle in under 2 minutes.
- **Paint edge quality:** Our low-pressure diaphragm system won't match
  commercial airless stripers on edge sharpness. Acceptable for parking
  lot lines but not for fine detail work.
- **Charger:** Tier 1 uses the hoverboard's included charger. Tiers 2/3
  need a 42V (10S) lithium-ion charger if not bundled with the battery.
- **Runtime reality:** The BOM originally estimated 2-3 hours. Realistic
  runtime with 10Ah battery is **45-70 minutes** (motors draw 200-400W
  average, pump 36W, electronics 5W). For all-day operation, buy a spare
  battery or upgrade to 15Ah (Tier 3).
- **Compass:** Disable the internal compass (`COMPASS_ENABLE=0`). The hub
  motor permanent magnets create overwhelming magnetic interference.
  ArduRover uses GPS-based heading estimation (GSF) which works well for
  rovers moving at 0.5+ m/s in open sky.
- **Tools needed:** Soldering iron, multimeter, hex keys, drill, wire
  strippers, crimping tool. ST-Link V2 and a laptop with
  STM32CubeProgrammer for flashing hoverboard firmware.
