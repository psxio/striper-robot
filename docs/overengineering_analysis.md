# Overengineering Analysis: Autonomous Line Striping Robot

## Executive Summary

**Verdict: Yes, the current stack is significantly overengineered for what this robot actually does.**

The robot's core job is: read GPS, steer toward next waypoint, toggle a solenoid. The current implementation uses 20+ ROS2 nodes, a dual EKF localization pipeline, the full Nav2 stack, 5 safety sub-nodes, a custom FastAPI dashboard, custom ROS2 message types, and an action server architecture. This is the software stack of a hospital delivery robot or a warehouse AGV navigating dynamic indoor environments -- not a parking lot paint robot driving pre-defined straight lines in an empty lot at 3AM.

The entire robot could be replaced by **ArduRover on a Pixhawk + a Lua script**, or by **~400 lines of Python on a Raspberry Pi**. Both would ship faster, be easier to debug in the field, and be more reliable.

---

## Current Architecture Inventory

### Node Count: 20+ processes at runtime

| Node | Package | Purpose | Lines |
|------|---------|---------|-------|
| ekf_local_node | robot_localization | Fuse wheel odom + IMU | config only |
| ekf_global_node | robot_localization | Fuse local odom + GPS + IMU | config only |
| navsat_transform_node | robot_localization | GPS -> odom frame conversion | config only |
| controller_server | nav2_controller | RegulatedPurePursuit path following | config only |
| behavior_server | nav2_behaviors | Wait/Spin/Backup recovery behaviors | config only |
| velocity_smoother | nav2_velocity_smoother | Smooth cmd_vel output | config only |
| lifecycle_manager | nav2_lifecycle_manager | Manage Nav2 node lifecycles | config only |
| robot_state_publisher | robot_state_publisher | Publish URDF transforms | config only |
| motor_driver | striper_hardware | Serial bridge to ESP32 | ~200 lines |
| gps_node | striper_hardware | ZED-F9P NMEA parser | ~295 lines |
| imu_node | striper_hardware | BNO085 I2C driver | ~160 lines |
| paint_valve | striper_hardware | GPIO solenoid control | ~160 lines |
| ntrip_client | striper_hardware | RTK corrections client | ~405 lines |
| odom_publisher | striper_localization | Encoder -> odometry | ~200 lines |
| datum_setter | striper_localization | GPS datum management | ~175 lines |
| path_manager | striper_navigation | Job orchestration via Nav2 actions | ~375 lines |
| paint_controller | striper_navigation | Spray timing along path | ~180 lines |
| speed_regulator | striper_navigation | PID speed control with ramp | ~195 lines |
| safety_supervisor | striper_safety | Central safety arbiter | ~200 lines |
| obstacle_detector | striper_safety | Ultrasonic processing | ~100 lines |
| geofence | striper_safety | GPS boundary check | ~100 lines |
| watchdog | striper_safety | Communication timeout | ~80 lines |
| operator_override | striper_safety | Manual takeover | ~80 lines |

Plus the ESP32 firmware (~300 lines C++), FastAPI dashboard backend (~750 lines), frontend (~400 lines JS), pathgen library (~800 lines), and test suites.

**Estimated total codebase: ~5,000+ lines across 65+ files, 10 ROS2 packages, 4 custom message types, 4 custom services, 1 custom action.**

---

## Question 1: Is ROS2 Overkill?

### Short answer: Yes, massively.

### What commercial line marking robots actually run

**TinyMobileRobots (TinyLineMarker):** Uses RTK-GPS and a proprietary embedded controller. No ROS2. Controlled via a tablet app (TinyController). The robot is essentially a GPS waypoint follower with a paint valve. Their software architecture is not public, but based on the product behavior (upload field layout, press go, robot follows lines), it is almost certainly a custom embedded firmware doing pure pursuit or simple PID-to-waypoint navigation.

**Turf Tank:** Similar architecture. RTK-GPS, proprietary embedded system, tablet control. No evidence of ROS, Nav2, or any academic robotics framework. These are purpose-built embedded systems.

**Dusty Robotics (FieldPrinter):** Uses a laser tracker (total station) for positioning rather than GPS. Custom software on a tablet drives the robot. Purpose-built, no ROS.

**The pattern is clear:** Commercial line marking robots use purpose-built embedded firmware, RTK-GPS, and simple path-following algorithms. None of them use ROS2, Nav2, or dual EKF localization. They are closer to a CNC machine than to a research robot.

