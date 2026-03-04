# Striper Robot -- Failure Modes Reference

Every failure scenario for the autonomous parking lot line striper, organized
by subsystem. For each failure: what the operator sees, what the robot does
automatically, and what the operator should do.

Hardware reference: Pixhawk 6C Mini, Unicore UM980 GPS, hoverboard hub motors
(350W x2) with FOC firmware, 36V 10Ah e-bike battery, 12V diaphragm pump +
solenoid valve + TeeJet TP8004EVS nozzle, FlySky FS-i6X RC, 2x HC-SR04 ultrasonics.

---

## 1. GPS Failures

### 1.1 Complete Loss of GPS Fix

| Item | Detail |
|------|--------|
| **Cause** | Antenna disconnected, antenna cable damaged, UM980 module failure, or complete sky obstruction (indoors, under dense cover) |
| **What operator sees** | Mission Planner shows "No GPS" or "No Fix". HUD GPS indicator turns red. Robot refuses to arm or, if mid-mission, triggers EKF failsafe |
| **Automatic action** | ArduRover triggers `FS_ACTION` (RTL or Hold depending on config). EKF rejects position estimates. Robot stops autonomous navigation |
| **Operator action** | 1. Switch to MANUAL mode on RC transmitter (CH5). 2. Drive robot to safety manually. 3. Check antenna SMA connector -- hand-tighten firmly. 4. Check antenna cable for cuts or kinks. 5. Verify antenna has clear sky view (no metal overhead). 6. In Mission Planner, check GPS tab for satellite count -- need 6+ for valid fix. 7. If no satellites at all, suspect UM980 module or wiring -- check SERIAL3 TX/RX/GND connections |
| **Prevention** | Secure SMA connector with threadlock (removable blue). Route antenna cable away from sharp edges. Pre-flight GPS lock check before every job |

### 1.2 RTK Float / Degraded Accuracy

| Item | Detail |
|------|--------|
| **Cause** | RTK corrections lost (NTRIP dropout, base station issue), too few satellites for RTK fix, or multipath interference near buildings |
| **What operator sees** | Mission Planner GPS status changes from "RTK Fixed" (green) to "RTK Float" (yellow) or "3D Fix" (orange). Position accuracy degrades from ~8mm to 0.5-2.0 meters. Painted lines become visibly wavy or offset |
| **Automatic action** | ArduRover continues navigating but with degraded accuracy. No automatic failsafe triggers for RTK loss -- the EKF accepts degraded GPS as long as it meets `EK3_GPS_CHECK` thresholds |
| **Operator action** | 1. Pause mission (switch to HOLD mode on CH5). 2. Check RTK correction source: in Mission Planner, verify NTRIP connection status. 3. If using NTRIP, check internet connectivity on the laptop running Mission Planner. 4. If corrections resume, wait 30-60 seconds for RTK to re-converge to Fixed. 5. If corrections cannot be restored, decide whether 3D Fix accuracy (~1-2m) is acceptable for the current work. For parking lot striping, it is not -- stop the job. 6. Check for nearby reflective surfaces (metal buildings, parked cars) causing multipath -- reposition the antenna if possible |
| **Prevention** | Use a reliable NTRIP service with cellular backup. Mount antenna on a ground plane (100mm aluminum disc) for multipath rejection. Test RTK convergence at the job site before starting paint work |

### 1.3 GPS Multipath Errors

| Item | Detail |
|------|--------|
| **Cause** | GPS signals reflecting off nearby buildings, metal walls, or large vehicles, creating false position readings. This is the primary unsolved challenge for parking lot striping near structures |
| **What operator sees** | Position jumps sideways by 10-50cm intermittently. Painted lines have sudden jogs or S-curves near buildings. RTK status may remain "Fixed" despite errors |
| **Automatic action** | None. The EKF may filter some outliers, but sustained multipath appears as valid position data |
| **Operator action** | 1. Stop the mission. 2. Identify the multipath source (usually a large flat metal surface within 5-10 meters). 3. If possible, paint the lines farthest from buildings first while RTK conditions are best. 4. For lines close to buildings, consider switching to manual RC driving with visual guides. 5. In Mission Planner, review the HDOP value -- values above 1.5 in RTK Fixed suggest multipath contamination. 6. Increase `GPS_MIN_ELEV` from 5 to 10-15 degrees to reject low-elevation satellites that are most affected by multipath |
| **Prevention** | Use a survey-grade antenna with ground plane (Tier 3 BOM). Schedule painting near buildings for times when satellite geometry is favorable (check GNSS planning tools). Consider dual-antenna heading for heading-independent of compass in future upgrade |

### 1.4 Antenna Disconnected Mid-Mission

