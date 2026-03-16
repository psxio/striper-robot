# ArduRover Autonomous Line Striper - Setup Guide

## Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Connections](#hardware-connections)
3. [Firmware Flashing](#firmware-flashing)
4. [Parameter Loading](#parameter-loading)
5. [Lua Script Installation](#lua-script-installation)
6. [Calibration Checklist](#calibration-checklist)
7. [First Drive Test](#first-drive-test)
8. [Creating a Paint Mission](#creating-a-paint-mission)
9. [Troubleshooting](#troubleshooting)

---

## System Overview

| Component | Model | Interface |
|---|---|---|
| Flight controller | Pixhawk 6C (FMUv6C) | -- |
| Firmware | ArduRover 4.5+ | -- |
| Drive type | Differential (skid steer), FRAME_TYPE=2 | -- |
| Motors | Hoverboard BLDC x2 (FOC firmware) | UART on Serial2 |
| GPS | Unicore UM982 dual-antenna RTK (8mm) | UART on Serial3 |
| Paint valve | 12V solenoid (normally closed) | Relay 1 on AUX5 (pin 54) |
| Paint pump | 12V diaphragm pump | Relay 2 on AUX6 (pin 55) |
| RC system | FlySky FS-i6X + FS-iA6B receiver | iBus/PPM on RC IN port |
| Telemetry | SiK radio 433/915 MHz | UART on Serial1 |
| Battery | 36V hoverboard pack (10S lithium) | Power module on POWER1 |
| Power conversion | 36V to 12V DC-DC (solenoid, pump), 36V to 5V DC-DC (Pixhawk, GPS) | -- |
| E-stop | NC mushroom button in series with motor power | Hardwired |
| Weight | ~50kg with full paint tank | -- |
| Wheels | 6.5" (0.165m diameter) hoverboard wheels, 0.40m track | -- |

### Directory Structure

```
ardurover/
  params/
    striper.param             # Complete ArduRover parameter file
  lua/
    motor_bridge.lua          # CRITICAL: Hoverboard UART motor driver (PWM -> FOC protocol)
    paint_control.lua         # Paint solenoid control with lead/lag compensation
    paint_speed_sync.lua      # Speed-synchronized paint control (optional)
    fence_check.lua           # Enhanced geofence safety (kills paint on breach)
  hoverboard/
    setup.md                  # Hoverboard motor integration guide
  README.md                   # This file
```

---

## Hardware Connections

### Pixhawk 6C Port Map

```
+----------------------------------------------------------+
|  PIXHAWK 6C                                              |
|                                                           |
|  TELEM1 (Serial1) -----> SiK telemetry radio             |
|  TELEM2 (Serial2) -----> Hoverboard FOC UART (TX/RX/GND)|
|  GPS1   (Serial3) -----> UM982 RTK GPS module            |
|  GPS2   (Serial4) -----> (unused / future RTK input)     |
|  RC IN  ---------------> FlySky FS-iA6B (iBus or PPM)   |
|  POWER1 ---------------> 5V power module from DC-DC      |
|                                                           |
|  AUX OUTPUTS:                                            |
|  AUX1 (SERVO9)  -------> Sprayer pump output (PWM)       |
|  AUX2 (SERVO10) -------> Sprayer spinner output (PWM)    |
|  AUX5 (SERVO13, pin 54) -> Relay module -> Paint solenoid|
|  AUX6 (SERVO14, pin 55) -> Relay module -> Diaphragm pump|
+----------------------------------------------------------+
```

### GPS Wiring (UM982 to Pixhawk GPS1 Port)

The UM982 connects to the GPS1 port using a JST-GH 6-pin connector.

| UM982 Pin | Pixhawk GPS1 Pin | Notes |
|---|---|---|
| VCC (3.3V or 5V) | VCC (5V) | Check your UM982 breakout board voltage |
| GND | GND | Common ground |
| TX | RX (Serial3 RX) | UM982 transmits to Pixhawk |
| RX | TX (Serial3 TX) | Pixhawk transmits to UM982 |

Mount the GPS antenna on top of the robot, as high as practical, with a clear
sky view. Keep it away from motors, the solenoid, and large metal surfaces.
Use a ground plane under the antenna if possible.

For RTK operation, the UM982 needs RTCM3 correction data from a base station.

**Quickest method: Mission Planner NTRIP (free via RTK2Go)**

1. Open Mission Planner and connect to the Pixhawk via telemetry or USB
2. Go to **Setup > Optional Hardware > RTK/GPS Inject**
3. Enter the NTRIP caster settings:
   - Host: `rtk2go.com`
   - Port: `2101`
   - Mount Point: find the nearest base station at http://monitor.use-snip.com
     (pick one within 30km of your job site)
   - Username: your email address (RTK2Go is free, email is the login)
   - Password: `none` (leave blank or type "none")
4. Click **Connect**
5. The status should show "Connected" and bytes flowing
6. In the HUD, watch the GPS fix type change:
   - 3D Fix -> RTK Float (30-60 seconds) -> RTK Fixed (1-3 minutes)
7. Once "RTK Fixed" shows, GPS accuracy is 1-2cm

**Other options:**
- **Own base station**: A second UM982 at a known location, transmitting
  RTCM3 corrections via a telemetry radio.
- **Commercial service** (PointPerfect, Polaris): $30-50/month subscription,
  works anywhere with cellular coverage.

### UM982 Configuration

The UM982 should output NMEA at 115200 baud. Use a serial terminal or the
Unicore configuration tool to send these commands:

```
# Enable GGA and RMC at 10Hz on COM1
$command,output com1 nmea gga 0.1
$command,output com1 nmea rmc 0.1
$command,config com1 115200
$command,saveconfig
```

ArduPilot's GPS driver (GPS_TYPE=25, UnicoreMovingBaselineNMEA) gives the best performance.
Use GPS_TYPE=1 (AUTO) if you are unsure or using a different GPS module.

### Hoverboard Motor UART Wiring

The hoverboard mainboard runs FOC firmware and accepts motor commands over UART.
Connect to the Pixhawk TELEM2 port (Serial2).

| Hoverboard Board | Pixhawk TELEM2 | Notes |
|---|---|---|
| UART TX | RX | 3.3V logic levels on both sides |
| UART RX | TX | 3.3V logic levels on both sides |
| GND | GND | Common ground is required |

**Do NOT connect VCC between the hoverboard and Pixhawk.** They run on
different voltages (36V vs 5V). Only TX, RX, and GND are connected.

See `hoverboard/setup.md` for the complete FOC firmware configuration guide.

ArduRover sends motor commands as PWM values on SERVO1 (ThrottleLeft) and
SERVO3 (ThrottleRight). Since the hoverboard uses UART, not PWM, you need a
translation layer:

**Option A: Lua script bridge** (recommended)
A Lua script on the Pixhawk reads SERVO1/SERVO3 output values, converts them
to the hoverboard UART protocol (start bytes + int16 steer + int16 speed +
checksum), and sends them over Serial2 (protocol 28 = Scripting).

**Option B: External Arduino bridge**
An Arduino Nano reads PWM signals from Pixhawk servo outputs and converts
them to UART commands for the FOC board. Simpler wiring but adds a component.

### Paint Solenoid Wiring

The 12V paint solenoid connects through a relay module or MOSFET driven by
Pixhawk AUX5.

**Using a relay module (recommended for simplicity):**

```
Pixhawk AUX5 (3.3V signal) ---> Relay module signal input (IN)
Relay module VCC -------------> 5V (or 3.3V, check module specs)
Relay module GND -------------> GND
12V DC-DC output (+) ---------> Relay NO (normally open) contact
Relay COM contact -------------> Solenoid coil (+)
Solenoid coil (-) -------------> 12V DC-DC output (-)
```

**Using a MOSFET (lower latency, ~5ms faster than mechanical relay):**

```
Pixhawk AUX5 --[1K resistor]--> MOSFET gate (e.g., IRLZ44N logic-level)
                                 MOSFET gate --[10K resistor]--> GND (pull-down)
12V (+) -----> Solenoid (+)
Solenoid (-) -> MOSFET drain
                MOSFET source -> GND

Add a flyback diode (1N4007) across the solenoid:
  Cathode (band) to solenoid (+), Anode to solenoid (-)
  This protects the MOSFET from inductive voltage spikes.
```

Use a normally-closed (NC) solenoid so paint stops flowing if power is lost.

### Diaphragm Pump Wiring

**Option A -- Relay controlled** (matches params):
Same circuit as the solenoid, but on AUX6 (Relay 2, pin 55). The Lua script
and mission commands control the pump in sync with the solenoid.

**Option B -- Continuous run with manual switch:**
Wire the pump directly to 12V through a manual toggle switch. Set
`RELAY2_FUNCTION,0` in the parameter file to disable Relay 2. The pump runs
whenever the operator flips the switch.

### RC Receiver (FlySky FS-iA6B)

Connect the receiver to the Pixhawk RC IN port:

| Receiver Pin | Pixhawk RC IN | Notes |
|---|---|---|
| iBus OUT (or PPM) | Signal | Auto-detected by ArduPilot |
| VCC | VCC | 5V from Pixhawk |
| GND | GND | |

**Binding procedure:**
1. Hold the BIND button on the FS-iA6B while powering it on
2. On the FS-i6X transmitter, go to System > RX Bind and start binding
3. The receiver LED goes solid when bound

**Channel assignments on the FS-i6X:**

| Channel | Function | FS-i6X Control | Param |
|---|---|---|---|
| CH1 | Steering | Right stick horizontal | RCMAP_ROLL=1 |
| CH3 | Throttle | Right stick vertical | RCMAP_THROTTLE=3 |
| CH5 | Flight mode (3-pos) | SwC | FLTMODE_CH=5 |
| CH6 | E-stop / motor kill | SwD | RC6_OPTION=31 |
| CH7 | Paint solenoid manual | SwA | RC7_OPTION=28 |
| CH8 | Pump manual | SwB | RC8_OPTION=29 |

Mode switch positions (SwC):
- Position 1 (low): MANUAL (mode 0) -- full manual control
- Position 2 (mid): HOLD (mode 4) -- stop and hold position
- Position 3 (high): AUTO (mode 10) -- follow mission waypoints

### E-Stop Button

The E-stop is a normally-closed (NC) mushroom-head push button wired in series
with the 36V power supply to the hoverboard motor controller.

```
36V Battery (+) --> E-Stop Button (NC) --> Hoverboard mainboard VCC
```

When pressed, it cuts power to the motor drivers, immediately stopping the
wheels. The E-stop does NOT cut power to the Pixhawk, GPS, or RC receiver.
This is intentional so the flight controller can log the event and maintain
GPS lock for recovery.

Optionally, wire a second E-stop contact (or a relay coil) to RC channel 6
(RC6_OPTION=31, Motor Emergency Stop) so the Pixhawk also knows the E-stop
was engaged.

### Power Distribution

```
+------------------+
|  36V Hoverboard  |
|  Battery Pack    |
|  (10S Lithium)   |
+--------+---------+
         |
         +---> E-Stop (NC) ---> Hoverboard FOC mainboard (motor power)
         |
         +---> DC-DC 36V to 12V --+--> Relay module --> Paint solenoid
         |                        +--> Relay module --> Diaphragm pump
         |
         +---> DC-DC 36V to 5V ---+--> Pixhawk POWER1 port (via power module)
         |                        +--> FS-iA6B receiver (via Pixhawk RC port)
         |                        +--> UM982 GPS module
         |                        +--> SiK telemetry radio
         |
         +---> Pixhawk power module (voltage + current sensing)
              (in-line between DC-DC output and Pixhawk POWER1)
```

---

## Firmware Flashing

### Prerequisites

- Mission Planner (Windows) or QGroundControl (cross-platform)
- USB-C cable for Pixhawk 6C
- Internet connection for firmware download

### Steps

1. **Download ArduRover firmware** for Pixhawk 6C (fmuv6c):
   - Open Mission Planner
   - Go to **Setup > Install Firmware**
   - Click the **Rover** icon
   - Select **Pixhawk 6C / fmuv6c** from the board list
   - Or download manually from: https://firmware.ardupilot.org/Rover/stable/Pixhawk6C/

2. **Connect the Pixhawk** via USB-C (battery power is not needed for flashing)

3. **Flash the firmware**: Click "Install Firmware" and wait for the upload.
   The Pixhawk reboots automatically. The main LED will flash blue when ready.

4. **Verify**: Disconnect and reconnect. Mission Planner should connect and
   show "ArduRover V4.5.x" in the top bar.

5. **Alternative: command-line flashing**:
   ```bash
   # Build from source (Linux/WSL)
   cd ardupilot
   ./waf configure --board Pixhawk6C
   ./waf rover
   # Flash via uploader
   python3 Tools/scripts/uploader.py build/Pixhawk6C/bin/ardurover.apj
   ```

**Firmware version requirement:** Use ArduRover 4.5.0 or later for full UM982
support, Lua scripting improvements, and relay function parameters.

---

## Parameter Loading

### Loading striper.param via Mission Planner

1. Connect to the Pixhawk via Mission Planner (USB or telemetry radio)

2. Go to **Config > Full Parameter List**

3. Click **Load from file** and select `ardurover/params/striper.param`

4. Review the comparison window:
   - Green = new parameter (not previously set)
   - Yellow = changed value from current
   - Red = parameter not recognized (check firmware version)

5. Click **Write Params** to upload all parameters to the Pixhawk

6. **Reboot the Pixhawk** (Config > Reboot, or power cycle). Many parameters
   (especially SERIAL protocols and SCR_ENABLE) require a reboot.

7. Reconnect and verify critical parameters:
   - `FRAME_TYPE` = 2
   - `GPS_TYPE` = 25
   - `SCR_ENABLE` = 1
   - `SPRAY_ENABLE` = 1
   - `RELAY1_PIN` = 54
   - `FENCE_ENABLE` = 1

### Loading via MAVProxy

```bash
mavproxy.py --master=/dev/ttyACM0 --baudrate=115200
# In MAVProxy console:
param load params/striper.param
reboot
```

### Important Notes

- Some parameters require a reboot before taking effect. Always reboot after
  loading the full parameter file.
- If parameters show as "unknown," update to ArduRover 4.5+.
- After loading params, you must still calibrate sensors (see next section).
- If you change BATT_VOLT_MULT or BATT_AMP_PERVLT, verify with a multimeter.

---

## Lua Script Installation

ArduRover runs Lua scripts from the SD card in the `/APM/scripts/` directory.

### Steps

1. Remove the SD card from the Pixhawk 6C (or use MAVFtp via Mission Planner)

2. Create the directory structure on the SD card:
   ```
   /APM/
   /APM/scripts/
   ```

3. Copy the following scripts to `/APM/scripts/`:
   - `lua/motor_bridge.lua` -- **REQUIRED** hoverboard UART motor driver
   - `lua/paint_control.lua` -- paint solenoid control with timing compensation
   - `lua/paint_speed_sync.lua` -- speed-based paint synchronization (optional)
   - `lua/fence_check.lua` -- geofence breach paint shutoff (optional)

4. Reinsert the SD card into the Pixhawk

5. Verify scripting parameters are set:
   - `SCR_ENABLE` = 1
   - `SCR_HEAP_SIZE` = 102400 (100KB)

6. Reboot the Pixhawk

7. Verify scripts loaded by checking the Messages tab in Mission Planner:
   ```
   motor_bridge.lua loaded - hoverboard FOC UART bridge
     Rate=50Hz, Deadband=15, RampLimit=50
   motor_bridge: Serial port found, 115200 baud
   paint_control.lua loaded - relay 0 = solenoid
   fence_check.lua loaded - monitoring geofence
   ```

### Via MAVFtp (without removing the SD card)

In Mission Planner or MAVProxy:
```bash
# MAVProxy:
ftp put lua/motor_bridge.lua scripts/motor_bridge.lua
ftp put lua/paint_control.lua scripts/paint_control.lua
ftp put lua/paint_speed_sync.lua scripts/paint_speed_sync.lua
ftp put lua/fence_check.lua scripts/fence_check.lua
reboot
```

### Script Descriptions

**motor_bridge.lua** (REQUIRED):
Translates ArduRover SERVO1/SERVO3 PWM outputs (ThrottleLeft/ThrottleRight)
into the hoverboard FOC firmware UART protocol (0xABCD start frame + int16
steer + int16 speed + XOR checksum). Runs at 50Hz on Serial2
(SERIAL2_PROTOCOL=28). Without this script, the wheels will not move.
Includes PWM deadband, rate-limited acceleration ramp, and telemetry
output (MSPD/MSTR named floats).

**paint_control.lua** (required):
Controls the paint solenoid relay during autonomous missions. Monitors
DO_SET_RELAY commands from the mission, applies lead/lag timing compensation
for the solenoid mechanical delay (~50ms), and provides safety interlocks:
auto-off when not in AUTO mode, speed-based cutoff below 0.10 m/s. Logs all
paint state changes and cumulative painting statistics.

**paint_speed_sync.lua** (optional):
Adds speed averaging and hysteresis to the paint speed threshold. Uses a
rolling average of 5 speed samples to prevent rapid on/off cycling from GPS
speed jitter. Adds a 0.05 m/s hysteresis band: paint turns off at
SPRAY_SPEED_MIN and does not re-enable until speed exceeds SPRAY_SPEED_MIN
+ 0.05 m/s. Logs detailed speed and paint state data (custom PSYN log
message) for post-mission analysis.

**fence_check.lua** (optional):
Monitors geofence status and immediately kills the paint solenoid and pump
relays if the robot breaches the fence boundary. Provides a faster response
than relying solely on ArduRover's FENCE_ACTION mode change.

---

## Calibration Checklist

Perform these calibrations in order after loading the parameter file. All
calibrations are done through Mission Planner.

### 1. Accelerometer Calibration

- Go to **Setup > Mandatory Hardware > Accel Calibration**
- Place the robot on a flat, level surface
- Click "Calibrate Accel" and follow the 6-position procedure:
  1. Level (right-side up)
  2. Left side down
  3. Right side down
  4. Nose down
  5. Nose up
  6. Upside down
- For a 50kg robot, you will need help holding it in each position
- Wait for "Calibration Successful" before moving to the next step

### 2. Compass Calibration

- Go to **Setup > Mandatory Hardware > Compass**
- Click "Start" under Onboard Mag Calibration
- Rotate the robot through all orientations:
  - Spin 360 degrees while level
  - Tilt nose up ~45 degrees and spin 360
  - Tilt nose down ~45 degrees and spin 360
  - Roll left ~90 degrees and spin 360
  - Roll right ~90 degrees and spin 360
- Progress bars fill and turn green on success
- Click "Accept" when all compasses show "Success"
- **Perform this outdoors**, away from metal structures, cars, rebar, and
  power lines. Metal near the robot during calibration causes permanent errors.

### 3. RC Calibration

- Go to **Setup > Mandatory Hardware > Radio Calibration**
- Turn on the FS-i6X transmitter (ensure it is bound to the receiver)
- Click "Calibrate Radio"
- Move all sticks to their full extent in all directions
- Flip all switches through all positions
- Click "Click when Done"
- Verify channel mappings:
  - CH1 moves with right stick horizontal (steering)
  - CH3 moves with right stick vertical (throttle)
  - CH5 changes with SwC (3 positions for mode switch)
  - CH6 changes with SwD (E-stop)
  - CH7 changes with SwA (paint toggle)
  - CH8 changes with SwB (pump toggle)

### 4. Motor Direction Test

- **Place the robot on blocks** so the wheels spin freely off the ground
- Switch to MANUAL mode (SwC position 1)
- Arm the vehicle:
  - Throttle stick down + right rudder (steering stick right) for 3 seconds
  - Or press the ARM button in Mission Planner
- Gently push the throttle forward:
  - Both wheels should spin in the forward direction
  - If a wheel spins backward: set `SERVO1_REVERSED,1` (left) or
    `SERVO3_REVERSED,1` (right) and retest
- Push the steering stick right:
  - The left wheel should speed up, the right wheel should slow down (or reverse)
  - If the response is inverted: swap `SERVO1_FUNCTION` and `SERVO3_FUNCTION`
    (change 73 to 74 and 74 to 73) and retest
- Disarm when done (throttle down + left rudder for 3 seconds)

### 5. GPS Verification

- Take the robot outside with a clear sky view (no overhead structures)
- Power on and wait for GPS lock
- In Mission Planner, check the HUD and status bar:
  - Satellite count: should be 20+ with the UM982 dual-antenna
  - Fix type: wait for "RTK Fixed" (green) if base station is running
  - HDOP: should be below 1.0 for RTK, below 2.0 for standalone
- Verify the GPS position on the map matches the robot's actual location
- Walk the robot around and confirm the position tracks correctly

### 6. Battery Voltage Calibration

- Measure the actual battery voltage with a digital multimeter
- Compare to the value shown in Mission Planner
- If they differ, adjust `BATT_VOLT_MULT`:
  ```
  new_mult = current_mult * (actual_voltage / displayed_voltage)
  ```
- Write the new value and verify it reads correctly

### 7. Solenoid and Pump Test

- Keep the robot disarmed for this test
- In MANUAL mode, flip SwA (CH7) -- you should hear the solenoid relay click
- Flip SwB (CH8) -- you should hear the pump relay click (or pump start)
- Verify in Mission Planner Messages tab that relay state changes are logged
- **Test with water first**, not paint. Connect a water supply to the solenoid
  and verify it opens and closes cleanly.

---

## First Drive Test

Perform this in a large, open area (empty parking lot). Do not load paint for
the first drive test.

### Pre-Flight Checks

1. Battery voltage reads correctly in Mission Planner
2. GPS has at least a 3D Fix (RTK Fixed preferred but not required for drive test)
3. RC transmitter is bound and all channels respond correctly
4. E-stop button is accessible and tested (press it, verify motor power cuts)
5. Geofence is set (FENCE_RADIUS=50 circle fence, or upload a polygon)
6. Mode switch verified: SwC low=Manual, mid=Hold, high=Auto
7. Someone is standing by with the E-stop or a finger on SwC (Hold mode)

### Bench Test (wheels off ground)

Before driving on the ground, verify motors respond with the robot on blocks:

1. Place the robot on blocks so both drive wheels spin freely
2. Verify `motor_bridge.lua` loaded (check Messages tab for "motor_bridge: Serial port found")
3. Arm in MANUAL mode (SwC low, throttle down + rudder right for 3 seconds)
4. Gently push throttle forward -- both wheels should spin forward
5. If wheels don't respond: check SERIAL2_PROTOCOL=28, hoverboard UART wiring, FOC firmware
6. Test relay: flip SwA (CH7) -- you should hear the solenoid click
7. Disarm (throttle down + rudder left)

### Manual Drive Test

1. Lower robot to the ground. Arm in MANUAL mode (SwC low, throttle down + rudder right)
2. Slowly push throttle forward -- robot should drive straight
3. Note the throttle percentage needed for ~0.5 m/s (from the HUD)
   - Use this to set CRUISE_THROTTLE
4. Test steering: right stick right should turn the robot right
5. Test in reverse: pull throttle back
6. Test E-stop: press the button, verify wheels stop immediately
7. Re-arm and repeat at slightly higher speeds
8. Switch to HOLD (SwC mid) -- robot should stop and hold position
9. Switch back to MANUAL -- verify you regain control

### Auto Mode Test (No Paint)

1. In Mission Planner, create a simple rectangular mission:
   - 4 waypoints forming a 5m x 5m square
   - No DO_SET_RELAY commands (no paint)
   - WP_SPEED = 0.5 m/s

2. Upload the mission: Plan tab > Write WPs

3. Arm in MANUAL mode, then switch to AUTO (SwC high)

4. Observe the robot:
   - It should drive to WP1, then WP2, WP3, WP4
   - Watch path tracking accuracy -- should be within 5-10cm of the line
   - Watch speed consistency -- should hold near 0.5 m/s
   - Watch waypoint transitions -- robot should smoothly advance at each WP

5. If anything goes wrong:
   - Switch to HOLD (SwC mid) to stop immediately
   - Switch to MANUAL (SwC low) for full manual control
   - Press E-stop if needed

6. After the test, review the log in Mission Planner:
   - DataFlash Logs > Download > Review
   - Check GPS position vs desired track
   - Check speed vs desired speed
   - Check steering PID performance

### PID Tuning

If the robot oscillates, overshoots, or tracks poorly:

**Steering PID (ATC_STR_RAT_*):**
- Oscillates left/right: reduce ATC_STR_RAT_P (try 0.15, then 0.10)
- Slow to correct heading: increase ATC_STR_RAT_P (try 0.25)
- Steady-state heading error: increase ATC_STR_RAT_I (try 0.30)
- Overshoot on turns: increase ATC_STR_RAT_D slightly (try 0.01)

**Speed PID (ATC_SPEED_*):**
- Speed oscillates: reduce ATC_SPEED_P (try 0.30)
- Slow to reach target speed: increase ATC_SPEED_P (try 0.50)
- Steady-state speed error: increase ATC_SPEED_I (try 0.30)

**L1 Navigation (NAVL1_*):**
- Path tracking is loose (robot cuts corners): decrease NAVL1_PERIOD (try 4)
- Path tracking oscillates (weaves around the line): increase NAVL1_PERIOD (try 7)
- Cross-track correction is too aggressive: reduce NAVL1_XTRACK_I

---

## Creating a Paint Mission

### Mission Structure

A typical line-striping mission alternates between painting segments and
transit segments:

```
WAYPOINT (line start position)
DO_SET_RELAY  relay=0, setting=1       <-- Paint ON
WAYPOINT (line end position)
DO_SET_RELAY  relay=0, setting=0       <-- Paint OFF
DO_CHANGE_SPEED  speed=1.0             <-- Speed up for transit
WAYPOINT (transit: move to next line start)
DO_CHANGE_SPEED  speed=0.5             <-- Slow down for painting
WAYPOINT (next line start)
DO_SET_RELAY  relay=0, setting=1       <-- Paint ON
WAYPOINT (next line end)
DO_SET_RELAY  relay=0, setting=0       <-- Paint OFF
... repeat for all lines ...
RETURN_TO_LAUNCH                       <-- Drive back to start
```

### Step-by-Step in Mission Planner

1. Connect to the Pixhawk via telemetry or USB

2. Go to the **Plan** (Flight Plan) tab

3. Set the home position: right-click on the map > "Set Home Here"

4. **For each paint line:**

   a. Right-click at the line start position > "Add Waypoint"
      - Set altitude to 0 (ground vehicle)

   b. In the waypoint list, insert a command after the start waypoint:
      - Command: DO_SET_RELAY
      - Relay Number (P1): 0
      - Setting (P2): 1 (ON)

   c. Right-click at the line end position > "Add Waypoint"

   d. Insert another command after the end waypoint:
      - Command: DO_SET_RELAY
      - Relay Number (P1): 0
      - Setting (P2): 0 (OFF)

5. **For transit between lines (no paint):**

   a. Insert DO_CHANGE_SPEED: speed=1.0 m/s (faster transit)
   b. Add waypoints for the transit path (curves, turns to next line)
   c. Insert DO_CHANGE_SPEED: speed=0.5 m/s (slow down before next line)

6. At the end, add RETURN_TO_LAUNCH or a final waypoint at the start position

7. Upload: click **"Write WPs"**

8. Verify on the map that all waypoints are in the correct positions

### Tips for Accurate Lines

- **Survey your line positions** with RTK GPS before creating the mission.
  Walk the intended lines with the robot (or a handheld RTK receiver) and
  record the start/end coordinates for each line.

- **Use a spreadsheet** to generate waypoint coordinates, then import as a
  `.waypoints` file into Mission Planner (Plan > Load WP File).

- **Solenoid compensation**: place the DO_SET_RELAY ON command 2-3cm before
  the desired paint start point. The `paint_control.lua` script also handles
  lead/lag compensation automatically.

- **Keep WP_RADIUS at 0.05m** (5cm) so the robot must pass very close to
  each waypoint before advancing.

- **Use DO_CHANGE_SPEED** to differentiate painting speed (0.5 m/s) from
  transit speed (1.0 m/s). Slower painting gives more consistent coverage.

- **Upload a polygon geofence** matching the parking lot boundary before
  starting any mission. This prevents the robot from driving off the lot.

### Importing Waypoints from a File

If you have line coordinates from a survey or CAD drawing:

1. Format as a Mission Planner `.waypoints` file:
   ```
   QGC WPL 110
   0  1  0  16  0  0  0  0  LAT  LON  0  1
   1  0  3  16  0  0  0  0  LAT  LON  0  1
   2  0  3  183  0  1  0  0  0  0  0  1
   3  0  3  16  0  0  0  0  LAT  LON  0  1
   4  0  3  183  0  0  0  0  0  0  0  1
   ...
   ```
   (Command 16 = WAYPOINT, Command 183 = DO_SET_RELAY)

2. In Mission Planner: Plan tab > Load WP File

### Geofence Setup

1. In Mission Planner: Plan tab > select "Geo-Fence" from the dropdown
2. Draw a polygon around the work area (parking lot boundary with margin)
3. Click "Upload" to send the fence to the Pixhawk
4. Set FENCE_ENABLE=1, FENCE_ACTION=2 (RTL on breach), FENCE_TYPE=6
   (polygon + circle)
5. Test: walk the robot near the fence boundary and verify it triggers RTL

---

## Troubleshooting

### Robot Will Not Arm

| Message | Cause | Fix |
|---|---|---|
| "PreArm: GPS not healthy" | No GPS fix | Wait for satellites; check UM982 wiring; verify SERIAL3_PROTOCOL=5 |
| "PreArm: Need 3D Fix" | Only 2D fix | Move to open sky; wait longer for convergence |
| "PreArm: GPS hdop too high" | Poor satellite geometry | Move away from buildings; wait for more satellites |
| "PreArm: Compass not calibrated" | No compass cal | Run compass calibration outdoors |
| "PreArm: Accel not calibrated" | No accel cal | Run accelerometer calibration on flat surface |
| "PreArm: RC not calibrated" | No RC cal | Run radio calibration with full stick deflections |
| "PreArm: Battery below minimum" | Low battery or wrong voltage multiplier | Charge battery or recalibrate BATT_VOLT_MULT |
| "PreArm: Check FRAME_TYPE" | Wrong frame config | Verify FRAME_TYPE=2 |
| "PreArm: Check fence" | Fence enabled but no polygon | Upload a geofence or set FENCE_ENABLE=0 for testing |

### Robot Drives in the Wrong Direction

- Both wheels backward when throttle forward: set `SERVO1_REVERSED,1` and
  `SERVO3_REVERSED,1`
- Left and right swapped: swap `SERVO1_FUNCTION` and `SERVO3_FUNCTION`
  (change 73 to 74 and 74 to 73)
- Verify hoverboard UART channel order matches the FOC firmware

### Robot Oscillates or Weaves

- Reduce `ATC_STR_RAT_P` (try 0.15, then 0.10)
- Increase `NAVL1_PERIOD` (try 7 or 8)
- Check for mechanical play in wheels, bearings, or frame
- Verify `WHL_TRACK` matches actual wheel center-to-center distance
- Check compass calibration quality and `COMPASS_ORIENT` setting

### Paint Does Not Activate in AUTO Mode

1. Verify the mission has DO_SET_RELAY commands (relay=0, setting=1)
2. Check that `SCR_ENABLE=1` and `paint_control.lua` is on the SD card
3. Look for "paint_control.lua loaded" in Messages tab
4. Verify `RELAY1_PIN=54` and `RELAY1_FUNCTION=1`
5. Test relay manually: flip SwA (CH7) in MANUAL mode, listen for click
6. Check solenoid wiring, 12V power supply, and relay module

### Paint Activates But Lines Are Offset

- Adjust `LEAD_TIME_MS` and `LAG_TIME_MS` in paint_control.lua (default 50ms/30ms)
- Verify GPS antenna offset (`GPS_POS1_X`, `GPS_POS1_Y`) matches the actual
  antenna position relative to the paint nozzle
- Check that `WP_RADIUS` is small enough (0.05m)
- Verify GPS is in RTK Fixed mode during the mission

### GPS Shows "No Fix" or Never Reaches RTK

- Verify RTCM3 corrections are being sent to the UM982
  (check NTRIP status in Mission Planner)
- Verify UM982 baud rate matches `SERIAL3_BAUD` (115200)
- Check antenna cable and connector (damaged cables cause signal loss)
- The UM982 needs 30-60 seconds to converge to RTK Fixed after corrections
  start flowing. Dual-antenna converges faster than single-band.
- Verify `GPS_GNSS_MODE=127` (all constellations enabled)
- Check base station distance: best results within 10km

### Hoverboard Motors Do Not Respond

- Verify FOC firmware is flashed and configured for UART control
  (see `hoverboard/setup.md`)
- Check baud rate: `SERIAL2_BAUD=115` (115200)
- Verify TX/RX are crossed correctly (Pixhawk TX to FOC RX and vice versa)
- Test with a USB-to-serial adapter and terminal program before connecting
  to the Pixhawk
- The FOC firmware expects a specific packet format. Verify the Lua bridge
  script matches your firmware's protocol.
- Check for common ground between Pixhawk and hoverboard board

### Lua Script Errors

- Check Messages tab after boot for error messages
- Common issues:
  - "Script not found": verify file is in `/APM/scripts/` on the SD card
  - "Heap exhausted": increase `SCR_HEAP_SIZE` (try 150000)
  - "CPU limit": increase `SCR_VM_I_COUNT` (try 50000)
  - Syntax errors: test locally with `luac -p script.lua` on your PC
- If scripts load but do not work as expected, add `gcs:send_text()` debug
  messages and check the Messages tab

### Battery Voltage Reads Incorrectly

- Measure actual voltage with a digital multimeter at the battery terminals
- Adjust BATT_VOLT_MULT:
  ```
  new_mult = old_mult * (actual_voltage / reported_voltage)
  ```
- For a 36V system through a Pixhawk power module, typical BATT_VOLT_MULT
  is 10-12 depending on the module's voltage divider resistors

---

## Pre-Mission Checklist

Before each striping session:

- [ ] Battery fully charged (verify voltage in Mission Planner, should be > 35V)
- [ ] Paint reservoir filled and pressurized (if using pressurized system)
- [ ] Solenoid test: manually trigger relay, verify paint sprays
- [ ] GPS status: RTK Fixed (green) with HDOP < 1.0
- [ ] Geofence uploaded and matches the work area boundary
- [ ] Mission waypoints loaded, verified on map, and uploaded to Pixhawk
- [ ] RC transmitter powered on, bound, and all channels responding
- [ ] E-stop button tested and accessible to the operator
- [ ] Work area clear of people, vehicles, and obstacles
- [ ] Test drive in MANUAL mode: verify steering and throttle
- [ ] Test HOLD mode: verify robot stops cleanly
- [ ] Switch to AUTO, observe the first waypoint approach before paint sprays

---

## Quick Reference: Key Parameters

| Parameter | Value | Description |
|---|---|---|
| FRAME_TYPE | 2 | Differential drive / skid steer |
| WHL_TRACK | 0.40 | Wheel center-to-center (meters) |
| CRUISE_SPEED | 1.00 | Transit speed (m/s) |
| WP_SPEED | 0.50 | Paint speed (m/s) |
| WP_RADIUS | 0.05 | Waypoint acceptance radius (5cm) |
| NAVL1_PERIOD | 5 | L1 navigation period (seconds) |
| SPRAY_ENABLE | 1 | Built-in sprayer subsystem |
| SPRAY_SPEED_MIN | 0.10 | Minimum speed for spraying (m/s) |
| RELAY1_PIN | 54 | Paint solenoid on AUX5 |
| RELAY2_PIN | 55 | Pump on AUX6 |
| FENCE_ENABLE | 1 | Geofencing active |
| GPS_TYPE | 25 | Unicore UM982 (UnicoreMovingBaselineNMEA) |
| GPS_TYPE2 | 25 | Second antenna for heading |
| SCR_ENABLE | 1 | Lua scripting enabled |
| BRD_SAFETY_DEFLT | 0 | Hardware safety switch disabled |
| BATT_LOW_VOLT | 33.0 | Low battery warning (10S pack) |
| BATT_CRT_VOLT | 30.0 | Critical battery voltage (10S pack) |

---

## Reference Links

- ArduRover documentation: https://ardupilot.org/rover/
- ArduPilot Lua scripting: https://ardupilot.org/rover/docs/common-lua-scripts.html
- ArduPilot parameter list: https://ardupilot.org/rover/docs/parameters.html
- Pixhawk 6C documentation: https://docs.holybro.com/autopilot/pixhawk-6c/overview
- Mission Planner download: https://ardupilot.org/planner/
- FlySky FS-i6X: https://www.flysky-cn.com/fsi6x
- Unicore UM982 datasheet: https://en.unicorecomm.com/products/detail/24
- Hoverboard FOC firmware: https://github.com/EFeru/hoverboard-firmware-hack-FOC
- ArduPilot forums (Rover): https://discuss.ardupilot.org/c/rover/