### Could this be done with a simple Python script on a Raspberry Pi?

**Yes.** The core algorithm is:

```
while waypoints remaining:
    current_pos = read_gps()
    target = next_waypoint()
    heading_error = atan2(target.y - current_pos.y, target.x - current_pos.x) - current_heading
    steer(heading_error)  # PID or pure pursuit
    if on_paint_segment and distance_along_path > start_threshold:
        solenoid_on()
    else:
        solenoid_off()
```

This is fundamentally a ~200-400 line Python program. The ZED-F9P gives you 2cm position at 10-20Hz. You do not need an EKF, wheel odometry, or an IMU to follow parking lot lines at 0.5 m/s with 5cm tolerance.

### micro-ROS on ESP32 -- could the ENTIRE robot run on an ESP32?

**No, not practically.** The ESP32 is excellent as a motor controller (which is how you are already using it), but it lacks the memory and processing power to run a GPS waypoint follower with NTRIP corrections, serial GPS parsing, and any kind of path management simultaneously. The ESP32 has 520KB SRAM and no real OS. You still need a Linux SBC (Raspberry Pi) or a flight controller (Pixhawk) to run the navigation logic, GPS parsing, and NTRIP client.

### ArduRover on a Pixhawk -- could we just flash ArduRover and be done?

**Yes. This is the strongest alternative to the current stack.** See the deep dive in Question 2.

---

## Question 2: ArduPilot / ArduRover Deep Dive

### Does ArduRover support what we need?

| Feature | ArduRover Support | Notes |
|---------|-------------------|-------|
| Custom waypoint following | YES | Auto mode follows mission waypoints |
| Triggering GPIO/relay at waypoints | YES | DO_SET_RELAY and DO_SET_SERVO mission commands |
| Differential drive | YES | Native frame type, FRAME_TYPE=2 |
| RTK-GPS | YES | Direct ZED-F9P support via serial or DroneCAN |
| Sub-5cm navigation accuracy | YES | With RTK fix, tested by multiple community members |
| Speed-based flow control | YES | Built-in Sprayer function (AC_Sprayer) |
| Lua scripting for custom logic | YES | Full Lua scripting engine on supported boards |

### The Sprayer Function -- This Is Exactly What You Need

ArduPilot has a built-in `AC_Sprayer` library. Key parameters:

- `SPRAY_PUMP_RATE`: Pump rate (%) at 1 m/s. Scales linearly with speed. Default 10%.
- `SPRAY_PUMP_MIN`: Minimum pump rate when moving. Default 0% (stops when robot stops).
- `SPRAY_SPINNER`: PWM for spray nozzle spinner (controls droplet size).
- `SPRAY_SPEED_MIN`: Minimum speed (cm/s) for pump to activate.
- `SPRAY_ENABLE`: Master enable.

This means ArduRover will automatically control your paint flow rate proportional to robot speed, and turn the paint off when the robot stops or slows below a threshold. **This eliminates your entire `paint_controller_node`, `speed_regulator_node`, and `paint_valve_node`** -- three custom ROS2 nodes replaced by a handful of parameters.

For simple on/off solenoid control (which is what your current setup uses), you would set `SPRAY_PUMP_MIN` to 100 and use a relay output. The sprayer turns on during mission segments and off during transit.

### Lua Scripting for Paint-On/Paint-Off Logic

If the built-in sprayer is not flexible enough, ArduRover supports Lua scripts that can:

- Read current position, speed, mission state
- Control relays via `relay:enabled(relay_num)` and `relay:toggle(relay_num)`
- Trigger at specific waypoints or mission items
- Run custom logic at configurable intervals

A Lua script for paint control would be approximately **30-50 lines**:

```lua
-- paint_unified.lua
function update()
    if ardu:get_mode() == 10 then  -- AUTO mode
        local wp = mission:get_current_nav_index()
        local item = mission:get_item(wp)
        -- Check if current segment is a paint segment (via mission item param)
        if item and item:command() == 16 then  -- NAV_WAYPOINT
            relay:on(0)   -- paint on
        else
            relay:off(0)  -- paint off
        end
    else
        relay:off(0)  -- safety: paint off when not in auto
    end
    return update, 100  -- run every 100ms
end
return update, 1000
```

### Hardware for an ArduRover-based Paint Robot

