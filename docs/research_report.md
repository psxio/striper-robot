# Deep Research Report: Striper Robot — Competitive Analysis & Architecture Recommendations

## Executive Summary

After researching every commercial competitor, open-source project, hardware alternative, positioning technology, and cutting-edge innovation in this space, the conclusion is clear:

**The current codebase is massively overengineered.** The robot's job is: read GPS, steer toward next waypoint, toggle a solenoid. The current implementation deploys 16+ ROS2 nodes, a dual EKF localization pipeline, the full Nav2 stack, 5 safety sub-nodes, a custom FastAPI+SQLite+WebSocket dashboard, custom messages/services/actions, and a URDF model. This is the architecture of a hospital delivery robot — not a paint robot driving straight lines in an empty parking lot.

### The Two Viable Paths Forward

| | **Path A: ArduRover** | **Path B: Bare Python** |
|---|---|---|
| Custom code needed | ~30 lines Lua | ~500 lines Python |
| Runtime processes | 1 (autopilot firmware) | 1 (Python script) |
| Dependencies | ArduPilot firmware | pyserial, math |
| Field debugging | Mission Planner (mature) | print statements (simple) |
| Dashboard | Mission Planner / QGC (free, built-in) | None needed for V1 |
| GPS waypoint following | Built-in | ~100 lines PID controller |
| Paint spray control | Built-in `AC_Sprayer` library | ~20 lines distance check |
| Geofencing | Built-in | ~30 lines ray casting |
| E-stop | Built-in RC/GCS failsafe | ~10 lines GPIO check |
| Hardware cost delta | +$100-250 (Pixhawk), -$80 (no RPi) | Same as current |

**Recommendation: ArduRover.** It is battle-tested firmware on thousands of rovers with every feature we need built in. Our `striper_pathgen` library (templates, coordinate transforms, DXF/SVG import) remains valuable for generating Mission Planner waypoint files. Everything else in `striper_ws/` and `dashboard/` can be shelved.

---

## Competitive Landscape

### No Open-Source Line Marking Robot Exists

Despite extensive searching of GitHub, Hackaday, ROS Discourse, Reddit, and Instructables, **there is no dedicated open-source line marking/painting robot project.** The closest platforms are:
1. **OpenMower** — RTK GPS autonomous mower (~$1,050 build)
2. **ArduPilot Rover** — proven RTK GPS waypoint following
3. **HoverMower** — hoverboard motors + GPS navigation

### Commercial Products (All $10K-$61K+)

| Company | Price | Base Station? | Annual Fee | Key Tech |
|---------|-------|--------------|------------|----------|
| **Turf Tank Two** | ~$61,000 | Yes (included) | $6K-16K/yr | RTK GNSS, skid-steer, low-pressure spray |
| **TinyMobileRobots Pro X** | ~$30-40K est. | No (network RTK) | Template fees | Network NTRIP, tri-wheel, STIHL partnership |
| **SWOZI auto** | Quote-based | Optional | RTK sub | Fastest (7 km/h), any paint brand, Swiss |
| **SWOZI Pico** | ~$11,000 | Optional | Included 1yr | Entry-level semi-auto |
| **FJD PaintMaster** | ~$160/wk rent | Yes | None | Dual GNSS receivers, Chinese mfg, no subscription |
| **Fleet Robot** | ~$19,000 | Yes (included) | ~$1,600/yr | Cheapest full robot, UK/NZ |
| **CivDot Mini** | Quote-based | Yes or NTRIP | — | Construction layout + striping |
| **10Lines** | Pre-commercial | — | — | Parking lot specialist, Estonia, EUR 1.5M funded |

### Key Insights from Competitors

1. **Every commercial product uses RTK GNSS** as primary positioning. No LiDAR, no 3D cameras, no SLAM.
2. **All robots are differential drive or skid-steer.** Nobody uses Ackermann steering.
3. **Paint systems are uniformly low-pressure spray nozzles** with solenoid on/off control.
4. **Path following is simple waypoint-based.** Templates → GPS waypoints → pure pursuit or similar controller.
5. **The base station problem is the #1 customer complaint.** Network RTK (NTRIP) eliminates this.
6. **The parking lot market is wide open.** Sports fields have 6+ competitors. Parking lots have almost zero commercial solutions available today.
7. **Nobody runs ROS2.** Commercial robots use embedded firmware or proprietary stacks.

