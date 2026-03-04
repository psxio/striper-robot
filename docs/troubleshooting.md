# Troubleshooting Guide

Problem → Diagnosis → Fix format for the 10 most common issues.

---

## 1. Robot Won't Arm

**Symptoms**: Mission Planner shows "PreArm: ..." messages, arm command rejected.

**Diagnostic steps**:
1. Read the PreArm message — it tells you exactly what's wrong
2. Mission Planner > Messages tab shows all PreArm failures

**Common causes and fixes**:

| PreArm Message | Fix |
|----------------|-----|
| "RC not calibrated" | Setup > Mandatory > Radio Calibration > Calibrate |
| "Compass not calibrated" | Setup > Mandatory > Compass > Start Calibration |
| "GPS not detected" | Check SERIAL3 cable, verify GPS_TYPE=25 |
| "Bad GPS Position" | Move to open sky, wait for 3D Fix |
| "Check Battery" | Connect battery, verify voltage > 33V |
| "Throttle not zero" | Center RC throttle stick |
| "Fence requires position" | Wait for GPS fix, or disable FENCE_ENABLE temporarily |
| "Hardware safety switch" | Press safety button on Pixhawk (if equipped) |
| "Compass offsets too high" | Recalibrate compass away from metal |
| "EKF not started" | Wait 30s after boot for EKF to initialize |

**Prevention**: Run `python scripts/deploy.py` before every field session.

---

## 2. Robot Drives in Circles

**Symptoms**: Robot spins continuously or curves in one direction.

**Diagnostic steps**:
1. Check heading in Mission Planner HUD — does it match actual heading?
2. Manually rotate robot 90° — does HUD heading change by 90°?

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| Compass interference from motors | Move Pixhawk/compass 15cm+ from motors |
| Compass not calibrated | Recalibrate outdoors, away from cars/metal |
| One motor reversed | Swap 2 of 3 phase wires on reversed motor |
| One motor not responding | Check UART cable from Pixhawk to hoverboard |
| Compass declination wrong | Set COMPASS_DEC for your location (auto from GPS) |
| Motor speeds unequal | Tune ATC_STR_RAT_P/I/D gains |

**Quick test**: Switch to MANUAL mode, drive forward. If straight, compass is the issue. If curved, motors are the issue.

---

## 3. Paint Lines Are Wavy

**Symptoms**: Lines wobble ±5-20cm instead of being straight.

**Diagnostic steps**:
1. Check GPS fix type — must be "RTK Fixed" for straight lines
2. Check HDOP — should be < 1.0
3. Check satellite count — want 15+

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| No RTK corrections | Set up NTRIP: `python scripts/rtk_setup.py --lat LAT --lon LON` |
| RTK Float (not Fixed) | Move closer to base station, wait longer, check NTRIP |
| GPS multipath | Move away from buildings/metal structures |
| Too fast | Reduce WP_SPEED from 0.5 to 0.3 m/s |
| Motor PID oscillation | Reduce ATC_STR_RAT_P by 20% |
| Loose GPS antenna | Secure antenna mount, tighten SMA connector |
| Wheel slip (wet/muddy) | Wait for dry conditions |

**Expected accuracy**: RTK Fixed = ±2cm, RTK Float = ±30cm, 3D Fix = ±2m.

---

## 4. Paint Lines Are Too Thick or Thin

**Symptoms**: Lines wider or narrower than expected 4 inches (10cm).

| Problem | Causes | Fix |
|---------|--------|-----|
| Too thick | Speed too slow, nozzle too close, pressure too high | Increase WP_SPEED, raise nozzle to 70mm, reduce pump duty |
| Too thin | Speed too fast, nozzle too high, pressure too low, clog | Decrease WP_SPEED, lower nozzle to 50mm, check pump, clean nozzle |
| Uneven width | Nozzle tilted, partial clog | Level nozzle, remove and clean tip |
| Splatter/dots | Air in paint line, intermittent clog | Bleed air from pump, replace nozzle tip |

**Bench test**: Run pump with water at standstill. Spray should be a clean flat fan, 4" wide at 60mm distance.

---

## 5. Robot Stops Mid-Mission

**Symptoms**: Robot halts during AUTO mission, may or may not show error.

**Diagnostic steps**:
1. Check Mission Planner mode — HOLD? RTL? Still AUTO?
2. Check Messages tab for error messages
3. Check battery voltage

**Common causes and fixes**:

| Mode After Stop | Cause | Fix |
|-----------------|-------|-----|
| HOLD | RC failsafe (TX off), obstacle detected, or E-stop | Check TX, clear obstacle, release E-stop |
| RTL | Geofence breach or battery failsafe | Check fence boundary, check battery level |
| AUTO (but not moving) | Stuck on waypoint, motor stall | Check for debris, check if wheels are blocked |
| MANUAL | Someone switched RC mode | Switch back to AUTO to resume |

**Resume**: After fixing the issue, switch to AUTO mode. Robot resumes from current waypoint.

---

## 6. GPS Shows "No Fix"

**Symptoms**: Mission Planner shows "No GPS" or "No Fix", 0 satellites.