| Item | Detail |
|------|--------|
| **Cause** | SMA connector vibrated loose, cable snagged on obstacle, or connector failure |
| **What operator sees** | Sudden complete GPS loss. Satellite count drops to 0 instantly (not gradually). Mission Planner alarm |
| **Automatic action** | EKF failsafe triggers. `FS_ACTION` executes (RTL attempt, but without GPS the robot may Hold instead). Motors stop in most configurations |
| **Operator action** | 1. Hit E-stop if robot is near obstacles. 2. Switch to MANUAL, drive to safety. 3. Reconnect antenna. 4. Wait for GPS lock (30-90 seconds for cold start, 5-15 seconds if ephemeris cached) |
| **Prevention** | Use SMA connector with strain relief. Zip-tie the cable to the frame at multiple points. Apply removable threadlock to the SMA nut |

---

## 2. Motor Failures

### 2.1 Motor Stall (One or Both)

| Item | Detail |
|------|--------|
| **Cause** | Wheel jammed by debris, high grass, curb contact, or mechanical obstruction. Overloaded on steep slope. FOC firmware overcurrent protection trip |
| **What operator sees** | Robot stops moving or veers sharply to one side. Motor makes buzzing/clicking sound. In Mission Planner, SERVO output shows maximum but speed is zero. motor_bridge.lua named floats (MSPD/MSTR) show commands being sent but no motion |
| **Automatic action** | FOC firmware has overcurrent protection -- the hoverboard PCB will cut power to the stalled motor to prevent winding damage. ArduRover may trigger `FS_CRASH_CHECK` if enabled and motion stops unexpectedly |
| **Operator action** | 1. Switch to HOLD mode. 2. Identify and clear the obstruction. 3. Check wheel for free rotation by hand. 4. If FOC protection tripped, power cycle the hoverboard mainboard (toggle E-stop off/on). 5. Check motor phase wires and hall sensor cables for disconnection. 6. Resume mission from the last completed waypoint |
| **Prevention** | Pre-clear the parking lot of debris before starting. Avoid running over curbs, speed bumps, or grass edges. Set `MOT_SLEWRATE=50` to limit sudden torque demands |

### 2.2 One Motor Dead

| Item | Detail |
|------|--------|
| **Cause** | Motor phase wire disconnected, hall sensor cable unplugged, motor winding failure, or one side of the hoverboard mainboard failed |
| **What operator sees** | Robot spins in a tight circle in one direction. One wheel is completely unresponsive while the other drives normally |
| **Automatic action** | ArduRover's steering controller will apply maximum differential, but with one motor dead, the robot cannot drive straight. No specific failsafe for single-motor failure |
| **Operator action** | 1. Hit E-stop. 2. Inspect the dead motor side: check 3 phase wires (yellow/blue/green) and 5-pin hall sensor cable at both the motor and mainboard ends. 3. Try swapping motor connectors at the mainboard to determine if the fault is in the motor or the controller. 4. If a phase wire is broken, it can be resoldered in the field. 5. If the motor or its mainboard channel is dead, the robot cannot operate -- pack up for repair |
| **Prevention** | Secure all motor connectors with hot glue or cable ties. Inspect phase wire solder joints before each day of operation |

### 2.3 Hoverboard PCB Fault

| Item | Detail |
|------|--------|
| **Cause** | MOSFET blowout (from stall or short), capacitor failure, regulator failure, or solder joint crack from vibration |
| **What operator sees** | Magic smoke, burning smell, both motors unresponsive, or erratic motor behavior (twitching, random speed changes). Status LED on mainboard may be off or blinking rapidly |
| **Automatic action** | None. The FOC firmware may halt on a hardware fault |
| **Operator action** | 1. Hit E-stop immediately. 2. Disconnect battery. 3. Inspect the mainboard for burnt components (blackened MOSFETs, bulging capacitors). 4. This is not field-repairable. 5. Replace the mainboard (source another hoverboard, $20-50). 6. Flash FOC firmware on the replacement board with your saved config.h settings |
| **Prevention** | Keep a spare hoverboard mainboard (already flashed) in your vehicle. Ensure adequate cooling airflow around the mainboard. Stay within motor current limits (avoid steep hills with a full paint tank) |

### 2.4 UART Communication Loss to Motors