| Component | Purpose | Approx Cost |
|-----------|---------|-------------|
| Pixhawk 6C or Cube Orange+ | Flight controller | $100-$250 |
| ZED-F9P RTK GPS (already have) | Positioning | $275 |
| GNSS antenna (already have) | GPS antenna | $65 |
| BNO085 IMU (already in Pixhawk) | Orientation | $0 (built into Pixhawk) |
| BTS7960 motor drivers (already have) | Motor power | $24 |
| Motors + encoders (already have) | Drive | $80 |
| 12V solenoid (already have) | Paint valve | $25 |
| Relay module | Solenoid switching | $5 |
| Telemetry radio (SiK 915MHz) | GCS link | $30 |
| Total additional beyond current BOM | | **~$135-$285** |

**You could remove:** Raspberry Pi 5 ($80), ESP32 ($10), BNO085 breakout ($30), and all custom wiring for those components. The Pixhawk contains its own IMU, compass, barometer, and safety switch. Net cost change is roughly neutral.

### Mission Planner / QGroundControl Replace the Dashboard

Mission Planner (Windows) and QGroundControl (cross-platform) provide:

- Real-time map display with robot position
- Mission upload/download (waypoints with DO_SET_RELAY commands)
- Live telemetry (speed, heading, GPS accuracy, battery)
- Parameter tuning
- Data logging and log replay
- Geofencing
- E-stop via RC or GCS

**This eliminates your entire FastAPI dashboard, SQLite job store, WebSocket bridge, and frontend.** That is roughly 1,500+ lines of code and an entire subsystem gone.

### Total ArduRover Parts List for a Paint Robot

1. Pixhawk 6C (or Cube Orange+)
2. ZED-F9P RTK GPS module + antenna
3. 2x BTS7960 motor drivers
4. 2x Pololu 37D gearmotors with encoders
5. 12V solenoid valve
6. Relay module (controlled by Pixhawk AUX output)
7. SiK 915MHz telemetry radio pair
8. RC receiver (Crossfire/ELRS for e-stop override)
9. Battery, frame, wheels (unchanged)
10. Laptop with Mission Planner or QGroundControl

**Software: ArduRover firmware (free, open source) + 30-50 line Lua script for paint logic + Mission Planner for job management.**

---

## Question 3: Simpler Navigation Alternatives

### Pure Pursuit on bare Python (no ROS2/Nav2)

The AtsushiSakai/PythonRobotics reference implementation of pure pursuit is **~80 lines of Python**. A complete GPS-waypoint-following pure pursuit controller including GPS reading, coordinate transforms, and motor output would be approximately **150-250 lines of Python**. Your current implementation uses Nav2's RegulatedPurePursuitController, which is ~2,000+ lines of C++ wrapping what is fundamentally the same algorithm.

The core pure pursuit formula:
```python
# Find lookahead point on path
alpha = atan2(lookahead_y - robot_y, lookahead_x - robot_x) - robot_heading
steering_curvature = 2.0 * sin(alpha) / lookahead_distance
angular_vel = linear_vel * steering_curvature
```

That is literally three lines of math. Everything else is bookkeeping.

### Stanley Controller vs Pure Pursuit

For line following at low speed (0.5 m/s), **pure pursuit is the correct choice**. Stanley controller is better at high speed and for Ackermann steering. For a differential drive robot at walking speed following pre-defined straight lines in a parking lot, pure pursuit is overkill already -- a simple PID heading controller toward the next waypoint would work fine.

### Simple PID-to-Waypoint

The simplest possible navigation for this robot:
```python
heading_to_target = atan2(target_y - gps_y, target_x - gps_x)
heading_error = normalize_angle(heading_to_target - current_heading)
angular_vel = Kp * heading_error
linear_vel = max_speed if abs(heading_error) < threshold else 0.0
```

This is 4 lines of core logic. For straight parking lot lines, this works. You do not need pure pursuit, Stanley, or any path-following framework.

### GPS Waypoint Following on ESP32/Arduino

Several libraries exist (TinyGPS++, SparkFun u-blox GNSS library) but the ESP32 cannot run the full stack (GPS + NTRIP + navigation + motor control + paint control) simultaneously due to memory and processing constraints. The ESP32 is best kept as a motor controller, with a Raspberry Pi or Pixhawk handling navigation.

---

## Question 4: Simpler Localization