**Diagnostic steps** (in order):
1. Is GPS antenna connected? (Check SMA cable at UM980 and antenna)
2. Is UM980 powered? (Check 3.3V supply from Pixhawk)
3. Is antenna outdoors with clear sky? (Must see sky, not inside building)
4. Is SERIAL3 configured correctly? (GPS_TYPE=25, SERIAL3_BAUD=115)

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| Antenna disconnected | Re-seat SMA connector, verify click |
| Antenna cable damaged | Replace coax cable |
| Indoor/garage testing | Move outside — GPS requires sky view |
| Wrong GPS_TYPE | Set GPS_TYPE=25 for UM980 |
| Wrong serial port | Verify UM980 is on SERIAL3 (not SERIAL2/4) |
| UM980 firmware issue | Update UM980 firmware via UPrecise software |
| Cold start | Wait 60-120s for first fix after power-on |

**Expected time to fix**: Cold start: 60-120s. Warm start: 10-30s. RTK Fixed: additional 30-60s.

---

## 7. Motors Don't Respond

**Symptoms**: Arm succeeds but no motor movement when throttle is applied.

**Diagnostic steps**:
1. Check Mission Planner > Messages for "motor_bridge.lua" output
2. Check if Lua scripts are running: look for "loaded" messages at boot
3. Manually test motors: apply 12V to motor phase wires (briefly)

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| Lua scripts not on SD card | Copy to /APM/scripts/, reboot |
| SERIAL2 disconnected | Check TX/RX wires from Pixhawk to hoverboard |
| Baud rate mismatch | Both sides must be 115200 (SERIAL2_BAUD=115) |
| TX/RX swapped | Swap the two signal wires |
| Hoverboard not powered | Check 36V supply to hoverboard PCB |
| Hoverboard in error state | Power cycle hoverboard (disconnect/reconnect battery) |
| Wrong SERVO functions | Verify SERVO1_FUNCTION=73, SERVO3_FUNCTION=74 |
| SCR_ENABLE not set | Set SCR_ENABLE=1, reboot |

---

## 8. Mission Planner Won't Connect

**Symptoms**: Mission Planner shows "Connecting..." then times out.

**Diagnostic steps**:
1. What connection type? USB, telemetry radio, or WiFi?
2. Is COM port showing in Device Manager?
3. Is baud rate correct?

**Common causes and fixes**:

| Connection | Issue | Fix |
|------------|-------|-----|
| USB | Wrong COM port | Check Device Manager, select correct port |
| USB | Wrong baud rate | Try 115200 (default) or 57600 |
| USB | Driver missing | Install Pixhawk USB driver (Silicon Labs CP2104) |
| Telemetry | Radio not paired | Re-pair radios (hold bind button) |
| Telemetry | Wrong baud | Match SERIAL1_BAUD to radio config (57600 default) |
| Telemetry | Antenna disconnected | Check SMA connections on both radios |
| Any | Pixhawk not booted | Wait 10s after power-on, check status LEDs |

---

## 9. Paint Won't Stop

**Symptoms**: Paint continues spraying during transit (between paint segments).

**Diagnostic steps**:
1. Check relay state in Mission Planner (Setup > Optional > Relay)
2. Listen for solenoid click when relay toggles

**Common causes and fixes**:

| Cause | Fix |
|-------|-----|
| Solenoid stuck open mechanically | Replace solenoid valve ($15) |
| Relay module failed (stuck ON) | Replace relay module, test with multimeter |
| paint_control.lua lag timer too long | Reduce LAG_TIME_MS in script (default: 30) |
| Mission has unbalanced relays | Run `python scripts/deploy.py --waypoints mission.waypoints` to validate |
| 12V always on to solenoid | Check wiring — solenoid power MUST go through relay |

**Emergency**: Press E-stop to cut all power. Manually close paint tank valve.

---

## 10. Lua Script Errors

**Symptoms**: Features don't work (paint, obstacle avoidance), error messages in logs.

**Diagnostic steps**:
1. Check Mission Planner > Messages for "Lua:" or "ERR:" messages at boot
2. Look for specific script names in error messages
3. Check SD card is inserted and readable

**Common causes and fixes**:

| Error | Fix |
|-------|-----|
| "Script not found" | Verify files in /APM/scripts/ on SD card |
| "Out of memory" | Increase SCR_HEAP_SIZE (default: 122880 = 120KB) |
| "Syntax error at line N" | Open script, check line N for typos |
| "Nil value" | API function not available — check ArduRover version |
| Scripts don't run at all | Set SCR_ENABLE=1, reboot Pixhawk |
| Script runs then stops | Check for infinite loop or crash — add error logging |

**Debug tip**: Set `SCR_DEBUG_LVL=2` for verbose Lua output in Messages tab. Reset to 1 for normal operation.

---

## General Tips

- **Always check Messages tab first** — ArduRover logs almost every problem
- **Power cycle fixes 50% of issues** — disconnect battery, wait 10s, reconnect
- **Check wiring before software** — most field failures are loose connectors
- **Run deploy.py before every session** — catches config issues early
- **Keep spare parts**: nozzle tips, fuses, connectors, zip ties, spare Arduino Nano