---

## Hardware: The Hoverboard Hack ($30 vs $200+)

The single biggest cost saving is using **salvaged hoverboard motors + the hoverboard-firmware-hack-FOC project.**

A used hoverboard ($20-50) from eBay/Facebook Marketplace gives you:
- Two 350W BLDC hub motors with built-in hall sensors
- A 36V battery pack (2-4Ah)
- An STM32-based dual motor controller board
- The [hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC) firmware replaces stock balancing firmware with Field Oriented Control that accepts UART speed commands

**Proven in dozens of robot projects:** HoverMower, ESP32-Hoverboard-Lawnmower, HoverBot, CHEAP-LAWNMOWER-ROBOT-FROM-HOVERBOARD.

**This eliminates:**
- Custom DC motors (~$60-80)
- Encoders (~$20-30)
- Motor driver board / ESP32 PID controller (~$25-80)
- Potentially the battery (~$290 for LiFePO4)

**What you need to flash it:**
- ST-Link V2 programmer: $6
- Total: $26-56

### Motor Controller Comparison (if NOT using hoverboard)

| Controller | Price | Built-in Encoder + PID? | Can Replace ESP32? |
|-----------|-------|------------------------|-------------------|
| Cytron MDD10A | $19 | No | No |
| RoboClaw 2x7A | $80 | Yes (auto-tune PID) | Yes |
| RoboClaw 2x15A | $120 | Yes | Yes |
| VESC (Flipsky) | $60-85 | Yes (FOC, single channel) | Partially |
| ODrive S1 | $150-250 | Yes (FOC, dual channel) | Yes |

**RoboClaw can completely replace the ESP32** — it has built-in encoder inputs, PID auto-tuning, and accepts serial commands directly from the RPi or Pixhawk.

---

## Positioning: UM980 Replaces ZED-F9P (Saves $125-175)

### RTK GPS Module Comparison

| Module | Price (on board) | Accuracy | Bands | Key Advantage |
|--------|-----------------|----------|-------|---------------|
| **Quectel LC29HEA** | ~$58 | 1-2cm RTK | L1/L5 | Cheapest RTK on Earth |
| **Unicore UM980** | ~$120-150 | **8mm RTK** | L1/L2/L5 | Best accuracy per dollar |
| **Unicore UM982** | ~$150-200 | 8mm RTK | L1/L2/L5 | Dual-antenna heading (no IMU needed) |
| **u-blox ZED-F9P** | ~$212-275 | 1-2cm RTK | L1/L2 | Most documented, largest community |
| **u-blox ZED-F9R** | ~$250-350 | 1-2cm RTK | L1/L2 | Built-in IMU + dead reckoning |
| **u-blox ZED-X20P** | TBD (new) | 1-2cm RTK | All-band | Eliminates base station via PointPerfect Live |

### Recommendation: UM980

The **Unicore UM980** at ~$120-150 gives **8mm RTK accuracy** — better than the ZED-F9P at half the price. It is well-validated in the precision agriculture community (AgOpenGPS). ArduPilot has native support.

**Skip the BNO085 IMU.** In an open parking lot with 10-20 Hz RTK, you do not need an IMU. Use heading-from-motion. If you need standstill heading, drive forward 20cm to establish GPS heading, or add a $10 LSM6DSV later.

### RTK Correction Sources

| Source | Cost | Coverage | Best For |
|--------|------|----------|----------|
| **Own base station** (2nd UM980/LC29H) | $60-150 one-time | Where you put it | Reliability, no subscription |
| **RTK2Go** | Free | 800+ stations, variable | Testing, demos |
| **Point One Polaris** | $50/month | USA, Canada, EU, Australia | Business with multiple job sites |
| **PointPerfect Live** (u-blox) | Usage-based | USA, EU | If using ZED-X20P |

**Best option for startup:** Own base station ($60-150) + RTK2Go (free). If jobs are spread across a metro area, add Point One Polaris at $50/month.

---

## Software: What to Keep, What to Kill

