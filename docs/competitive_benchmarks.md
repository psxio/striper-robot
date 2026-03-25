# Competitive Benchmarks & Accuracy Research

*Compiled March 2026 from manufacturer specs, forum reports, and academic papers.*

> For actual purchases, use [approved_sku_sheet.md](approved_sku_sheet.md) or [buying_guide.md](buying_guide.md).
> This document is a benchmarking and risk-analysis reference, not the canonical shopping list.

---

## 1. Industry Accuracy Standard Summary

| System | Claimed Accuracy | GPS Type | Speed | Notes |
|--------|-----------------|----------|-------|-------|
| **Turf Tank Two** | +/- 1 cm (+/- 0.3 in) | RTK-GNSS (GPS+GLONASS), local base station | Soccer field in <24 min | Proprietary RTK; base station required |
| **TinyMobileRobots Pro X** | 1-2 cm (~0.8 in) | Network RTK corrected GNSS | 4 kph (1.1 m/s) | Network RTK = no base station |
| **SWOZI Auto** | Sub-inch / sub-centimeter (claimed) | RTK GNSS + optional laser tracker | Up to 7 kph (4.5 mph) | Laser fallback for GPS-denied areas |
| **FJD PaintMaster Pro** | cm-level (GNSS), mm-level (with laser kit) | Dual GNSS + local base station; CORS support | Not published | Laser kit for under trees/stands |
| **10Lines (Estonia)** | 1-2 cm | Satellite positioning + other sensors | 7x faster than manual | Parking lot specialist; tested in Tallinn |
| **CivDash (Civ Robotics)** | 3 cm | Trimble R780 GNSS; VRS/RTX corrections | 16 miles/day of lines | Road striping; 25 lbs; remote operated |
| **Tyker Robot Plotter** | "pinpoint" (not quantified) | RTK-GNSS or Total Station | 12-16x faster than manual crew | Road pre-marking; Netherlands |
| **HP SitePrint** | +/- 2 mm | Total Station (not GNSS) | Indoor only | Floor layout printing; $$$; not outdoor |
| **Husqvarna EPOS** | 2 cm (local base) / 1-6 cm (cloud) | RTK-GNSS | Mowing speed | Consumer robot mower reference |
| **Striper (ours)** | Target: 2 cm | Holybro H-RTK UM982 dual-antenna GNSS | 0.5-1.0 m/s target | 8 mm RTK-class position with dual-antenna heading at standstill |

### Key Takeaway
**The industry consensus for GNSS-based outdoor line marking is +/- 1-2 cm accuracy.** This is the bar. No commercial system claims better than 1 cm outdoors with GNSS alone. Systems achieving mm-level use total stations or laser kits (not pure GNSS).

---

## 2. Competitor Deep Dives

### 2.1 TinyMobileRobots

