# Striper Robot -- Troubleshooting Guide

Problem, diagnosis, and fix format for the 10 most common issues.
Each entry includes: symptoms, diagnostic steps, fix, and prevention.

Hardware reference: Pixhawk 6C Mini running ArduRover 4.5+, Unicore UM980 GPS,
hoverboard hub motors (350W x2) with FOC firmware on SERIAL2, 36V 10Ah e-bike
battery, 12V diaphragm pump + solenoid valve, FlySky FS-i6X RC.

---

## 1. "Robot Won't Arm"

The robot refuses to arm when you hold rudder right + throttle down, or when
you click "Arm" in Mission Planner. A pre-arm failure message appears in the
Mission Planner HUD.

### Symptoms

- Mission Planner HUD shows a red "PreArm: ..." message
- No motor response to RC stick inputs
- The Pixhawk may show a flashing yellow or red LED pattern

### The 10 Most Common Causes

Read the exact PreArm message in Mission Planner. It tells you exactly what
is wrong.

| # | PreArm Message | Cause | Fix |
|---|----------------|-------|-----|
| 1 | "PreArm: Compass not calibrated" | Compass calibration not done or failed | Perform compass calibration: Setup > Mandatory Hardware > Compass > Start. Rotate robot through all axes outdoors, away from metal |
| 2 | "PreArm: GPS hdop too high" or "PreArm: Need 3D Fix" | GPS does not have a good enough fix. Satellite count too low or accuracy too poor | Move outdoors with clear sky view. Wait 30-60 seconds for fix. Check antenna SMA connector. Check `SERIAL3_PROTOCOL=5`, `GPS_TYPE=25` |
| 3 | "PreArm: Battery below minimum" or "PreArm: Battery voltage X below minimum Y" | Battery voltage below `BATT_ARM_VOLT` (35V) | Charge the battery. Minimum arming voltage is 35V (3.5V/cell). If battery is charged but reading is wrong, recalibrate `BATT_VOLT_MULT` with a multimeter |
| 4 | "PreArm: RC not calibrated" | RC transmitter has not been calibrated in Mission Planner | Go to Setup > Mandatory Hardware > Radio Calibration. Move all sticks to full extents and click Calibrate |
| 5 | "PreArm: Throttle not zero" or "PreArm: Throttle too high" | Throttle stick is not at the bottom position | Pull throttle stick (CH3) fully down. Check `RC3_TRIM` matches the actual minimum PWM value |
| 6 | "PreArm: Check AHRS" or "PreArm: EKF not healthy" | EKF has not converged yet (common immediately after power-on) or IMU calibration is bad | Wait 30-60 seconds after boot for the EKF to converge. If it persists, redo accelerometer calibration: Setup > Mandatory Hardware > Accel Calibration |
| 7 | "PreArm: Compass offsets too high" | Compass calibration was done near a magnetic source, or Pixhawk is mounted too close to hub motors | Redo compass calibration at least 10m from vehicles and metal structures. Move Pixhawk farther from the hub motors (at least 15cm) |
| 8 | "PreArm: Param check failed" or "PreArm: SERVO_FUNCTION invalid" | A parameter value is out of range or conflicting | In Mission Planner, go to Config > Full Parameter List. Check for parameter errors highlighted in red. Reload from `striper.param` if needed |
| 9 | "PreArm: No scripting serial" or Lua script error | `SERIAL2_PROTOCOL` is not set to 28, or motor_bridge.lua failed to load | Check `SERIAL2_PROTOCOL=28`. Check SD card has `/APM/scripts/motor_bridge.lua`. Check GCS messages for Lua errors |
| 10 | "PreArm: Hardware safety switch" | Safety switch is engaged (Pixhawk default) | Hold the safety button on the Pixhawk for 5 seconds. Or set `BRD_SAFETY_DEFLT=0` to disable (our param file already does this since we use a hardware E-stop instead) |

### Diagnostic Steps

1. Connect to Mission Planner and read the HUD message bar -- the pre-arm
   message tells you exactly which check is failing
2. If no message is visible, go to the Messages tab for the full error text
3. Check which arming checks are enabled: `ARMING_CHECK=124` enables
   compass, GPS, INS, params, RC, and voltage checks (skips barometer)