### KEEP (genuinely valuable)

| Component | Why |
|-----------|-----|
| `striper_pathgen/models.py` | Core data types, used everywhere |
| `striper_pathgen/template_generator.py` | Parking space templates, arrow, crosswalk |
| `striper_pathgen/dxf_importer.py` | DXF file import |
| `striper_pathgen/svg_importer.py` | SVG file import |
| `striper_pathgen/path_optimizer.py` | Nearest-neighbor + 2-opt segment ordering |
| `striper_pathgen/coordinate_transform.py` | GPS ↔ local meters conversion |
| `striper_pathgen/ros_converter.py` | Convert paths to waypoint format |
| `striper_pathgen/job_exporter.py` | GeoJSON, KML, CSV export |
| `scripts/pathgen_cli.py` | CLI for generating jobs |
| `firmware/esp32_motor_controller/` | Keep IF not using hoverboard or ArduRover |

### KILL (overengineered)

| Component | Replaced By |
|-----------|------------|
| All 16 ROS2 nodes | ArduRover firmware (or ~500 lines Python) |
| Nav2 + RegulatedPurePursuit | ArduRover's built-in path following |
| Dual EKF (robot_localization) | RTK GPS position read directly |
| Safety supervisor + 5 sub-nodes | ArduRover built-in failsafes + geofencing |
| Custom FastAPI dashboard | Mission Planner / QGroundControl |
| WebSocket ROS bridge | MAVLink telemetry (built into ArduPilot) |
| SQLite job store | Mission Planner waypoint files |
| Frontend (HTML/JS/Leaflet) | Mission Planner map view |
| URDF model | ArduPilot frame configuration |
| striper_msgs (11 custom messages) | MAVLink standard messages |

### The ArduPilot Sprayer Function

ArduPilot's `AC_Sprayer` library automatically controls pump output proportional to vehicle speed. Parameters:
- `SPRAY_PUMP_RATE` — flow rate at 1 m/s
- `SPRAY_PUMP_MIN` — minimum pump speed
- `SPRAY_SPEED_MIN` — speed below which spray turns off

This replaces three ROS2 nodes (`paint_controller_node`, `speed_regulator_node`, `paint_valve_node`) with configuration parameters.

For more complex paint logic (on/off at specific path positions), a **30-line Lua script** handles everything:
```lua
-- Paint control Lua script for ArduRover
local RELAY_PAINT = 0
local spray_active = false

function update()
    local mode = vehicle:get_mode()
    if mode ~= 10 then  -- Not in AUTO mode
        relay:off(RELAY_PAINT)
        spray_active = false
        return update, 50
    end

    local cmd = mission:get_current_nav_cmd()
    if cmd and cmd:id() == 181 then  -- MAV_CMD_DO_SET_RELAY
        if cmd:param2() == 1 then
            relay:on(RELAY_PAINT)
        else
            relay:off(RELAY_PAINT)
        end
    end
    return update, 50  -- Run at 20Hz
end

return update, 1000
```

---

## Revised BOM: Three Tiers

### Tier 1: $409 "Proof of Concept"

| Component | Source | Cost |
|-----------|--------|------|
| Used hoverboard (motors + battery + controller) | eBay/FB Marketplace | $30 |
| ST-Link V2 programmer | Amazon | $6 |
| 3/4" plywood platform + casters | Home Depot | $25 |
| ESP32-S3 dev board (custom firmware) | Amazon | $8 |
| simpleRTK2B Budget (ZED-F9P) + antenna | ArduSimple | $252 |
| 12V diaphragm pump + solenoid + nozzle | Amazon | $60 |
| Hoverboard battery + DC-DC converters | Included + Amazon | $10 |
| E-stop button + relay | Amazon | $5 |
| Wiring, connectors, fuses | Amazon | $13 |
| **TOTAL** | | **~$409** |

### Tier 2: $631 "Best Value" (Recommended)

> **NOTE:** This was the original estimate. After deep hardware research,
> the Tier 2 BOM has been revised to **~$780**. See `docs/bom.md` for
> the corrected BOM with Shurflo pump, PM06 V2, DC contactor, etc.