- **Products**: TinyLineMarker Pro X (large), TinyLineMarker Sport (compact)
- **GPS**: Network RTK corrected GNSS receiver (no local base station needed)
- **Accuracy**: 1-2 cm consistently; "0.8-inch precision even in challenging conditions"
- **Speed**: Pro X marks at 4 kph (1.1 m/s); Sport marks at 1.6 mph (~2.6 kph)
- **Performance**: Pro X paints a regulation football field in ~3 hours; Sport does a soccer field in ~20 min
- **Business model**: Robot-as-a-Service (subscription); Danish company; $5,000-15,000/yr estimated
- **Strengths**: Network RTK eliminates base station setup (#1 customer pain point)
- **Weaknesses**: Sports fields only; no parking lot product

### 2.2 Turf Tank

- **Products**: Turf Tank Two (flagship), Turf Tank One (legacy), Turf Tank Lite (budget)
- **GPS**: RTK-GNSS (GPS + GLONASS), proprietary/patented technology, local base station
- **Accuracy**: +/- 0.3 inches (+/- ~8 mm) per marketing; +/- 1 cm per technical docs
- **Speed**: Soccer field <24 min; football field <3.5 hrs; baseball <11 min
- **Dimensions**: 109 x 83 x 75 cm, 55.7 kg without paint/battery
- **Paint**: 5.5 gallon capacity; 50%+ paint reduction vs manual
- **Business model**: RaaS subscription; largest market share in sports fields
- **Strengths**: Mature product, large install base, good software
- **Weaknesses**: Requires base station setup; sports fields only; expensive subscription

### 2.3 SWOZI

- **Products**: SWOZI Auto (autonomous), SWOZI Pro (semi-auto), SWOZI Ride-on, SWOZI Evo (manual)
- **GPS**: RTK GNSS; optional laser tracker for GPS-denied environments
- **Accuracy**: "Sub-inch/centimeter GPS line marking precision"
- **Speed**: Up to 7 kph (~4.5 mph); claims 75% time savings
- **Paint**: 30 kg capacity
- **Battery**: 12V/48Ah; dual batteries = ~4 hours runtime
- **Strengths**: Most versatile (4 operating modes); laser fallback for stadiums/tree lines
- **Weaknesses**: Less market presence than Turf Tank/TinyMobileRobots

### 2.4 FJD PaintMaster Pro

- **Products**: PaintMaster Pro (RLM01), PaintMaster Mini (RLM02)
- **GPS**: Dual industrial-grade GNSS positioning + local base station; CORS RTK support
- **Accuracy**: cm-level with GNSS; mm-level with optional laser kit
- **Strengths**: Chinese manufacturer = lower price point; laser fallback
- **Weaknesses**: Newer to market; less brand recognition in US

### 2.5 10Lines (Estonia) -- Direct Parking Lot Competitor

- **Founded**: 2019 by Tarmo Prints (parking lot marking veteran) and Janno Paas (startup CTO)
- **Funding**: EUR 700K seed (2021, Tera Ventures + Perot Jain) + EUR 1.5M (2024-2025, Tera + Karista + Butterfly Ventures)
- **GPS**: Satellite positioning + additional sensors; 1-2 cm accuracy
- **Capability**: 7x faster than manual; eliminates pre-marking (70% of traditional time)
- **Status**: Small-series production; testing in Tallinn car parks; expanding to US market
- **Differentiator**: Only funded startup specifically targeting parking lot marking
- **Risk to us**: They have real funding, a veteran co-founder from the industry, and are actively entering the US market. But they are still pre-scale and their robots are not yet widely available.

### 2.6 CivDash (Civ Robotics)

- **Focus**: Road striping (highways, parking lots, airports)
- **GPS**: Compatible with Trimble R780; connects to VRS/RTX corrections
- **Accuracy**: 3 cm claimed
- **Performance**: 16 miles of lines per day; 8 hours battery
- **Weight**: 25 lbs
- **Differentiator**: Road-grade striping (thermoplastic capable); worker safety (100 ft remote operation)

---

## 3. Academic Research: Achieved Accuracy in Field Tests

### 3.1 Road Marking Robot (Robotica, Cambridge Core)
- **Paper**: "Development of an Autonomous Robotics Platform for Road Marks Painting Using Laser Simulator and Sensor Fusion Technique"
- **System**: WiFi camera + laser range finder + odometry; A* + DWA path planning; ROS
- **Achieved accuracy**: **+/- 10 cm** (100 mm)
- **Takeaway**: Without RTK GNSS, using only cameras/LIDAR/odometry, accuracy is an order of magnitude worse. This validates the RTK approach.

### 3.2 Precision Floor Marking Robot (MDPI Robotics, 2025)
- **Paper**: "Development of an Autonomous Robot for Precision Floor Marking"
- **System**: Wheeled robot with pen plotter; encoder-based positioning; low-cost components
- **Achieved accuracy**: 1.6 mm std dev (forward), 3 mm std dev (lateral)
- **Takeaway**: Encoder-only works well indoors over short distances. Irrelevant for outdoor parking lots where GPS drift and terrain matter.

### 3.3 HP SitePrint (Commercial, Indoor)
- **System**: Total station + robotic printer
- **Achieved accuracy**: +/- 2 mm (with high-accuracy mode, total station, at 5-30m range)
- **Takeaway**: Total station achieves mm-level, but requires line-of-sight, indoor use, and costs $50K+. Not applicable to parking lots.

### 3.4 General RTK Field Accuracy (Multiple Sources)
- **Theoretical RTK position accuracy**: 8 mm + 1 ppm horizontal, 15 mm + 1 ppm vertical
- **UM982 / UM980 RTK class spec**: 8 mm horizontal, 15 mm vertical (RTK fixed)
- **Practical outdoor**: 1-2 cm in open sky, degrading near buildings
- **The gap**: Position accuracy != path following accuracy. The controller, steering, speed, terrain all add error on top of GPS error.

---

## 4. ArduRover Real-World Accuracy

### 4.1 Position Accuracy vs. Path Following Accuracy

This is the critical distinction. RTK gives you 1-2 cm **position knowledge**, but the rover's ability to **follow a line** depends on:
1. GPS update rate (typically 5-20 Hz)
2. L1 controller tuning (NAVL1_PERIOD, NAVL1_DAMPING)
3. Vehicle speed (slower = more corrections per meter = tighter tracking)
4. Steering response (mechanical slop, turning radius)
5. Terrain (bumps, slopes, surface friction)

### 4.2 Reported Cross-Track Errors

| Source | Setup | Cross-Track Error | Notes |
|--------|-------|-------------------|-------|
| DIYRobocars blog | Pixhawk 4 + Reach RTK M+ | 10-50 cm typical | RTK float; "good signal" gets cm-level position but path following lagged |
| ArduPilot forum user | RTK + tractor | +/- 19-20 cm | RTK float on 150-yard run at 1.3 m/s |
| ArduPilot forum user | RTK + rover, WP_RADIUS=0.4 | Looping/oscillation at <40 cm | System struggled to converge below 40 cm WP_RADIUS |
| The Mower Project | RTK fixed + ArduRover mower | ~10 cm drift over 20 loops | "Path drifted approximately 4 inches over 20 loops" |
| ArduPilot SITL | Simulated | ~1-2 m off in some stretches | Known L1 controller convergence issues |

### 4.3 Key Tuning Parameters

- **NAVL1_PERIOD**: Controls steering aggressiveness. Lower = more responsive but can oscillate. Default 8, try 2-4 for precision.
- **NAVL1_DAMPING**: Default 0.75. Increase to 1.0 for smoother convergence.
- **WP_RADIUS**: Minimum practical value ~0.4m with RTK. Below this, rover oscillates trying to hit the exact point.
- **WP_SPEED**: **Slower is more accurate.** At 1 m/s with 10 Hz GPS, you get a correction every 10 cm. At 0.5 m/s, every 5 cm.
- **ATC_TURN_MAX_G**: Max lateral acceleration. Most ground rovers limited to ~0.3G.

### 4.4 Realistic Expectations for Our Robot

Given:
- UM982 position accuracy: ~8 mm RTK fixed
- Hoverboard differential drive: responsive steering, no mechanical slop in turns
- Target speed: 0.5-1.0 m/s (typical for paint robots)
- GPS update rate: 10 Hz in the checked-in baseline; higher rates are available if later tuning justifies them
- Open parking lot: good sky view, minimal multipath

**Realistic cross-track error: 2-5 cm** in the middle of a parking lot, degrading to **5-10 cm** near buildings due to multipath. This is competitive with commercial systems claiming 1-2 cm (which is position accuracy, not necessarily path-following accuracy).

---

## 5. GPS Multipath in Parking Lots

### 5.1 The Problem

Parking lots are surrounded by buildings, light poles, cars, and walls. GPS signals bounce off these surfaces and arrive at the receiver via multiple paths, causing:
- **Position errors**: Even with RTK fixed, multipath can add several cm of error
- **Fix loss**: Dropping from RTK fixed to float (accuracy degrades from 1-2 cm to 20-75 cm)
- **Cycle slips**: Sudden jumps in position when satellite tracking is interrupted

### 5.2 Quantified Impact

| Environment | RTK Accuracy | Notes |
|-------------|-------------|-------|
| Open field | 1-2 cm horizontal | Best case; high satellite count |
| Near single building | 2-5 cm | Partial sky blockage; some multipath |
| Between buildings | 5-15 cm | Reduced satellites; significant multipath |
| Urban canyon | Float only (20-75 cm) or no fix | Severe multipath and blockage |
| Under tree canopy | Float common (20-75 cm) | Foliage attenuates signals |

### 5.3 Mitigation Strategies

1. **Triband receiver (L1/L2/L5)**: the current UM982 baseline retains the triband advantage and better heading behavior than the old single-antenna path
2. **Ground plane**: 10+ cm metal ground plane under antenna reduces ground-bounce multipath
3. **Antenna placement**: Mount as high as practical; clear of metal obstructions
4. **NTRIP over base station**: Eliminates base station multipath as a variable
5. **IMU/odometry fusion**: ArduRover's EKF fuses GPS + IMU + wheel odometry for smoothing
6. **Operational constraint**: Mark from center outward; do building-adjacent lines last when fix is established
7. **Speed reduction near buildings**: Slower speed = more GPS samples per meter = better averaging

---

## 6. Vibration Effects on RTK GPS

### 6.1 Direct Effects

Motor vibration does **not** significantly degrade RTK position accuracy for ground robots. The reasons:
- GPS carrier phase measurements operate at ~1.5 GHz; mechanical vibration frequencies (10-500 Hz) are far below this
- The antenna is a passive receiver; vibration doesn't affect signal reception meaningfully
- RTK processing happens in firmware, not mechanically

### 6.2 Indirect Effects (Real Concerns)

- **Antenna cable fatigue**: Vibration can loosen SMA connectors over time, causing intermittent signal loss
- **Compass interference**: Hub motor magnets create magnetic fields that overwhelm the compass (we disable the compass and use UM982 dual-antenna GPS heading)
- **IMU noise**: High-frequency vibration feeds into accelerometer/gyro, degrading EKF state estimation
- **Structural flex**: If antenna is on a flexible mount, it moves relative to the robot body, adding position noise

### 6.3 Mitigation for Our Design

- **Rigid antenna mount**: Bolt directly to frame, not on a flex arm
- **Ground plane**: 12 cm+ aluminum disk under antenna
- **Vibration damping on Pixhawk**: Standard foam mounting isolates IMU from motor vibration
- **No compass**: Already planned; eliminates hub motor magnetic interference
- **Cable strain relief**: Secure antenna cable to prevent connector loosening

---

## 7. Parking Lot Striping Standards (For Reference)

- **Line width**: 4 inches standard per MUTCD
- **ADA accessible space**: 96 inches minimum width (measured to centerline of markings)
- **ADA access aisle**: 60 inches minimum
- **Van accessible**: 132 inches minimum (or 96 in + 96 in aisle)
- **Accuracy tolerance**: No formal standard exists for line placement accuracy in parking lots. The practical standard is "looks straight to the human eye" which is approximately +/- 2-3 inches (+/- 5-7 cm). Our 2-5 cm target far exceeds this practical requirement.

---

## 8. Conclusions for Striper Project

### We Are Competitive
- Our UM982 GNSS stack matches or exceeds what competitors use on raw RTK position while improving low-speed heading behavior
- Our target accuracy (2-5 cm path following) is within the same range as commercial sports field robots
- Parking lots have more forgiving accuracy requirements than sports fields (no FIFA certification needed)

### Our Advantages vs. 10Lines
- Open-source ArduRover firmware vs proprietary (faster iteration, community support)
- $1,027 research-backed BOM vs likely $5K+ for their hardware
- NTRIP eliminates base station (same as TinyMobileRobots' advantage)
- US-based development (they're expanding from Estonia)

### Known Risks
- **Multipath near buildings**: The #1 technical risk. Mitigation: triband GPS + operational procedures
- **ArduRover L1 controller precision**: May need custom tuning or even a modified controller for <5 cm tracking
- **Paint nozzle lag**: Solenoid on/off timing at 1 m/s means start/stop accuracy of ~2-5 cm (at 50ms response time). This may dominate overall line accuracy more than GPS does.
- **No formal benchmarks yet**: We need to build and test before claiming any accuracy numbers

### Recommended Next Steps
1. Build prototype and run straight-line accuracy tests on open pavement
2. Measure actual cross-track error with RTK logging
3. Test near buildings to quantify multipath degradation
4. Benchmark solenoid on/off timing and its effect on line start/stop accuracy
5. Compare results against the 2-5 cm target

---

## Sources

### Competitor Products
- [TinyMobileRobots TinyLineMarker Pro X](https://tinymobilerobots.us/robots/tinylinemarker-pro-x)
- [Turf Tank Two](https://turftank.com/us/turf-tank-two/)
- [Turf Tank One](https://turftank.com/us/turftankone/)
- [SWOZI Auto](https://swozi.com/auto/)
- [SWOZI Linemarking Machines](https://swozi.com/linemarking-machines-at-a-glance/)
- [10Lines Striping Robots](https://10linesrobots.com/striping-robots)
- [10Lines EUR 1.5M Funding (Invest in Estonia)](https://investinestonia.com/estonian-robotic-startup-10lines-raises-e1-5m-to-automate-line-marking-with-ai/)
- [10Lines EUR 700K Seed (EU-Startups)](https://www.eu-startups.com/2021/07/estonian-startup-10lines-raises-e700k-to-boost-its-autonomous-line-marking-robots-for-parking-spaces/)
- [FJD PaintMaster Pro](https://www.fjdynamics.com/product/fjd-rlm01-robotic-line-marker)
- [CivDash Road Striping (Equipment World)](https://www.equipmentworld.com/roadbuilding/article/15638310/civ-robotics-new-civdash-robot-automates-road-striping)
- [Tyker Robot Plotter (Inside GNSS)](https://insidegnss.com/tykers-robot-plotter-for-autonomous-ground-marking/)
- [HP SitePrint](https://www.hp.com/us-en/printers/site-print/layout-robot.html)
- [Husqvarna EPOS](https://www.husqvarna.com/us/discover/epos/)

### ArduRover & RTK Accuracy
- [ArduRover RTK Cross Track Tether Discussion](https://discuss.ardupilot.org/t/rtk-requirement-and-cross-track-tether/135276)
- [DIYRobocars ArduRover RTK Test](https://www.diyrobocars.com/2021/01/18/using-ardurover-with-an-rtk-gps/)
- [ArduPilot Waypoint Radius with RTK](https://discuss.ardupilot.org/t/waypoint-radius-using-rtk/9732)
- [ArduPilot Centimetric Waypoint Accuracy](https://discuss.ardupilot.org/t/waypoint-radius-centimetric-accuracy/64468)
- [ArduPilot Making Rover More Precise](https://discuss.ardupilot.org/t/making-the-ardurover-more-precise-in-reaching-waypoints/131510)
- [ArduPilot Navigation Tuning Docs](https://ardupilot.org/rover/docs/rover-tuning-navigation-420.html)
- [ArduPilot L1 Controller Overview](https://ardupilot.org/dev/docs/rover-L1.html)
- [The Mower Project RTK GPS](https://mowerproject.com/category/rtk-gps/)
- [Ardumower RTK (ArduSimple)](https://www.ardusimple.com/customer-project-ardumower-robotik-lawn-mower-kit/)
- [Robot Mower on ArduRover (ArduPilot Forum)](https://discuss.ardupilot.org/t/robot-mower-based-on-ardurover/61999)

### Academic Papers
- [Autonomous Road Marks Painting Robot (Robotica, Cambridge Core)](https://www.cambridge.org/core/journals/robotica/article/abs/development-of-an-autonomous-robotics-platform-for-road-marks-painting-using-laser-simulator-and-sensor-fusion-technique/7A3439E2962193C05AE0ACDF3A225DC9)
- [Autonomous Robot for Precision Floor Marking (MDPI Robotics)](https://www.mdpi.com/2218-6581/15/1/7)
- [Autonomous Robot for Road Lines Markings Inspection (Preprints.org)](https://www.preprints.org/manuscript/202410.1284)
- [GPS Multipath in Urban Canyons (PMC/Sensors)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12349109/)

### GPS/RTK Technology
- [Unicore UM980 Specs](https://en.unicore.com/products/surveying-grade-gnss-um980/)
- [ArduSimple simpleRTK3B (UM980)](https://www.ardusimple.com/product/simplertk3b-budget/)
- [RTK GPS Accuracy Factors (Lefixea)](https://www.lefixea.com/article/rtk166)
- [RTK Troubleshooting (Swift Navigation)](https://www.swiftnav.com/resource/blog/troubleshooting-the-most-common-rtk-ntrip-issues-a-step-by-step-guide)
- [ArduSimple RTK for Ground Robots](https://www.ardusimple.com/rtk-applications-ground-robots/)
- [GPS Antenna on Non-Rigid Body (PX4 Forum)](https://discuss.px4.io/t/effect-of-gps-antenna-mounted-to-non-rigid-body/22246)
- [RTK Fix Stability (The Mower Project)](https://mowerproject.com/2020/07/06/an-even-better-rtk-fix/)

### Standards
- [ADA Restriping Parking Spaces](https://www.ada.gov/resources/restriping-parking-spaces/)
- [ADA Parking Chapter 5](https://www.access-board.gov/ada/guides/chapter-5-parking/)
- [Parking Lot Striping Standards (GetOneCrew)](https://www.getonecrew.com/post/parking-lot-striping-standards)