| Item | Detail |
|------|--------|
| **Cause** | UART wire disconnected or broken, TX/RX crossed, baud rate mismatch, or motor_bridge.lua script crashed |
| **What operator sees** | Motors stop responding. In Mission Planner, SERVO1/SERVO3 PWM values change (Pixhawk is sending commands) but wheels do not move. `motor_bridge.lua` error messages appear in GCS messages if the script detects port loss |
| **Automatic action** | FOC firmware has a UART timeout -- if it receives no valid commands for ~1 second, it sets motor speed to zero (safe stop). motor_bridge.lua retries port connection every 1 second |
| **Operator action** | 1. Switch to HOLD. 2. Check UART wires at Pixhawk SERIAL2 connector (JST-GH pins 2, 3, 6). 3. Check UART pads on hoverboard mainboard (may need to re-solder). 4. Verify in Mission Planner: `SERIAL2_PROTOCOL=28`, `SERIAL2_BAUD=115`. 5. Check SD card: open `/APM/scripts/` and verify motor_bridge.lua is present and not corrupted. 6. Reboot Pixhawk to restart Lua scripting engine |
| **Prevention** | Use a proper JST-GH connector (not bare wires). Solder UART pads on the hoverboard mainboard with generous joints. Test motor commands before every job |

---

## 3. Paint Failures

### 3.1 Nozzle Clog

| Item | Detail |
|------|--------|
| **Cause** | Dried paint in the TeeJet TP8004EVS nozzle orifice, paint debris or aggregate, or inadequate straining of paint |
| **What operator sees** | Paint line becomes thin, spotty, or stops entirely despite pump running and solenoid open. Spray pattern changes from a clean fan to a deflected stream or drip |
| **Automatic action** | None. The system has no flow sensor to detect clogs |
| **Operator action** | 1. Pause mission (HOLD mode). 2. Turn off paint via RC toggle (CH7). 3. Remove the nozzle tip. 4. For TeeJet TP8004EVS: the tip is reversible -- flip it 180 degrees and run the pump briefly to back-flush. 5. Soak the tip in warm water or paint thinner for 5 minutes. 6. Clear the orifice with the cleaning pin (included with TeeJet tips) or a thin wire. 7. Reinstall and test with a short burst before resuming mission |
| **Prevention** | Strain all paint through a 60-mesh filter before pouring into the reservoir. Flush the entire system with warm water after every use. Carry 2-3 spare nozzle tips. With Tier 3 Graco tips, use the inline filter |

### 3.2 Pump Failure

| Item | Detail |
|------|--------|
| **Cause** | Pump motor burned out, diaphragm ruptured, pump lost prime (air in the line), or 12V power supply failure |
| **What operator sees** | No paint flow despite solenoid opening. Pump is silent (no motor sound) or running but not pushing fluid (damaged diaphragm). 12V rail voltage may be low if the DC-DC converter failed |
| **Automatic action** | None |
| **Operator action** | 1. Check 12V rail with multimeter at the DC-DC converter output. 2. Check pump relay (Relay 2) operation: toggle via RC (CH8) and listen for relay click and pump motor. 3. If pump motor runs but no flow: check for air lock -- disconnect output line, run pump to see if fluid moves. Prime by filling input line with paint. 4. If pump motor does not run: check wiring, fuse on 12V rail, and relay module connections. 5. If pump motor is burned out: replace pump ($30, carry a spare) |
| **Prevention** | Carry a spare pump. Run pump at least once a month even during off-season to keep the diaphragm flexible. Prime the pump with paint before starting each job. Check 12V fuse regularly |

### 3.3 Solenoid Stuck Open

| Item | Detail |
|------|--------|
| **Cause** | Relay welded closed (overcurrent), solenoid coil energized due to wiring short, or relay module failure |
| **What operator sees** | Paint continues flowing after the mission commands paint off. Paint sprays during transit segments between paint lines. Cannot stop paint flow via RC toggle |
| **Automatic action** | paint_control.lua monitors mode -- paint should stop when leaving AUTO mode. fence_check.lua kills paint on geofence breach. But if the relay is welded closed, software cannot override |
| **Operator action** | 1. Hit E-stop (cuts all power including 12V rail, stopping pump and closing solenoid). 2. If paint continues dripping (gravity-fed from elevated reservoir), physically pinch the tubing. 3. Inspect the relay module: swap channels to test if the relay is welded. 4. Replace the relay module if a channel is welded ($5 part). 5. Add a 5A fuse on the 12V solenoid circuit to prevent relay welding from overcurrent |
| **Prevention** | Use a fused relay module or add a 5A inline fuse on the solenoid circuit. Use an opto-isolated relay module. Always add a 1N4007 flyback diode across the solenoid to reduce back-EMF that can weld relay contacts |

### 3.4 Solenoid Stuck Closed