| Component | Source | Cost |
|-----------|--------|------|
| Used hoverboard (motors + battery + controller) | eBay/FB Marketplace | $30 |
| ST-Link V2 | Amazon | $6 |
| 2020 aluminum extrusion + plywood deck | Amazon/Home Depot | $50 |
| **Pixhawk 6C Mini** (ArduRover) | Holybro | $120 |
| UM980 breakout + antenna | ArduSimple/SparkFun | $165 |
| 12V diaphragm pump + solenoid + nozzle + fittings | Amazon | $80 |
| 36V 10Ah e-bike battery | Amazon | $100 |
| DC-DC converters (36V→12V, 36V→5V) | Amazon | $10 |
| E-stop + 2x HC-SR04 ultrasonics | Amazon | $10 |
| RC transmitter/receiver (for manual override) | Amazon | $30 |
| Wiring/misc | Amazon | $30 |
| **TOTAL** | | **~$631** |

### Tier 3: $850 "Production Prototype"

| Component | Source | Cost |
|-----------|--------|------|
| Used hoverboard + upgraded 36V battery | eBay + Amazon | $80 |
| 2020 aluminum frame, proper casters, paint tray | Amazon | $80 |
| Pixhawk 6C (full size) | Holybro | $180 |
| UM980 breakout + quality multiband antenna | ArduSimple | $190 |
| 12V diaphragm pump + solenoid + Graco-style tip + filter | Amazon/Ag supply | $100 |
| 36V 15Ah e-bike battery + charger | Amazon | $140 |
| DC-DC converters + fuse panel | Amazon | $20 |
| E-stop + bumper switches + 2x ultrasonics | Amazon | $15 |
| RC transmitter/receiver (FlySky FS-i6X) | Amazon | $50 |
| Weatherproof enclosure for electronics | Amazon | $20 |
| Wiring, connectors, mounting hardware | Amazon | $30 |
| **TOTAL** | | **~$905** |

**vs. Original BOM: $1,100-1,350. Savings: $200-740.**

---

## Cutting-Edge Tech Worth Adopting

### Adopt Now

| Technology | What It Does | Why |
|-----------|-------------|-----|
| **ArduRover + AC_Sprayer** | Replaces entire ROS2 stack | Battle-tested, 30 lines of Lua vs 16 nodes |
| **Hoverboard FOC firmware** | Replaces custom motor driver | Proven in dozens of robots, $30 total |
| **UM980 RTK module** | Better GPS at half the price | 8mm accuracy, triple-band, ArduPilot native |
| **Mission Planner / QGC** | Replaces custom dashboard | Free, mature, mobile-ready |
| **Foxglove Studio** | Dev-time monitoring/debugging | Better than RViz for field work |

### Adopt in V2

| Technology | What It Does | Why Wait |
|-----------|-------------|----------|
| **Downward camera + OpenCV** | Line-following for restriping | High value for repaint jobs, $25 camera |
| **Drone + SAM2/YOLO pipeline** | Auto-detect existing lines from aerial photos | Auto-generate repaint waypoints from photos |
| **Zenoh RMW** | Simpler networking if we keep ROS2 | Only relevant if we don't go ArduRover |
| **Photoluminescent paint option** | Glow-in-dark lines, premium upsell | Differentiation, higher margin per job |
| **LoRa telemetry** | Backup monitoring across large lots | $5-15 module, nice-to-have |

### Ignore (Not Ready / Not Relevant)

| Technology | Why Skip |
|-----------|---------|
| LiDAR / 3D cameras | Flat surface, GPS waypoints. Not a SLAM robot. |
| Xona LEO satellites | Not until 2027+ |
| 5G positioning | Not deployable until 2028-2030 |
| Starlink positioning | Pure research, not a product |
| UWB anchors | Per-site infrastructure, impractical for service business |
| VIO / Visual SLAM | Too much drift, too much compute |
| Sodium-ion batteries | Not yet cheaper at pack level |
| WiBotic wireless charging | $3K-5K, only for 24/7 autonomous operation |
| NVIDIA Isaac ROS | Overkill — needs Jetson, solves problems we don't have |
| AWS RoboMaker | Dead (EOL September 2025) |

---

## Paint System