4. For quick testing only: you can temporarily set `ARMING_CHECK=0` to
   bypass all checks. **Never do this for a real paint mission.**

### Prevention

- Run through the pre-job checklist (`docs/maintenance.md` Section 1)
  before every use
- If you change parameters, always try to arm before driving to a job site
- Keep the battery charged above 35V

---

## 2. "Robot Drives in Circles"

The robot starts an autonomous mission but drives in circles instead of
toward the first waypoint. In MANUAL mode, it drives normally.

### Symptoms

- In AUTO mode, robot spins in circles or spirals
- In Mission Planner, the heading indicator does not match the robot's actual
  facing direction
- The compass heading may be off by 90, 180, or random degrees
- MANUAL mode works correctly (because MANUAL uses raw RC input, no compass)

### Diagnostic Steps

1. Place the robot on the ground, pointed north (use a phone compass as
   reference)
2. In Mission Planner, check the heading display. If it shows south (180
   degree error), east (90 degree error), or spinning randomly, the
   compass is the problem
3. In Mission Planner, go to Status tab and watch the `magfield` values
   while rotating the robot. Erratic values = magnetic interference
4. Check `COMPASS_ORIENT` -- if the Pixhawk is rotated on the frame, this
   value must match:
   - 0 = Pixhawk arrow points forward (standard)
   - 4 = Pixhawk arrow points backward (yaw 180)
   - 6 = Pixhawk arrow points right (yaw 270)
5. Check physical distance between Pixhawk and hub motors. The permanent
   magnets in the hub motors produce strong magnetic fields

### Fix

| Cause | Fix |
|-------|-----|
| Compass not calibrated | Redo calibration outdoors, 10m+ from metal |
| `COMPASS_ORIENT` wrong | Set to match Pixhawk physical orientation on frame |
| Motor magnetic interference | Move Pixhawk farther from motors (15cm+). Re-calibrate. Set `COMPASS_MOT_TYPE=2` and run compass-mot wizard |
| Compass completely unreliable | Disable compass and use GPS-based heading: set `COMPASS_USE=0`, `EK3_SRC1_YAW=1`. Robot must be moving for heading (no heading at standstill) |

### Prevention

- Mount Pixhawk at maximum distance from hub motors
- Always calibrate compass at the job site, not at home
- Run `COMPASS_MOT_TYPE=2` (throttle-based motor compensation) once during
  initial setup
- Consider disabling the compass entirely for this robot (hub motors are very
  strong magnets) and relying on GPS course heading

---

## 3. "Paint Lines Are Wavy"

The painted lines have visible wobble, S-curves, or lateral offset instead
of being straight.

### Symptoms

- Lines wobble left and right by 2-10cm
- Wobble may be periodic (consistent S-curve) or random
- Lines may be offset from where they should be (parallel but shifted)

### Diagnostic Steps

1. Check GPS fix type in Mission Planner during the mission:
   - RTK Fixed = 8mm accuracy (wobble should be less than 2cm)
   - RTK Float = 20-50cm accuracy (visible wobble expected)
   - 3D Fix = 1-3m accuracy (unacceptable for striping)
2. Check HDOP value in Mission Planner: below 1.0 is excellent, 1.0-1.5 is
   good, above 1.5 indicates degraded geometry or multipath
3. Review the dataflash log: plot the GPS position vs the commanded path.
   If GPS is accurate but the robot is weaving, it is a PID tuning issue.
   If GPS itself is noisy, it is a GPS quality issue
4. Drive a straight line in MANUAL mode at the same speed and compare the
   GPS track -- if it is also wavy, the problem is GPS. If it is straight,
   the problem is the navigation controller

### Fix

| Cause | Fix |
|-------|-----|
| RTK Float or 3D Fix | Check RTK correction source. Verify NTRIP connection. Wait for RTK Fixed before painting |
| GPS multipath (near buildings) | Move to an area with clear sky view. Add a ground plane under the antenna. Increase `GPS_MIN_ELEV` from 5 to 10 degrees |
| PID tuning too aggressive | Reduce `ATC_STR_RAT_P` by 20%. Reduce `ATC_STR_RAT_D` to 0. Increase `NAVL1_PERIOD` from 5 to 7 |
| PID tuning too loose | Increase `ATC_STR_RAT_P` by 20%. Decrease `NAVL1_PERIOD` from 5 to 4 |
| Robot speed too fast for controller | Reduce `WP_SPEED` from 0.50 to 0.30 m/s |
| GPS antenna vibration | Secure antenna mounting. Ensure the antenna is rigid on the mast, not wobbling |
| `GPS_DELAY_MS` too high | Reduce from 200 to 100ms. The UM980 is fast and 200ms may over-compensate |