### Does RTK fix mode eliminate the need for an EKF?

**For this application, yes.**

The ZED-F9P in RTK fixed mode provides:
- **1-2cm horizontal accuracy** (CEP50)
- **10-20 Hz update rate**
- Position + velocity output

Your current dual-EKF setup exists to smooth over GPS dropouts by fusing wheel odometry and IMU data. In a parking lot (open sky, no buildings blocking signals), the ZED-F9P will maintain RTK fix essentially 100% of the time. The EKF adds complexity and failure modes (bad IMU calibration, encoder drift, covariance tuning) while providing negligible benefit in this environment.

### Is wheel odometry necessary with RTK?

**No.** At 10-20 Hz position updates with 2cm accuracy, wheel odometry provides no meaningful improvement for a robot traveling at 0.5 m/s. Between GPS fixes (50-100ms), the robot moves 2.5-5cm -- which is within the GPS accuracy anyway.

Wheel odometry is valuable when:
- GPS is unavailable (indoors, urban canyons) -- NOT your use case
- GPS update rate is low (1 Hz) -- NOT your case with ZED-F9P at 10-20Hz
- Sub-centimeter accuracy is needed -- NOT your case (5cm tolerance)

### Can we skip the IMU entirely?

**Mostly yes, with one caveat.** The ZED-F9P provides heading-from-motion when the robot is moving, but not when stationary. If you need heading at standstill (e.g., to orient before starting a line), you need either:
- An IMU/compass (like the BNO085 you already have, or the one built into a Pixhawk)
- A dual-antenna GPS heading setup (two ZED-F9Ps, ~$550 additional)

For practical purposes, keeping a single cheap IMU for heading is worthwhile. But the dual EKF fusion pipeline is not. A simple complementary filter (GPS heading when moving, IMU heading when stopped) would suffice.

**What to cut:**
- ekf_local_node: **DELETE**
- ekf_global_node: **DELETE**
- navsat_transform_node: **DELETE**
- odom_publisher_node: **DELETE** (no wheel odometry needed)
- All ekf_*.yaml configs: **DELETE**
- imu_node: **KEEP but simplify** (heading only, not full EKF input)

---

## Question 5: Simpler Paint Control

### Can paint on/off be a simple distance-along-path check?

**Yes. This is what it should be.** Your current `paint_controller_node.py` is already doing exactly this -- it tracks distance along a segment and toggles the spray. But it does so as a separate ROS2 node subscribing to odometry topics, with configurable lead/lag compensation.

The simplified version:
```python
def should_paint(distance_along_segment, segment_length):
    return 0.0 <= distance_along_segment <= segment_length
```

The lead/lag compensation (50ms/30ms in your config) accounts for solenoid response time. At 0.5 m/s, 50ms = 2.5cm. This matters. But it can be implemented as a 2-line offset, not a 180-line ROS2 node.

### Do you need flow rate control or just on/off?

**Just on/off for V1.** Your current paint system uses a simple solenoid valve (normally closed, 12V, on/off). There is no proportional valve in the BOM. The `flow_rate` field in `PaintCommand.msg` is never actually used to control a proportional output -- the valve node only checks `spray_on` (boolean).

Flow rate control becomes relevant only if:
- You add a proportional valve or variable-speed pump
- You need consistent paint thickness at varying speeds

For V1, constant speed + on/off solenoid = consistent paint. Ship it.

### What do commercial robots use?

Commercial line marking robots (TinyMobileRobots, Turf Tank) use:
- **Solenoid valves** for on/off (like yours)
- **Constant-speed paint delivery** (pressurized tank or gravity feed)
- **Speed regulation** to maintain consistent line width (slow down at curves)

More advanced systems use proportional valves or peristaltic pumps for variable-width lines. Your solenoid approach is correct for V1.

---

## Question 6: Dashboard Alternatives

### Mission Planner / QGroundControl as Dashboard

If you go the ArduRover route, **Mission Planner or QGroundControl completely replaces your custom dashboard**. They provide:
- Map-based mission planning (draw waypoints on satellite imagery)
- Real-time position tracking on map
- Telemetry graphs (speed, heading, battery, GPS accuracy)
- Log downloading and replay
- Parameter configuration
- Geofence management
- Multiple vehicle support

QGroundControl also runs on tablets (Android/iOS), which is the form factor field operators prefer.