| Item | Detail |
|------|--------|
| **Cause** | Relay module signal wire disconnected, relay coil dead, 5V supply to relay module lost, or paint_control.lua script crashed |
| **What operator sees** | No paint flows during mission segments where it should be painting. Pump may be running (fluid circulating through relief valve) but solenoid is not opening. No relay click sound |
| **Automatic action** | None |
| **Operator action** | 1. Check relay module: verify 5V at VCC pin, GND connected, and signal wire from Pixhawk AUX5 (pin 54) is connected. 2. In Mission Planner, manually toggle Relay 1 and listen for relay click. 3. Check `RELAY1_PIN=54` in parameters. 4. Check paint_control.lua is running: look for "paint_control.lua loaded" in GCS messages after reboot. 5. Test the relay by jumpering the signal pin to 5V directly (bypasses Pixhawk). 6. Replace relay module if coil is dead |
| **Prevention** | Test relay operation before every job. Carry a spare relay module. Verify Lua scripts load on every Pixhawk boot by watching GCS messages |

### 3.5 Paint Tank Empty

| Item | Detail |
|------|--------|
| **Cause** | Ran out of paint mid-job. A 50-space lot needs 4-5 gallons; underestimation is common |
| **What operator sees** | Paint line fades out, becomes spotty, then stops. Pump runs normally but sputters air. Spray pattern becomes erratic |
| **Automatic action** | None. No fluid level sensor is installed |
| **Operator action** | 1. Pause mission (HOLD). 2. Refill paint reservoir. Strain through 60-mesh filter. 3. Prime pump by running it briefly with solenoid open. 4. Test spray pattern. 5. Resume mission from the last completed waypoint |
| **Prevention** | Estimate paint usage before the job: ~350 linear feet per gallon for standard 4" lines. Bring 20% extra. Check tank level periodically during the job |

### 3.6 Line Too Wide or Too Narrow