All competitors use the same approach we planned: **low-pressure diaphragm pump + solenoid valve + flat fan nozzle.** This is correct.

- **Paint type:** Water-based latex traffic paint (~$15-25/gallon, ~350 linear feet/gallon)
- **Nozzle:** TeeJet TP8004EVS (even spray) or Graco RAC 5 LL5319 for 4" line width ($5-15)
- **A 50-space lot needs ~4-5 gallons of paint ($60-100) and takes 30-60 minutes**
- **Spray paint can + servo** works for demos ($15) but is 10-20x more expensive per foot for production
- **Thermoplastic marking** (3-5 year lifespan vs 6-12 months for paint) is a V2 opportunity but requires heated applicator

---

## Business Model Notes

- **Parking lot striping market is wide open** — almost zero commercial autonomous solutions
- **Sports field market is crowded** — 6+ well-funded competitors (Turf Tank, TinyMobileRobots, SWOZI, FJD, Fleet, CivDot)
- **RaaS (Robot-as-a-Service)** is the dominant model: $2K-5K/month recurring vs $50K+ robot sale
- **10Lines** (Estonia, EUR 1.5M funded) is the only direct competitor targeting parking lots, but is pre-commercial (launching 2026)
- **CivDot** (USA, $12.5M funded) does construction layout + some striping
- **The #1 customer complaint** across all competitors is base station setup. Eliminating the base station (via network RTK/NTRIP) is a major selling point.
- **GPS multipath near buildings** is the unsolved technical challenge for parking lots specifically

---

## Recommended Architecture: ArduRover + pathgen

```
┌─────────────────────────────────────────────────┐
│                  OPERATOR SIDE                    │
│                                                   │
│  striper_pathgen (Python, runs on laptop)         │
│  ├── template_generator.py  → parking templates   │
│  ├── dxf_importer.py        → import CAD files    │
│  ├── path_optimizer.py      → optimize order      │
│  └── job_exporter.py        → export waypoints    │
│           ↓                                       │
│  Mission Planner / QGroundControl                 │
│  ├── Load waypoint file                           │
│  ├── Add DO_SET_RELAY commands for paint           │
│  ├── Upload mission to Pixhawk via USB/telemetry  │
│  └── Monitor live telemetry + map                 │
└───────────────────────┬─────────────────────────┘
                        │ MAVLink (WiFi/telemetry radio)
                        ↓
┌─────────────────────────────────────────────────┐
│                   ROBOT SIDE                      │
│                                                   │
│  Pixhawk 6C running ArduRover                     │
│  ├── GPS waypoint following (built-in)            │
│  ├── AC_Sprayer pump control (built-in)           │
│  ├── DO_SET_RELAY for solenoid (built-in)         │
│  ├── Geofencing (built-in)                        │
│  ├── RC failsafe / E-stop (built-in)             │
│  ├── Lua script (~30 lines) for paint logic       │
│  └── MAVLink telemetry to ground station          │
│           ↓ UART                                  │
│  Hoverboard mainboard (FOC firmware)              │
│  ├── Left motor speed control                     │
│  └── Right motor speed control                    │
│           ↓ GPIO/relay                            │
│  Paint system                                     │
│  ├── 12V diaphragm pump                           │
│  └── 12V solenoid valve → nozzle                  │
└─────────────────────────────────────────────────┘
```

**Total custom code: ~30 lines Lua + pathgen library (already written).**
**Total BOM: $631-905 vs $1,100-1,350 original.**
**Time to field-ready: days, not months.**

---

## What Happens to the Existing Codebase