### Prevention

- Always verify RTK Fixed status before starting a paint mission
- Tune PIDs on dry runs (no paint) first
- Use the slowest speed that is practical (0.30-0.50 m/s)
- Add a ground plane disc under the GPS antenna

---

## 4. "Paint Lines Are Too Thick or Too Thin"

The paint line width is not the target 4 inches (10cm). Too thick wastes
paint and looks bad. Too thin leaves gaps in coverage.

### Symptoms

- Lines wider than 5 inches or narrower than 3 inches
- Inconsistent width (varies along the line)
- Drips or runs (too thick)
- Gaps or light spots (too thin)

### Diagnostic Steps

1. Stop the mission. Measure the actual line width with a tape measure
2. Test the nozzle spray pattern statically: hold the nozzle at the
   mounting height (6-8 inches) and trigger the solenoid manually. Measure
   the fan width
3. Check which nozzle tip is installed (TeeJet 8004 = 4 inch fan at the
   rated height)
4. Check pump pressure: if you have a pressure gauge, it should read
   60-80 PSI
5. Measure the actual nozzle-to-ground distance. Even 1-2 inches off can
   change the line width significantly

### Fix

| Problem | Cause | Fix |
|---------|-------|-----|
| Lines too wide (>5") | Nozzle too close to ground | Raise nozzle to 8 inches. Measure and mark the bracket |
| Lines too wide (>5") | Wrong nozzle tip | Verify TeeJet 8004 is installed (the "04" means 4 inches). Swap if wrong |
| Lines too wide (>5") | Pump pressure too high | If pump has adjustable pressure, reduce it. Or partially restrict the pump output |
| Lines too thin (<3") | Nozzle too far from ground | Lower nozzle to 6 inches |
| Lines too thin (<3") | Pump pressure too low | Check 12V rail voltage (should be 12.0V). Check pump for wear. Verify pump is getting 12V, not 10V from a sagging converter |
| Lines too thin (<3") | Clogged nozzle | Remove and clean nozzle tip. See maintenance guide Section 7 |
| Width varies along line | Robot speed varies | Check PID tuning for speed control. Set `SPRAY_SPEED_MIN=0.10` to cut paint at very low speeds |
| Drips/runs at line starts | Solenoid opens before robot moves | Increase `SPRAY_SPEED_MIN` from 0.10 to 0.20 m/s. Adjust lead time in paint_control.lua (`LEAD_TIME_MS`) |
| Thin at line ends | Solenoid closes too early | Increase `LAG_TIME_MS` in paint_control.lua from 30 to 50-80ms |

### Prevention

- Bench-test spray pattern with water before every job
- Mark the correct nozzle height on the mounting bracket with tape or a
  permanent marker
- Carry spare nozzle tips (TeeJet 8002, 8004, 8006) for different line
  widths
- Replace worn nozzle tips (every 50-100 gallons for plastic, 200-400
  for stainless)

---

## 5. "Robot Stops Mid-Mission"

The robot stops moving during an autonomous mission and will not continue.

### Symptoms

- Robot halts at a random point in the mission
- Motors are unresponsive
- Mission Planner may or may not show an error message
- The current waypoint number stops advancing

### Diagnostic Steps

Check these in order (most common first):

1. **Check the HUD message bar** in Mission Planner for failsafe messages:
   - "Battery failsafe" = voltage dropped below `BATT_LOW_VOLT` (33V)
   - "Fence breach" = robot crossed the geofence boundary
   - "RC failsafe" = RC transmitter signal lost
   - "GCS failsafe" = telemetry link lost
2. **Check the flight mode** -- did it change from AUTO to HOLD or RTL?
   If so, a failsafe triggered. See which one from the messages
3. **Check battery voltage** in Mission Planner. Below 33V = low battery
   failsafe. Below 30V = critical battery failsafe
4. **Check motor status**: in MANUAL mode, do motors respond to RC? If not,
   the UART link or motor_bridge.lua may have failed
5. **Check Lua script status**: look in GCS messages for "Lua: error" or
   "Lua: out of memory"
6. **Check E-stop**: is the E-stop button pressed? (Everything would be
   dead, not just the motors)
7. **Check for crash detection**: `FS_CRASH_CHECK=1` can trigger if the
   robot is stuck against an obstacle and making no forward progress

### Fix

| Cause | Fix |
|-------|-----|
| Low battery failsafe | Swap or charge battery. Resume from last waypoint |
| Geofence breach | Redraw fence wider. Re-upload. Resume mission |
| RC failsafe | Check transmitter is on and bound. Replace transmitter batteries |
| GCS failsafe | Reconnect Mission Planner. Or set `FS_GCS_ENABLE=0` if you want the robot to continue without telemetry |
| Motor UART loss | Check SERIAL2 wiring. Reboot Pixhawk. See problem #7 |
| Lua script crash | Reboot Pixhawk. Check SD card for scripts. See problem #10 |
| Crash detection | Clear obstacle. Disable with `FS_CRASH_CHECK=0` if false-triggering |
| Missed waypoint (circling) | Increase `WP_RADIUS` from 0.05 to 0.10m. Or manually advance to next waypoint in Mission Planner |

### Prevention

- Fully charge battery before every job
- Draw geofence with 2m+ margin beyond all waypoints
- Keep RC transmitter powered on and within range during entire mission
- Test the full mission with water before loading paint

---

## 6. "GPS Shows 'No Fix'"

Mission Planner GPS status says "No Fix" or "No GPS" and the robot cannot
navigate or arm.

### Symptoms

- Mission Planner shows "No GPS" or "No Fix" with 0 satellites
- Or Mission Planner shows a few satellites but never achieves 3D Fix
- HUD position shows 0,0 or no movement when robot is moved

### Diagnostic Steps

1. **Is the GPS module detected?** In Mission Planner, go to Setup >
   Optional Hardware > GPS. It should show the UM980 (or "AutoDetect").
   If nothing is detected:
   - Check SERIAL3 wiring (TX/RX crossover, GND, 5V)
   - Check `SERIAL3_PROTOCOL=5` and `SERIAL3_BAUD=115`
   - Check `GPS_TYPE=25` (UM980)
2. **Is the antenna connected?** Check the SMA connector at the UM980
   breakout. It must be hand-tight. A disconnected antenna = 0 satellites
3. **Is there sky view?** The antenna needs an unobstructed view of the sky.
   Test outdoors, away from buildings and tree canopy. GPS does not work
   indoors
4. **How many satellites?** Mission Planner shows sat count. For 3D Fix:
   need 6+ satellites. For RTK: typically need 10+ satellites
5. **Is the antenna on the correct frequency?** The UM980 is L1/L2/L5
   triple-band. The antenna must support at least L1/L2. A single-band
   L1-only antenna will work but with reduced accuracy and slower convergence
6. **Cold start vs warm start**: first fix after a long power-off can take
   60-90 seconds (cold start). Subsequent fixes after short power-offs take
   5-15 seconds (warm start, cached ephemeris)

### Fix

| Cause | Fix |
|-------|-----|
| SERIAL3 wiring wrong | Verify TX-to-RX crossover: Pixhawk TX (pin 2) to UM980 RX, Pixhawk RX (pin 3) to UM980 TX. Verify GND connected |
| `GPS_TYPE` wrong | Set `GPS_TYPE=25` for UM980. Use `GPS_TYPE=1` (Auto) if unsure |
| Antenna disconnected | Hand-tighten SMA connector |
| No sky view | Move outdoors. The antenna needs 360-degree sky view |
| Antenna cable damaged | Replace the SMA cable. Check for kinks or cuts |
| UM980 module dead | Measure 5V at the UM980 VCC pin. If power is present but no response, the module may be faulty. Try `GPS_TYPE=1` (Auto) to re-detect |
| Wrong antenna type | Verify the antenna is multiband (L1/L2). A Bluetooth or WiFi antenna on an SMA connector will not work |

### Prevention

- Verify GPS fix as part of the pre-job checklist, before leaving your
  staging area
- Carry a spare SMA cable
- Protect the antenna and cable from physical damage during transport

---

## 7. "Motors Don't Respond"

RC stick inputs or AUTO mode commands do not produce any wheel movement.

### Symptoms

- In MANUAL mode, throttle stick has no effect on wheels
- In AUTO mode, the robot is armed and navigating but wheels do not spin
- Mission Planner shows SERVO1/SERVO3 PWM values changing (Pixhawk is
  trying to drive) but no physical motor movement
- Or SERVO1/SERVO3 stay at 1500 (Pixhawk is not outputting commands)

### Diagnostic Steps

1. **Is the robot armed?** Motors will not respond if disarmed. Check the
   HUD in Mission Planner for "ARMED" or "DISARMED"
2. **Check SERVO outputs**: in Mission Planner, go to Status tab and watch
   `servo1_raw` and `servo3_raw`. Move the throttle stick in MANUAL mode.
   Values should change from 1500 (center) toward 1000 or 2000
   - If they DO change: the Pixhawk is working. Problem is downstream
     (UART, Lua, hoverboard)
   - If they do NOT change: the Pixhawk is not receiving RC input, or
     mode/arming is wrong
3. **Check Lua script status**: look for "motor_bridge.lua loaded" in GCS
   messages. If missing, the script did not load from SD card
4. **Check SERIAL2 wiring**: Pixhawk TX (pin 2) to hoverboard RX, Pixhawk
   RX (pin 3) to hoverboard TX, Pixhawk GND (pin 6) to hoverboard GND
5. **Check hoverboard mainboard power**: is the 36V supply reaching the
   mainboard? Check with multimeter at the mainboard power terminals
6. **Check motor_bridge.lua named floats**: in Mission Planner Status tab,
   look for `MSPD` and `MSTR` values. If they change when you move sticks,
   the Lua script is running and sending commands
7. **Listen for motor buzz**: when armed in MANUAL with throttle applied,
   do the motors make any sound? A faint buzz but no rotation = hall sensor
   issue. No sound at all = no power or UART not working

### Fix

| Cause | Fix |
|-------|-----|
| Not armed | Arm the robot (rudder right + throttle down, or Mission Planner Arm button) |
| RC not calibrated | Calibrate RC: Setup > Mandatory Hardware > Radio Calibration |
| motor_bridge.lua not loaded | Check SD card has `/APM/scripts/motor_bridge.lua`. Check `SCR_ENABLE=1`. Reboot Pixhawk |
| `SERIAL2_PROTOCOL` wrong | Set `SERIAL2_PROTOCOL=28` (Scripting) and `SERIAL2_BAUD=115` |
| UART TX/RX crossed | Swap TX and RX wires at the Pixhawk end |
| Hoverboard no power | Check 36V reaching mainboard. Check fuse and E-stop |
| Hall sensor disconnected | Reconnect the 5-pin hall sensor cables at both motor and mainboard ends |
| FOC firmware not flashed | The mainboard must have hoverboard-firmware-hack-FOC, not the stock firmware. Re-flash with ST-Link V2 |
| Hoverboard mainboard dead | Test with USB-serial adapter directly. If no response, the mainboard is dead. Replace |

### Prevention

- Test motors in MANUAL mode before every job
- Check Lua script loading messages on every boot
- Keep UART solder joints solid -- re-solder if they look cold or cracked
- Carry a spare hoverboard mainboard (pre-flashed)

---

## 8. "Mission Planner Won't Connect"

Mission Planner cannot establish a connection to the Pixhawk over USB or
telemetry radio.

### Symptoms

- Mission Planner connection attempt times out
- "No heartbeat packets received" error
- COM port not appearing in the dropdown
- Connection established but immediately drops

### Diagnostic Steps

1. **USB connection**:
   - Is the USB-C cable connected to the Pixhawk USB-C port? Some cables
     are charge-only and do not carry data
   - Does the Pixhawk power up when USB is connected? (LED startup
     sequence)
   - In Windows Device Manager, does a new COM port appear when you plug
     in the Pixhawk? If not, install the Pixhawk USB driver (STM32 VCP)
   - Try a different USB-C cable
   - Try a different USB port on the laptop
2. **Telemetry radio**:
   - Is the telemetry radio powered? (Power LED on)
   - Are both radios paired? (Solid LED = paired, flashing = searching)
   - Is the baud rate correct? Default for Serial1 is 57600. The radio
     must match: `SERIAL1_BAUD=57`
3. **Mission Planner settings**:
   - Select the correct COM port from the dropdown
   - Select the correct baud rate: 115200 for USB, 57600 for telemetry
   - Try "AUTO" baud rate detection

### Fix

| Cause | Fix |
|-------|-----|
| Wrong COM port | Check Windows Device Manager for the correct port number. Select it in Mission Planner |
| Charge-only USB cable | Use a data-capable USB-C cable. Test with a phone -- if it transfers files, it carries data |
| USB driver missing | Install STM32 Virtual COM Port driver from st.com |
| Wrong baud rate | For USB: 115200 or AUTO. For telemetry: match `SERIAL1_BAUD` (default 57 = 57600) |
| Telemetry radio not paired | Re-pair radios using the SiK radio configuration tool or Mission Planner SiK radio page |
| Telemetry radio baud mismatch | Set both radios to 57600 (or matching value) using the SiK configurator |
| `SERIAL1_PROTOCOL` not set to MAVLink | Set `SERIAL1_PROTOCOL=2` (MAVLink2). If set to something else, Mission Planner cannot communicate |
| Pixhawk not booting | Check 5V power to Pixhawk. Verify BEC output. Try powering from USB only |
| Another program using the COM port | Close any other serial terminal or GCS software that may be holding the port open |

### Prevention

- Always carry two USB-C cables (one data, one backup)
- Label cables that are data-capable
- Note the COM port number for your setup and write it on the laptop with
  a sticker

---

## 9. "Paint Won't Stop"

The paint solenoid stays open and paint continues spraying even when it
should be off.

### Symptoms

- Paint sprays during transit segments (between lines)
- Toggling CH7 (paint relay) on the RC transmitter has no effect
- Mission Planner relay toggle has no effect
- Paint continues after switching out of AUTO mode

### Diagnostic Steps

1. **Is this a relay problem or a Lua script problem?**
   - In Mission Planner, manually toggle Relay 1. Listen for a relay click
   - If you hear a click but paint continues: the relay is switching but
     something else is holding the solenoid open (wiring short, second
     power path)
   - If no click: the relay is stuck closed (welded) or the signal is not
     reaching the relay
2. **Check relay module**: disconnect the signal wire from AUX5 (pin 54).
   The relay should return to its default state (open, paint off). If paint
   continues with the signal wire disconnected, the relay is welded
3. **Check for a wiring short**: disconnect the relay module entirely.
   Measure continuity between the 12V supply and the solenoid -- there
   should be no continuity with the relay removed. If there is, a wire is
   shorting around the relay
4. **Check paint_control.lua**: in GCS messages, look for "PAINT: OFF"
   messages when switching out of AUTO mode. If these messages are absent,
   the script may have crashed

### Fix

| Cause | Fix |
|-------|-----|
| Relay welded closed | Replace the relay module ($5). The relay contacts have fused from overcurrent or missing flyback diode |
| Relay signal wire shorted to 5V | Find and fix the short. The signal wire from AUX5 should only go to the relay IN pin |
| paint_control.lua crashed | Reboot Pixhawk. Script will reload. Check for Lua errors in GCS messages |
| `RELAY1_PIN` wrong | Verify `RELAY1_PIN=54` in parameters |
| Solenoid wired bypassing relay | Trace the solenoid wiring. Both terminals must go through the relay N.O. contact, not direct to 12V |

### Emergency Stop for Stuck Paint

1. Hit the E-stop (cuts all power, paint stops)
2. If E-stop is not accessible: physically pinch the tubing between the
   pump and nozzle
3. If pump is running but you only need to stop spray: disconnect the pump
   12V wire

### Prevention

- Install 1N4007 flyback diodes across both the solenoid and pump terminals
  (cathode to positive). This is the primary prevention for relay welding
- Add a 5A fuse on the 12V solenoid circuit
- Use an opto-isolated relay module (better than bare relay modules)
- Test relay off-switching before every job

---

## 10. "Lua Script Errors"

One or more Lua scripts fail to load or crash during operation.

### Symptoms

- GCS messages show "Lua: <script_name> error" with an error description
- GCS shows "Lua: out of memory"
- One or more of the four expected "loaded" messages is missing after boot:
  - `motor_bridge.lua loaded` -- MISSING means motors will not respond
  - `paint_control.lua loaded` -- MISSING means paint relay control is manual only
  - `paint_speed_sync.lua loaded` -- MISSING means no speed-based paint safety
  - `fence_check.lua loaded` -- MISSING means no automatic paint cutoff on fence breach
- No "loaded" messages at all = scripting engine is not enabled

### Diagnostic Steps

1. **Check `SCR_ENABLE`**: must be set to 1. If 0, no scripts will load.
   This requires a reboot after changing
2. **Check the SD card**:
   - Power off the Pixhawk. Remove the SD card
   - Insert into your laptop. Navigate to `/APM/scripts/`
   - Verify all four .lua files are present
   - Verify file sizes are non-zero (open each in a text editor to confirm
     they contain valid Lua code and are not corrupted)
   - Check the SD card for filesystem errors (right-click > Properties >
     Tools > Error checking on Windows)
3. **Check the error message**: the Lua error text identifies the script
   and line number. Common errors:
   - `attempt to index a nil value` = the script is calling an API that
     does not exist. This can happen if the ArduRover firmware is too old
     for the script
   - `out of memory` = the Lua heap is too small for all four scripts
   - `file not found` = the script path is wrong (must be `/APM/scripts/`)
   - `syntax error` = the .lua file is corrupted or was edited incorrectly
4. **Check `SCR_HEAP_SIZE`**: default is 102400 (100KB). All four scripts
   should fit comfortably. If getting out-of-memory, increase to 153600
   (150KB)
5. **Check `SCR_VM_I_COUNT`**: default is 25000. If scripts are timing
   out (taking too many instructions per tick), increase to 50000

### Fix

| Cause | Fix |
|-------|-----|
| `SCR_ENABLE=0` | Set `SCR_ENABLE=1`. Reboot Pixhawk |
| Script files missing from SD card | Copy all four .lua files from `ardurover/lua/` to the SD card at `/APM/scripts/` |
| Script files corrupted | Re-download from the repository and copy fresh files to the SD card |
| SD card not inserted | Insert the SD card into the Pixhawk. It is a microSD slot on the side |
| SD card filesystem error | Back up the card contents, format as FAT32, restore files |
| Out of memory | Increase `SCR_HEAP_SIZE` from 102400 to 153600. Reboot |
| Script timeout | Increase `SCR_VM_I_COUNT` from 25000 to 50000. Reboot |
| API not available (old firmware) | Update ArduRover firmware to latest stable (4.5+). Some Lua APIs were added in recent versions |
| Syntax error from bad edit | Compare the script against the repository version. Restore the original file |

### Quick Recovery in the Field

If you do not have time to debug a Lua script issue:

1. **motor_bridge.lua failed**: the robot cannot move autonomously. You
   must fix this script before proceeding. The most common field fix is to
   reboot the Pixhawk (power cycle)
2. **paint_control.lua failed**: you can still control paint manually via
   RC toggles (CH7 for solenoid, CH8 for pump). Mission DO_SET_RELAY
   commands will still work for basic on/off
3. **paint_speed_sync.lua failed**: non-critical. Paint control still works
   through paint_control.lua. You lose the speed-based paint pause feature
4. **fence_check.lua failed**: non-critical. ArduRover's built-in
   `FENCE_ACTION` still works. You lose the automatic paint-off on fence
   breach feature

### Prevention

- Never edit Lua scripts on the SD card directly from the Pixhawk (pull
  the card and edit on your laptop)
- After editing, open the script in a Lua syntax checker before deploying
- Keep backup copies of all scripts in the repository (`ardurover/lua/`)
- Set `SCR_DEBUG_LVL=1` for warnings that catch issues before they become
  crashes
- Test scripts in ArduRover SITL simulation before deploying to hardware

---

## Quick Diagnostic Flowchart

When something goes wrong, start here:

```
Is the Pixhawk powered on (LED lit)?
  NO  --> Check 5V BEC, check E-stop, check battery
  YES --> Continue

Is Mission Planner connected?
  NO  --> See Problem #8 (Mission Planner Won't Connect)
  YES --> Continue

What does the HUD message say?
  "PreArm: ..."     --> See Problem #1 (Robot Won't Arm)
  "Battery failsafe" --> See Problem #5 (Robot Stops Mid-Mission)
  "Fence breach"     --> See Problem #5 (Robot Stops Mid-Mission)
  "RC failsafe"      --> See Problem #5 (Robot Stops Mid-Mission)
  "Lua: error"       --> See Problem #10 (Lua Script Errors)
  No error message   --> Continue

Does the robot move in MANUAL mode?
  NO  --> See Problem #7 (Motors Don't Respond)
  YES --> Continue

Does the robot navigate correctly in AUTO mode?
  Drives in circles  --> See Problem #2 (Robot Drives in Circles)
  Lines are wavy     --> See Problem #3 (Paint Lines Are Wavy)
  Stops mid-mission  --> See Problem #5 (Robot Stops Mid-Mission)
  YES --> Continue

Is the paint system working?
  No paint at all     --> Check relay, pump, solenoid (Problem #7 in failure_modes.md)
  Won't stop painting --> See Problem #9 (Paint Won't Stop)
  Lines too thick/thin --> See Problem #4 (Paint Lines Too Thick/Thin)
  YES --> Everything is working. Go paint a parking lot.
```

---

## Parameter Quick Reference for Troubleshooting

These are the parameters you will most commonly need to check or adjust
during troubleshooting. All values reference the default `striper.param` file.

| Parameter | Default | Purpose | Adjust When |
|-----------|---------|---------|-------------|
| `FRAME_TYPE` | 2 | Skid steer / differential drive | Never (must be 2) |
| `SERIAL2_PROTOCOL` | 28 | Motor UART scripting | Motors do not respond |
| `SERIAL2_BAUD` | 115 | Motor UART baud rate | Motors do not respond |
| `SERIAL3_PROTOCOL` | 5 | GPS UART | GPS not detected |
| `GPS_TYPE` | 25 | UM980 driver | GPS not detected |
| `SCR_ENABLE` | 1 | Lua scripting on/off | Scripts not loading |
| `SCR_HEAP_SIZE` | 102400 | Lua memory (bytes) | Out of memory errors |
| `COMPASS_ORIENT` | 0 | Pixhawk mounting direction | Heading wrong |
| `COMPASS_USE` | 1 | Enable/disable compass | Compass interference |
| `WP_RADIUS` | 0.05 | Waypoint acceptance radius (m) | Circling at waypoints |
| `WP_SPEED` | 0.50 | Navigation speed (m/s) | Lines wavy or overshooting |
| `WP_OVERSHOOT` | 0.10 | Max overshoot distance (m) | Overshooting waypoints |
| `NAVL1_PERIOD` | 5 | Path following tightness | Lines wavy |
| `ATC_STR_RAT_P` | 0.20 | Steering P gain | Circles, oscillation, sluggish turns |
| `ATC_SPEED_P` | 0.40 | Speed P gain | Speed control issues |
| `BATT_ARM_VOLT` | 35.0 | Minimum arming voltage | Cannot arm (low battery) |
| `BATT_LOW_VOLT` | 33.0 | Low battery warning | Robot stops mid-mission |
| `RELAY1_PIN` | 54 | Solenoid relay pin | Paint relay not working |
| `RELAY2_PIN` | 55 | Pump relay pin | Pump relay not working |
| `FENCE_ENABLE` | 1 | Geofence on/off | False fence breaches |
| `ARMING_CHECK` | 124 | Arming checks bitmask | Cannot arm (diagnosis) |
| `FS_THR_ENABLE` | 1 | RC failsafe | Robot stops (RC loss) |
| `FS_GCS_ENABLE` | 1 | Telemetry failsafe | Robot stops (GCS loss) |
| `SPRAY_SPEED_MIN` | 0.10 | Min speed for paint (m/s) | Paint pooling at stops |