**This eliminates:** FastAPI backend, SQLite database, WebSocket bridge, HTML/CSS/JS frontend, ros_bridge.py, all dashboard routers, all dashboard schemas -- roughly 2,000+ lines of code.

### Foxglove Studio

Foxglove is a good option if you stay on ROS2 but want to stop building a custom dashboard. It provides visualization panels (map, plots, 3D, logs) without writing any frontend code. It can connect directly to ROS2 topics over WebSocket or rosbridge. It runs cross-platform and does not require ROS2 installed on the viewing machine.

However, Foxglove is a developer/debugging tool, not a customer-facing product. For customer-facing operation, you will eventually need a custom UI -- but that can wait until after V1 ships.

### Flask vs FastAPI

This is irrelevant to the overengineering question. FastAPI is fine. The problem is not which web framework you chose -- the problem is that you are building a custom web application at all when off-the-shelf ground station software exists.

### What do customers prefer?

Field operators strongly prefer **tablet apps** over web dashboards. A tablet (Android/iPad) they can carry around the parking lot, set on the robot, or hand to a worker is far more practical than a laptop running a web browser. QGroundControl runs natively on Android and iOS tablets.

---

## Question 7: Minimum Viable Software

### If you had to ship in 2 weeks, what would you cut?

**Option A: ArduRover (recommended -- ship in 1 week)**

1. Flash ArduRover on a Pixhawk 6C (1 hour)
2. Configure differential drive frame type (30 minutes)
3. Configure ZED-F9P GPS (already done)
4. Wire solenoid to Pixhawk relay output (1 hour)
5. Write 30-line Lua script for paint on/off logic (2 hours)
6. Create test mission in Mission Planner (1 hour)
7. Tune PID gains by driving the robot in Manual mode (1-2 days)
8. Test auto missions with paint (2-3 days)

**Total new code: ~30 lines of Lua. Everything else is configuration.**

**Option B: Bare Python on Raspberry Pi (ship in 2 weeks)**

Keep only:
1. GPS serial reader (simplified from gps_node.py, ~80 lines)
2. NTRIP client (simplified from ntrip_client_node.py, ~120 lines)
3. Motor serial bridge (simplified from motor_driver_node.py, ~60 lines)
4. Pure pursuit / PID waypoint follower (~100 lines)
5. Paint on/off distance check (~20 lines)
6. Job loader (read JSON waypoints file, ~30 lines)
7. Main loop tying it all together (~50 lines)
8. Simple safety: e-stop GPIO check, geofence check (~30 lines)

**Total: ~500 lines of Python. One file. No ROS2. No Nav2. No EKF.**

### What is the 80/20?

The 20% of the code doing 80% of the work:

1. **GPS reader** (gps_node.py) -- you must read GPS, no way around it
2. **NTRIP client** (ntrip_client_node.py) -- you must get RTK corrections
3. **Motor serial bridge** (motor_driver_node.py) -- you must drive motors
4. **ESP32 firmware** (esp32_motor_controller.ino) -- PID motor control is essential
5. **Paint valve toggle** -- a single GPIO write

Everything else is scaffolding, abstraction, or handling edge cases that do not exist in a parking lot:

- **Nav2**: You have no obstacles to plan around. Your paths are pre-defined straight lines. RegulatedPurePursuit with costmaps and recovery behaviors is for dynamic indoor environments.
- **Dual EKF**: You have RTK GPS in an open parking lot. The EKF is solving a problem you do not have.
- **5 safety nodes**: A single `if estop_pressed or outside_geofence: stop()` check in the main loop is sufficient for V1.
- **Custom messages/services/actions**: These exist only because ROS2 requires them for inter-node communication. Without ROS2, you pass data between functions with regular Python function calls.
- **Dashboard + SQLite**: A JSON file of waypoints and QGroundControl (or even a terminal printout) is sufficient for V1.
- **URDF/xacro**: Publishing a robot model is unnecessary. There is no 3D visualization or collision checking needed.
- **Velocity smoother**: At 0.5 m/s with a 20Hz control loop, velocity smoothing is imperceptible.
- **Behavior server**: Wait/Spin/Backup recovery behaviors are for robots stuck in narrow hallways. You are in an empty parking lot.

---

## Concrete Recommendation

### Phase 1: Ship the MVP (1-2 weeks)

**Go with ArduRover on a Pixhawk 6C.**