| Package | Decision | Reason |
|---------|----------|--------|
| `striper_pathgen/` | **KEEP** | Core value — generates waypoint files for Mission Planner |
| `firmware/esp32_motor_controller/` | **KILL** | Hoverboard FOC firmware replaces this |
| `striper_ws/src/striper_msgs/` | **KILL** | ArduPilot uses MAVLink |
| `striper_ws/src/striper_description/` | **KILL** | ArduPilot uses frame params |
| `striper_ws/src/striper_bringup/` | **KILL** | No ROS2 launch needed |
| `striper_ws/src/striper_navigation/` | **KILL** | ArduRover handles navigation |
| `striper_ws/src/striper_localization/` | **KILL** | RTK GPS direct, no EKF |
| `striper_ws/src/striper_hardware/` | **KILL** | Pixhawk handles all hardware |
| `striper_ws/src/striper_safety/` | **KILL** | ArduRover built-in failsafes |
| `striper_ws/src/striper_simulation/` | **KILL** | Use SITL (ArduPilot's built-in simulator) |
| `dashboard/` | **KILL** | Mission Planner / QGC replaces this |
| `scripts/pathgen_cli.py` | **KEEP** | CLI for job generation |
| `docs/bom.md` | **UPDATE** | New BOM |
| `docs/wiring_guide.md` | **UPDATE** | Simplified wiring |
| `docs/topic_map.md` | **KILL** | No ROS2 topics |

---

## Market Opportunity: Parking Lot Striping Is Wide Open

### Direct Competition (Parking Lots)

| Competitor | Status | Funding | Target | Threat Level |
|-----------|--------|---------|--------|-------------|
| **10Lines** (Estonia) | Pre-commercial, full launch expected 2026 | EUR 2.2M total (EUR 700K seed 2021, EUR 1.5M 2024 led by Tera Ventures/Karista) | Parking lots, road markings | Medium — ESA-backed tech, software already used by 300+ companies, but hasn't shipped hardware yet |
| **CivDot** (USA) | Commercial, expanding | $12.5M total ($7.5M Series A July 2025, Trimble + Converge) | Construction layout, some striping | Low-Medium — primarily construction, striping is secondary feature |
| **Tyker/BauMotor** (Netherlands) | Commercial | Unknown | Road pre-marking, parking | Low — expensive, focused on roads/municipalities |

**That's it.** Three companies, and only 10Lines is directly targeting parking lot striping — and they haven't shipped a robot yet.

### The Sports Field Market Is Saturated (Don't Go Here)

| Competitor | Price | Deployed | Funding/Backing |
|-----------|-------|----------|----------------|
| **Turf Tank** (Denmark) | ~$61,000 + $6-16K/yr subscription | 1,500+ robots, 5,000+ clients, 2 NFL stadiums | Tens of millions in revenue |
| **TinyMobileRobots** (Denmark) | ~$30-40K est. + template fees | 2M+ fields marked, 35+ countries | $14.4M Series A + STIHL acquired 23.8% stake |
| **SWOZI** (Switzerland) | $11K-$40K+ | Active globally | Unknown |
| **FJD Dynamics** (China) | ~$160/wk rent-to-own | Growing | Large agtech parent company |
| **Fleet Line Markers** (UK/NZ) | ~$19,000 + $1,600/yr | Launched 2024 | 70-year old line marking company |
| **Traqnology** (Norway/US) | Quote-based | Active | NovAtel partnership |

6+ well-funded competitors in sports fields. Red ocean.

### Market Size

- **Global line-marking robot market:** $322.92M (2025) → $454.42M by 2035 (3.5% CAGR)
- **GPS line-marking robot market:** projected $1.2B by 2028 (14.3% CAGR)
- **Architecture/construction marking segment:** ~40% of market (~$129M)
- **Sports/stadium automation segment:** grown 32%

### Why Parking Lots Are Underserved

1. **GPS multipath near buildings** — satellite signals bounce off walls, reducing accuracy. Sports fields are open sky. Parking lots have buildings, light poles, trees nearby. RTK still works but needs better antennas/receivers (UM980's triple-band helps here).

2. **More obstacles** — parked cars, curbs, speed bumps, pedestrians, light poles. Sports fields are flat open grass.

3. **Surface differences** — asphalt/concrete vs grass. Paint adhesion, drying time, and durability requirements differ.

4. **Fragmented customer base** — one sports complex might have 20 fields. Parking lots are one-off jobs at hundreds of different properties.

5. **Sports field companies got funded first** — the use case is simpler, the customers (universities, cities) have bigger budgets, and the demo is more impressive (painting a football field in 30 minutes).

### Our Competitive Advantages

| Advantage | Detail |
|-----------|--------|
| **Price** | Sub-$1K robot vs $19K-61K commercial products |
| **No subscription** | One-time build cost vs $6K-16K/year fees |
| **Open architecture** | ArduPilot is open source, hackable, community-supported |
| **Parking lot focus** | Purpose-built for asphalt, not retrofitted from sports |
| **Network RTK** | No base station setup (competitors' #1 complaint) |
| **First mover (US)** | 10Lines is in Estonia and hasn't shipped. CivDot is construction-first. |
| **Path from DXF/SVG** | Import AutoCAD site plans directly (property managers already have these) |

### What Customers Actually Care About (From Reviews/Forums)

1. **Time savings** — #1 factor. Going from 3-4 days with a crew to an afternoon with one person.
2. **Paint savings** — 50%+ reduction. Precise spray = less waste.
3. **Consistency/repeatability** — same lot, same lines, every time. No human error.
4. **One-person operation** — labor cost reduction is the real ROI driver.
5. **No base station hassle** — biggest operational complaint across all competitors.

### Revenue Model

- **Per-job pricing:** $500-2K per parking lot (matching manual pricing but faster)
- **Robot pays for itself in 2-3 jobs** at a $631 build cost
- **RaaS potential:** $2K-5K/month recurring revenue per robot deployed
- **Consumables:** ~$60-100 in paint per 50-space lot ($15-25/gallon, 4-5 gallons needed)

---

## Sources

### Commercial Products
- [Turf Tank](https://turftank.com/us/turf-tank-two/)
- [TinyMobileRobots](https://tinymobilerobots.us/robots/tinylinemarker-pro-x)
- [SWOZI](https://swozi.com/auto/)
- [FJD PaintMaster](https://www.fjdynamics.com/product/fjd-rlm01-robotic-line-marker)
- [Fleet Line Markers](https://fleetlinemarkers.co.uk/products/line-marking-robot)
- [CivDot](https://www.civrobotics.com/)
- [10Lines](https://10linesrobots.com/striping-robots)
- [Tyker/BauMotor](https://baumotor.com/robot_plotter)
- [Traqnology](https://traqnology.com/)
- [RoadPrintz](https://roadprintz.com/)

### Open Source
- [OpenMower](https://github.com/ClemensElflein/OpenMower)
- [hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC)
- [HoverMower](https://hovermower.github.io/)
- [ArduPilot Rover](https://ardupilot.org/rover/)
- [ArduPilot Sprayer Function](https://ardupilot.org/copter/docs/sprayer.html)
- [ArduPilot Lua Scripts](https://ardupilot.org/rover/docs/common-lua-scripts.html)

### Positioning
- [Unicore UM980](https://en.unicore.com/products/surveying-grade-gnss-um980/)
- [Quectel LC29HEA RTK for <$60](https://rtklibexplorer.wordpress.com/2024/04/28/dual-frequency-rtk-for-less-than-60-with-the-quectel-lc29hea/)
- [ArduSimple simpleRTK2B Budget](https://www.ardusimple.com/product/simplertk2b/)
- [Point One Polaris](https://pointonenav.com/rtk-network-ntrip/)
- [RTK2Go Free NTRIP](http://rtk2go.com/)
- [u-blox ZED-X20P](https://www.u-blox.com/en/zed-x20p)

### Hardware
- [Graco LineLazer Tips](https://www.portlandcompressor.com/stripers/linelazer-tips)
- [Traffic Paint Guide](https://www.asphaltsealcoatingdirect.com/info/which-road-paint-should-you-buy)
- [RoboClaw Motor Controller](https://resources.basicmicro.com/esp32-roboclaw-motor-control/)
- [WiBotic Wireless Charging](https://www.wibotic.com/)

### Cutting Edge
- [Foxglove Studio](https://foxglove.dev/)
- [Xona Space Systems](https://www.xonaspace.com/)
- [SAM 2 (Meta)](https://ai.meta.com/sam2/)
- [AirWorks AI](https://www.airworks.io/)
- [LuminoKrom Glow Paint](https://www.luminokrom.com/en/)
- [Zenoh for ROS2](https://docs.ros.org/en/jazzy/Installation/RMW-Implementations/Non-DDS-Implementations/Working-with-Zenoh.html)