| Item | Detail |
|------|--------|
| **Cause** | Wrong nozzle tip installed, pump pressure incorrect, nozzle height wrong, or robot speed not matching spray rate |
| **What operator sees** | Lines are consistently wider or narrower than the target 4" width |
| **Automatic action** | None |
| **Operator action** | 1. For lines too wide: raise the nozzle, reduce pump pressure (if adjustable), or use a smaller orifice tip (e.g., TeeJet 8002 for 2" width). 2. For lines too narrow: lower the nozzle, increase pump pressure, or use a larger orifice tip (e.g., TeeJet 8006). 3. Check nozzle-to-ground distance: TeeJet TP8004EVS produces a 4" fan at approximately 6-8 inches from the surface. 4. Check robot speed: slower speed = thicker paint application (good for coverage, but can cause drips) |
| **Prevention** | Bench test spray pattern with water before every job. Mark the correct nozzle height on the mounting bracket. Calibrate `WP_SPEED` to match the paint flow rate |

---

## 4. Power Failures

### 4.1 Battery Dead Mid-Job

| Item | Detail |
|------|--------|
| **Cause** | Battery not fully charged before the job, battery capacity degraded, or job took longer than expected |
| **What operator sees** | Mission Planner shows low voltage warning (below 33V). Robot behavior becomes sluggish. Eventually the battery failsafe triggers |
| **Automatic action** | At `BATT_LOW_VOLT` (33V / 3.3V per cell): `BATT_FS_LOW_ACT=2` triggers Hold mode -- robot stops in place. At `BATT_CRT_VOLT` (30V / 3.0V per cell): `BATT_FS_CRT_ACT=1` triggers RTL. ArduRover will not arm below `BATT_ARM_VOLT` (35V) |
| **Operator action** | 1. When low voltage warning appears, note the current waypoint number. 2. Switch to HOLD or MANUAL. 3. Drive the robot back to the staging area manually (to save remaining battery for safe return). 4. Swap batteries or charge. The 36V 10Ah battery takes 3-5 hours on a standard 42V 2A charger. 5. Resume mission from the noted waypoint |
| **Prevention** | Fully charge before every job (42V at the charger). Monitor voltage in Mission Planner throughout the job. For large lots (100+ spaces), bring a second battery. The Tier 2 battery provides 45-70 minutes of runtime; plan jobs accordingly. For large lots, bring a spare battery |

### 4.2 DC-DC Converter Failure (36V to 12V)

| Item | Detail |
|------|--------|
| **Cause** | Converter overheated, input voltage spike, or component failure. The 36V-to-12V converter powers the paint pump and solenoid |
| **What operator sees** | Paint system stops working (pump and solenoid both dead). Motors still run (powered directly from 36V). In Mission Planner, everything else works normally |
| **Automatic action** | None |
| **Operator action** | 1. Measure output of 36V-to-12V converter with multimeter. Should read 12.0V +/- 0.5V. 2. If output is 0V or wrong voltage: disconnect loads and re-measure. If still dead, the converter has failed. 3. Replace converter ($5 part -- carry a spare). 4. If output is correct but paint system is still dead, check 12V rail fuse and wiring downstream |
| **Prevention** | Use a converter rated for at least 3A continuous (5A preferred). Mount with ventilation. Carry a spare converter. Add a 5A fuse on the 12V rail |

### 4.3 DC-DC Converter Failure (36V to 5V)

| Item | Detail |
|------|--------|
| **Cause** | Same as 4.2 but for the 5V BEC that powers the Pixhawk, GPS, and RC receiver |
| **What operator sees** | Everything dies except the motors (which are on 36V direct). Pixhawk goes dark. RC receiver loses power. GPS stops. The hoverboard mainboard may continue driving at whatever speed was last commanded for up to 1 second (FOC UART timeout) |
| **Automatic action** | FOC firmware UART timeout: if no UART commands received for ~1 second, motors stop. This is the only safety net when the entire control system loses power |
| **Operator action** | 1. Hit E-stop immediately (cuts 36V to everything). 2. Diagnose: measure 5V BEC output with multimeter. 3. Replace BEC if failed. 4. Before reconnecting, verify output is 5.0V +/- 0.25V with multimeter -- a wrong voltage will destroy the Pixhawk and GPS |
| **Prevention** | Use a quality BEC rated for 2A minimum (3A preferred). Mount with airflow. Carry a spare. This is a critical single point of failure -- consider wiring two BECs in redundant configuration for Tier 3 builds |

### 4.4 Brownout (Voltage Sag)

| Item | Detail |
|------|--------|
| **Cause** | Battery voltage sags under high motor load (e.g., climbing a curb ramp, both motors stalled briefly). The sag can dip the 36V supply enough to cause DC-DC converter dropout |
| **What operator sees** | Pixhawk reboots unexpectedly (LED startup sequence replays). GPS loses lock momentarily. Mission state may be lost. Motors may twitch |
| **Automatic action** | After reboot, Pixhawk enters INITIAL_MODE (HOLD, mode 4). It will not resume the mission automatically. Lua scripts must reload from SD card (takes a few seconds) |
| **Operator action** | 1. Wait for Pixhawk to complete boot sequence (solid green LED). 2. Wait for GPS to re-acquire fix (5-30 seconds). 3. Verify Lua scripts reloaded (check GCS messages for "loaded" messages). 4. The mission remains in memory -- switch to AUTO mode to resume. But verify the current waypoint is correct before resuming. 5. Investigate root cause: check battery charge level, check for motor stall conditions, check DC-DC converter input capacitance |
| **Prevention** | Use a battery with low internal resistance. Add a 1000uF capacitor across the 5V BEC output for ride-through. Avoid high-load scenarios (curbs, steep slopes). Upgrade to a Tier 3 Pixhawk 6C with dual power inputs |

---

## 5. Communication Failures

### 5.1 RC Link Lost (FlySky FS-i6X)

| Item | Detail |
|------|--------|
| **Cause** | RC transmitter turned off, battery dead in transmitter, out of range (300m+ for 2.4 GHz), or interference |
| **What operator sees** | Transmitter shows no bind indicator. Mission Planner RC inputs page shows all zeros or fixed values |
| **Automatic action** | `FS_THR_ENABLE=1` triggers throttle failsafe when RC PWM drops below `FS_THR_VALUE` (950us). `FS_ACTION=1` (RTL) activates. Robot drives back to launch point and stops. If GPS is unavailable, it switches to Hold instead |
| **Operator action** | 1. Turn transmitter on and verify bind. 2. Move closer to the robot. 3. Check transmitter batteries (4x AA in FS-i6X). 4. If bind is lost, re-bind: hold bind button on receiver while powering on, then put transmitter in bind mode. 5. After RC is restored, switch to HOLD, then verify control before switching to AUTO |
| **Prevention** | Fresh batteries in transmitter before every job. Stay within 200m of robot. Do not stand behind metal structures or vehicles that block 2.4 GHz signal |

### 5.2 Telemetry Lost (Mission Planner Connection)

| Item | Detail |
|------|--------|
| **Cause** | Telemetry radio range exceeded, radio power cable loose, USB cable disconnected from laptop, or radio interference |
| **What operator sees** | Mission Planner shows "link lost" or disconnects. HUD freezes. No live data |
| **Automatic action** | `FS_GCS_ENABLE=1` triggers GCS failsafe after `FS_TIMEOUT` (5 seconds). `FS_ACTION=1` (RTL) activates. Robot returns to launch point |
| **Operator action** | 1. Check USB connection to laptop. 2. Check telemetry radio power LED. 3. Move laptop closer to robot. 4. If using USB direct (no radio), reconnect USB-C cable. 5. In Mission Planner: disconnect and reconnect on the correct COM port and baud rate (57600 for Serial1) |
| **Prevention** | If you want the robot to continue autonomously without telemetry, set `FS_GCS_ENABLE=0`. But only do this if you trust the mission is correct and you have RC override available. Use a long-range telemetry radio (SiK 915MHz or RFD900) for lots where you park far away |

### 5.3 Lua Script Crash

| Item | Detail |
|------|--------|
| **Cause** | Runtime error in a Lua script (nil value access, division by zero), out-of-memory (heap exceeded), or SD card read error |
| **What operator sees** | Depends on which script crashed. motor_bridge.lua crash: motors stop (FOC UART timeout). paint_control.lua crash: paint may stay in its last state (stuck on or off). GCS message shows "Lua: script <name> error" or "Lua: out of memory" |
| **Automatic action** | ArduRover Lua engine may restart the failed script automatically (depends on error type). If motor_bridge.lua crashes, the FOC firmware UART timeout (1 second) stops the motors |
| **Operator action** | 1. Switch to HOLD (motors stop regardless of Lua state). 2. Check GCS messages for the error text. 3. Reboot Pixhawk (power cycle or use Mission Planner reboot command). Scripts reload from SD card on boot. 4. If the error repeats, check the SD card: pull it and verify /APM/scripts/ contains all four .lua files, and none are 0 bytes. 5. For "out of memory": increase `SCR_HEAP_SIZE` from 102400 to 153600 (150KB) |
| **Prevention** | Test all Lua scripts in SITL before deploying to hardware. Use `SCR_DEBUG_LVL=1` to catch warnings. Keep scripts simple -- the current four scripts total under 300 lines, well within Lua engine limits |

---

## 6. Navigation Failures

### 6.1 Waypoint Overshoot

| Item | Detail |
|------|--------|
| **Cause** | Robot speed too fast for the turn, `WP_OVERSHOOT` set too high, PID tuning too aggressive, or GPS latency causing late turn detection |
| **What operator sees** | Robot drives past waypoints before turning. Lines extend beyond where they should end. Corners are rounded instead of sharp |
| **Automatic action** | ArduRover accepts the waypoint as reached if it passes within `WP_RADIUS` (0.05m) and has overshot by less than `WP_OVERSHOOT` (0.10m) |
| **Operator action** | 1. Reduce `WP_SPEED` from 0.50 to 0.30 m/s. 2. Reduce `WP_OVERSHOOT` from 0.10 to 0.05m. 3. Reduce `CRUISE_SPEED` from 1.00 to 0.50 m/s for transit segments. 4. Check `GPS_DELAY_MS` -- if set too high, the EKF position estimate lags reality. Try reducing from 200 to 100ms. 5. Check PID tuning: reduce `ATC_SPEED_P` if braking is not responsive enough |
| **Prevention** | Always start with conservative (slow) speeds and tighten gradually. Use Mission Planner's auto-tune feature on flat pavement before running paint missions |

### 6.2 Circular Looping

| Item | Detail |
|------|--------|
| **Cause** | Compass interference from motor magnets, incorrect compass calibration, compass oriented wrong (`COMPASS_ORIENT`), or motor direction reversed |
| **What operator sees** | Robot drives in circles instead of toward the waypoint. Heading indicator in Mission Planner shows a heading that does not match the robot's actual pointing direction |
| **Automatic action** | None. ArduRover trusts the heading estimate |
| **Operator action** | 1. Switch to MANUAL and verify both sticks work correctly. 2. Check heading in Mission Planner vs actual robot orientation. If off by 180 degrees: set `COMPASS_ORIENT=4` (Yaw180). 3. If heading is erratic or spinning: motor magnetic interference. Increase distance between Pixhawk and hub motors. 4. Redo compass calibration: large figure-8 pattern in all 3 axes, away from metal and motors. 5. Enable compass learning: `COMPASS_LEARN=1` and drive in a straight line for 100m |
| **Prevention** | Mount Pixhawk as far from hub motors as possible (at least 15cm). Do compass motor compensation (`COMPASS_MOT_TYPE=2`). Calibrate compass at the job site, not at home |

### 6.3 Wrong Heading at Start

| Item | Detail |
|------|--------|
| **Cause** | Compass interference at the starting position (near a vehicle, manhole cover, or rebar). The robot drives off in the wrong direction at the start of the mission |
| **What operator sees** | Robot drives confidently but in the wrong direction for the first 5-20 meters until GPS-based heading correction kicks in |
| **Automatic action** | EKF3 with `EK3_SRC1_YAW=1` (GPS yaw) will gradually correct the heading using GPS velocity vector. This requires the robot to be moving at 1+ m/s |
| **Operator action** | 1. Switch to MANUAL, stop the robot. 2. Drive forward manually in a known direction (straight line, 10+ meters) to let the EKF learn the correct heading. 3. Switch back to AUTO. 4. If this persists, disable the internal compass for heading and rely solely on GPS course: set `COMPASS_USE=0` and ensure `EK3_SRC1_YAW=1` (requires motion for heading) |
| **Prevention** | Always start the robot in an open area, away from vehicles and metal structures. Drive forward manually for 10 meters before switching to AUTO to establish heading. Consider dual-GPS heading setup for future upgrade |

### 6.4 Missed Waypoint

| Item | Detail |
|------|--------|
| **Cause** | `WP_RADIUS` too tight (robot passes close but not close enough), GPS accuracy insufficient, or waypoint is physically inaccessible (on a curb, in a planter) |
| **What operator sees** | Robot circles around a waypoint repeatedly, unable to reach it within `WP_RADIUS` (0.05m). In Mission Planner, the current waypoint number does not advance |
| **Automatic action** | ArduRover keeps trying to reach the waypoint indefinitely. It will not skip it automatically |
| **Operator action** | 1. Switch to HOLD. 2. In Mission Planner, manually advance to the next waypoint (right-click waypoint, "Set WP"). 3. If this happens frequently: increase `WP_RADIUS` from 0.05m to 0.10m. 4. Check GPS accuracy: if not in RTK Fixed, the 5cm radius is too tight for float or 3D fix accuracy. 5. Check mission file: verify waypoint coordinates are on accessible pavement, not on a wall or obstacle |
| **Prevention** | Generate missions with waypoints at least 0.15m away from physical obstacles. Validate missions with the pathgen waypoint validator (`scripts/pathgen_cli.py validate`). Use `WP_RADIUS=0.10m` if GPS accuracy is routinely in the 5-10cm range |

---

## 7. Safety Failures

### 7.1 E-Stop Triggered

| Item | Detail |
|------|--------|
| **Cause** | Operator pressed the E-stop (intentional safety action), or the E-stop was bumped accidentally |
| **What operator sees** | All power cuts immediately. Motors stop. Pixhawk powers down. GPS and RC receiver lose power. Complete silence |
| **Automatic action** | Hard electrical cutoff. No software involved. The E-stop N.C. contacts break the 36V supply to all systems |
| **Operator action** | 1. Address the safety concern that triggered the E-stop. 2. Twist the mushroom button to release. 3. Wait for Pixhawk to boot (10-15 seconds). 4. Wait for GPS fix (5-60 seconds). 5. Wait for Lua scripts to load (2-3 seconds after boot). 6. Note the last completed waypoint from Mission Planner (the mission state is lost on power loss). 7. Manually set the current waypoint in Mission Planner and resume |
| **Prevention** | Mount E-stop where it can be reached intentionally but not bumped accidentally (top of robot, recessed if possible). Use a twist-release button (not push-push) to prevent accidental release |

### 7.2 Geofence Breach

| Item | Detail |
|------|--------|
| **Cause** | Mission waypoints placed outside the fence boundary, GPS drift pushed position outside the fence, or fence was drawn incorrectly in Mission Planner |
| **What operator sees** | Mission Planner shows "FENCE BREACH" warning. Robot enters RTL mode and drives toward the launch point |
| **Automatic action** | `FENCE_ACTION=2` (RTL) activates. fence_check.lua immediately turns off paint solenoid and pump relays. Robot drives back to launch point |
| **Operator action** | 1. Let the robot complete RTL (it will stop at the launch point). 2. Check the fence boundary in Mission Planner -- is it correctly drawn around the entire work area? 3. Check `FENCE_MARGIN` (1.0m) -- the robot must stay 1m inside the polygon. 4. If the fence is too small: redraw and re-upload in Mission Planner. 5. If the breach was due to GPS drift: check RTK status, wait for better fix. 6. To disable the fence temporarily: `FENCE_ENABLE=0` (use with caution) |
| **Prevention** | Draw fence boundaries at least 2 meters beyond the outermost waypoint in every direction. Include `FENCE_MARGIN=1.0m`. Validate that all mission waypoints are inside the fence polygon before starting. Set `FENCE_RADIUS=50` as a circular backup |

### 7.3 Obstacle Detected (HC-SR04 Ultrasonics)

| Item | Detail |
|------|--------|
| **Cause** | Person, vehicle, bollard, shopping cart, or other object in the robot's path. HC-SR04 sensors detect objects at 2-400cm range |
| **What operator sees** | Robot stops unexpectedly. If wired to ArduRover's object avoidance, Mission Planner shows obstacle detection |
| **Automatic action** | Depends on integration method. If wired through ArduRover's avoidance system (`AVOID_ENABLE`): robot stops and waits. If handled by a separate Arduino/script: behavior depends on implementation. In the default param file, `AVOID_ENABLE=0` (disabled) |
| **Operator action** | 1. Clear the obstacle. 2. If the robot stopped, switch to MANUAL, reposition if needed, then resume AUTO. 3. If using ultrasonic sensors with `AVOID_ENABLE=0`: the sensors are logging-only (no auto-stop). The operator must watch and use E-stop or RC manual override to stop the robot for obstacles |
| **Prevention** | Clear the lot of movable obstacles before starting. Set up cones or caution tape around the work area. Monitor the robot throughout the mission. Consider enabling `AVOID_ENABLE=1` once ultrasonic integration is tested |

---

## 8. Environmental Failures

### 8.1 Rain Starts During Job

| Item | Detail |
|------|--------|
| **Cause** | Weather change during an outdoor job. Paint application requires dry pavement |
| **What operator sees** | Rain on the lot surface. Paint will not adhere properly and will wash or bleed |
| **Automatic action** | None. ArduRover has no rain sensor |
| **Operator action** | 1. Pause mission (HOLD mode). 2. Stop paint (RC CH7 toggle). 3. If light drizzle: you may have a few minutes. Evaluate if paint is still adhering (test a short line). 4. If steady rain: stop the job. Drive robot to shelter in MANUAL mode. 5. Cover the electronics enclosure (Tier 2 has no weatherproofing). 6. Note the current waypoint for resumption. 7. After rain stops: wait until pavement is dry (30-60 minutes in sun). Resume from the last waypoint |
| **Prevention** | Check weather forecast before the job. Schedule a 4-hour dry window minimum. For Tier 3: the IP65 enclosure protects electronics but paint still requires dry pavement. Carry a tarp to cover the robot if caught unexpectedly |

### 8.2 Wind Too Strong

| Item | Detail |
|------|--------|
| **Cause** | Gusts or sustained wind exceeding 15 mph at ground level |
| **What operator sees** | Paint spray deflects to one side. Lines are offset from the nozzle path. Overspray drifts onto adjacent surfaces. Paint mist reaches bystanders or vehicles |
| **Automatic action** | None |
| **Operator action** | 1. If overspray is hitting vehicles or people, stop immediately. 2. Lower the nozzle height to reduce wind exposure. 3. Reduce pump pressure if possible (less atomization = less wind drift). 4. Paint only lines that run parallel to the wind direction (crosswind is the worst case). 5. If wind is sustained above 15 mph: stop the job and wait for calmer conditions |
| **Prevention** | Schedule paint jobs for early morning (typically calmest wind). Check wind forecast. Bring a wind meter ($15). Use low-pressure, large-orifice nozzle tips that produce large droplets resistant to wind drift |

### 8.3 Temperature Too Hot or Cold for Paint

| Item | Detail |
|------|--------|
| **Cause** | Water-based latex traffic paint has an application temperature window, typically 50-90 degrees F (10-32 degrees C). Outside this range, paint does not cure properly |
| **What operator sees** | In cold: paint is thick, does not flow well, streaky application, long cure time. In heat: paint dries too fast, clogs nozzle quickly, may skin over in the reservoir |
| **Automatic action** | None |
| **Operator action** | 1. Cold weather: store paint indoors (room temperature) until ready to pour. Work during the warmest part of the day. Add water (up to 5% by volume) to thin if needed per manufacturer guidelines. 2. Hot weather: keep paint in shade. Add retarder or extender per paint manufacturer guidelines. Flush nozzle more frequently (every 15-20 minutes). 3. Extreme cold (below 40 F / 4 C): do not paint. The paint will not cure and will wash off at the first rain. 4. Extreme heat (above 95 F / 35 C): paint early morning or late evening. The pavement surface temperature may be 20-30 degrees hotter than the air temperature |
| **Prevention** | Check paint manufacturer's application temperature range. Schedule jobs within the recommended window. Monitor both air and pavement surface temperature |

---

## Quick Reference: Failure Response Priority

When multiple failures occur simultaneously, address them in this order:

| Priority | Category | First Action |
|----------|----------|--------------|
| 1 | Safety (person in danger, fire, chemical spill) | E-stop. Remove people from danger |
| 2 | Power (uncontrolled motion, short circuit) | E-stop. Disconnect battery |
| 3 | Paint stuck on (spraying uncontrollably) | E-stop. Pinch tubing |
| 4 | Motor runaway | E-stop |
| 5 | Navigation (driving wrong direction) | RC switch to MANUAL. Steer to safety |
| 6 | GPS/Communication | RC switch to HOLD. Diagnose |
| 7 | Paint quality (wrong width, spotty) | Pause mission. Adjust and test |
| 8 | Environmental | Pause mission. Evaluate conditions |