Rationale:
- ArduRover already has differential drive, RTK-GPS, waypoint following, sprayer control, Lua scripting, geofencing, telemetry logging, and a full ground station (Mission Planner / QGroundControl)
- Total new code: ~30 lines of Lua
- Battle-tested firmware used on thousands of rovers worldwide
- Eliminates: ROS2, Nav2, dual EKF, all custom nodes, custom dashboard, custom messages
- You keep: ESP32 motor controller (wire it to Pixhawk PWM outputs instead of RPi serial), ZED-F9P GPS, solenoid valve, existing mechanical platform

**If ArduRover feels too opaque**, go with Option B: bare Python on Raspberry Pi. ~500 lines, one file, full control over every line of code.

### Phase 2: Add Complexity Only When Needed

- **If customers need a custom UI**: Build a simple tablet app that generates Mission Planner-compatible waypoint files. Do not build a web dashboard.
- **If accuracy degrades in specific lots** (trees, buildings): Add IMU heading fusion. Still no EKF -- a complementary filter in 10 lines of Python.
- **If you need to paint curves**: Implement pure pursuit. Still not Nav2 -- 80 lines of Python.
- **If you need obstacle avoidance**: Add ultrasonics to the Pixhawk (ArduRover supports them natively), or add them to the bare-Python version as a simple distance check.

### What to Delete from the Current Codebase

| Component | Verdict | Reason |
|-----------|---------|--------|
| ROS2 (entire striper_ws) | DELETE | Unnecessary framework overhead |
| Nav2 + RegulatedPurePursuit | DELETE | Pre-defined paths need no path planner |
| Dual EKF (ekf_local + ekf_global) | DELETE | RTK GPS is sufficient |
| navsat_transform_node | DELETE | Not needed without EKF |
| robot_state_publisher + URDF | DELETE | No 3D visualization needed |
| velocity_smoother | DELETE | Imperceptible at 0.5 m/s |
| behavior_server (Wait/Spin/Backup) | DELETE | Empty parking lot, no recovery needed |
| 5 safety sub-nodes | COLLAPSE to 1 function | if estop or geofence: stop |
| Custom ROS2 msgs/srvs/actions | DELETE | Not needed without ROS2 |
| FastAPI dashboard | DELETE | Use Mission Planner/QGC |
| SQLite job store | DELETE | JSON file is sufficient |
| WebSocket ros_bridge | DELETE | Not needed without custom dashboard |
| speed_regulator_node | DELETE | ArduRover handles speed |
| paint_controller_node | SIMPLIFY | 5 lines instead of 180 |
| odom_publisher_node | DELETE | No wheel odometry needed |
| datum_setter_node | DELETE | ArduRover handles GPS datum |

### What to Keep

| Component | Verdict | Reason |
|-----------|---------|--------|
| ESP32 motor controller firmware | KEEP | Solid PID motor control |
| ZED-F9P hardware + NTRIP concept | KEEP | Essential for accuracy |
| Pathgen library (models, coordinate_transform, templates) | KEEP | Useful for generating waypoint files |
| E-stop hardware | KEEP | Safety-critical |
| BOM and mechanical design | KEEP | Hardware is well-designed |

---

## Summary: Complexity Comparison

| Metric | Current Stack | ArduRover | Bare Python |
|--------|--------------|-----------|-------------|
| Lines of custom code | ~5,000+ | ~30 (Lua) | ~500 |
| Number of processes | 20+ | 1 (ArduRover) + 1 (ESP32) | 1 (Python) + 1 (ESP32) |
| Dependencies | ROS2, Nav2, robot_localization, FastAPI, aiosqlite, rclpy | ArduPilot firmware | pyserial, math |
| Config files | 4 YAML + launch files + URDF | ArduPilot params | 1 JSON |
| Time to debug in field | Hours (which node crashed?) | Minutes (check logs in MP) | Minutes (one file, print statements) |
| Time to onboard new dev | Weeks (learn ROS2 + Nav2) | Days (learn ArduPilot params) | Hours (read one Python file) |
| OS requirement | Ubuntu 22.04 with ROS2 Humble | None (bare metal firmware) | Raspberry Pi OS |
| Compute hardware | RPi 5 + ESP32 | Pixhawk + ESP32 | RPi 5 + ESP32 |

The current stack is built to handle problems this robot does not have. Ship the simple version. Add complexity only when reality demands it.
