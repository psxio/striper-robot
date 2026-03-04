# Failure Modes & Recovery Procedures

Every failure scenario for the Striper Robot, with detection, automatic response, and manual recovery.

---

## 1. GPS Failures

### 1.1 Loss of Fix (No GPS)
- **What you see**: Mission Planner shows "No Fix" or "No GPS", satellite count drops to 0
- **Robot does automatically**: Switches to HOLD mode (stops moving), paint turns off
- **What to do**:
  1. Check GPS antenna cable connection at Pixhawk SERIAL3
  2. Check antenna is mounted high with clear sky view
  3. Move away from buildings/trees and wait 60s for re-acquisition
  4. If persistent: power cycle Pixhawk, check UM980 LED (blinking = searching)

### 1.2 RTK Float (Degraded Accuracy)
- **What you see**: GPS status shows "RTK Float" instead of "RTK Fixed", HDOP > 1.5
- **Robot does automatically**: Continues mission (accuracy ~30cm instead of 2cm)
- **What to do**:
  1. Check NTRIP connection in Mission Planner (green = connected)
  2. Verify internet connection on laptop/phone providing NTRIP
  3. Check base station distance (>30km degrades accuracy)
  4. Wait 30-60s — may recover to Fixed. If not, pause mission and investigate
  5. **Paint lines will be wavy** — stop if precision matters

### 1.3 GPS Multipath (Near Buildings)
- **What you see**: Robot position jumps 0.5-2m randomly, path oscillates
- **Robot does automatically**: Nothing (GPS reports valid fix with bad data)
- **What to do**:
  1. Avoid painting rows within 3m of tall buildings or metal structures
  2. Start with rows farthest from buildings
  3. Consider GPS antenna ground plane to reduce multipath
  4. If persistent: use higher GPS antenna mast (>500mm)

### 1.4 Antenna Disconnected
- **What you see**: Satellite count drops instantly to 0, "No GPS" in Mission Planner
- **Robot does automatically**: HOLD mode, paint off
- **What to do**: Press E-stop, check coax cable and SMA connector. Re-seat connection.

---

## 2. Motor Failures

### 2.1 Motor Stall (One or Both)
- **What you see**: Robot stops or turns in circles, motor whining sound, high current draw
- **Robot does automatically**: ArduRover detects no movement, may switch to HOLD
- **What to do**:
  1. Press E-stop immediately
  2. Check for debris caught in wheels
  3. Check if surface is too steep or soft (mud, gravel)
  4. Feel motors — if hot (>60C), let cool for 10 min
  5. Check motor current limit in hoverboard firmware (default 10A)

### 2.2 One Motor Dead
- **What you see**: Robot spins in circles, only one wheel moves
- **Robot does automatically**: Continues trying to navigate (will fail)
- **What to do**:
  1. Press E-stop
  2. Check UART cable from dead motor's hub to hoverboard PCB
  3. Check hoverboard PCB for error LED (usually red blink pattern)
  4. Swap motor hall sensor connectors to test if PCB or motor is faulty
  5. If PCB fault: flash backup hoverboard firmware

### 2.3 Hoverboard PCB Fault
- **What you see**: Both motors dead, beeping from PCB, or no response
- **Robot does automatically**: Can't move, paint should stop (speed < 0.1 m/s)
- **What to do**:
  1. Press E-stop
  2. Power cycle: disconnect battery, wait 10s, reconnect
  3. Check error LED pattern on PCB
  4. If persistent: re-flash FOC firmware via ST-Link
  5. Check power connections (36V supply, ground, phase wires)

### 2.4 UART Communication Loss
- **What you see**: Mission Planner shows "Bad AHRS" or motors freeze
- **Robot does automatically**: motor_bridge.lua detects timeout, sets zero speed
- **What to do**:
  1. Check SERIAL2 cable from Pixhawk to hoverboard PCB
  2. Verify baud rate: both sides must be 115200
  3. Check TX/RX aren't swapped (Pixhawk TX → hoverboard RX)
  4. Test with USB-TTL adapter to verify hoverboard responds

---

## 3. Paint Failures

### 3.1 Nozzle Clog
- **What you see**: Paint line becomes thin, spotty, or stops entirely
- **Robot does automatically**: Continues mission (no flow sensor)
- **What to do**:
  1. Pause mission (switch to HOLD via RC)
  2. Remove nozzle tip (TeeJet 8004), inspect for dried paint
  3. Soak in water/thinner for 5 min, clear with compressed air
  4. Carry spare nozzle tips in field kit
  5. **Prevention**: flush system with water after every job

### 3.2 Pump Failure
- **What you see**: No paint flow despite solenoid opening, pump not humming
- **Robot does automatically**: Continues mission (laying no paint)
- **What to do**:
  1. Check 12V supply to pump (test with multimeter)
  2. Check RELAY2_PIN output from Pixhawk relay board
  3. Listen for pump motor — if silent, relay or pump is dead
  4. Check inline fuse on pump power wire
  5. Carry a spare pump ($20) in field kit

### 3.3 Solenoid Stuck Open
- **What you see**: Paint sprays continuously, even during transit
- **Robot does automatically**: fence_check.lua kills relays on geofence breach
- **What to do**:
  1. Press E-stop (cuts all power)
  2. Check RELAY1_PIN output — if pin is LOW but solenoid is open, solenoid is failed
  3. Replace solenoid valve ($15)
  4. **Immediate**: manually close paint tank valve to stop flow

### 3.4 Solenoid Stuck Closed
- **What you see**: No paint despite mission commanding paint ON
- **Robot does automatically**: Continues mission (painting nothing)
- **What to do**:
  1. Check 12V supply to solenoid
  2. Check RELAY1_PIN output with multimeter (should be HIGH when painting)
  3. Manually energize solenoid to test (apply 12V directly)
  4. Check wiring from relay board to solenoid

### 3.5 Paint Tank Empty
- **What you see**: Lines become thin then stop, pump runs but no flow
- **Robot does automatically**: Continues mission
- **What to do**:
  1. Pause mission (HOLD mode)
  2. Refill tank (2-gallon capacity, ~3 gallons for a 20-space lot)
  3. Bleed air from pump/hose (run pump briefly with nozzle closed)
  4. Resume mission from current waypoint

### 3.6 Lines Too Wide/Narrow
- **What you see**: Paint lines are not the expected 4" width
- **Robot does automatically**: Nothing
- **What to do**:
  - **Too wide**: Increase speed (raise WP_SPEED), lower pump pressure, raise nozzle
  - **Too narrow**: Decrease speed, increase pump pressure, lower nozzle
  - Verify nozzle height is 50-70mm above ground
  - Check pump PSI (target: 60-80 PSI)

---

## 4. Power Failures

### 4.1 Battery Dead Mid-Job
- **What you see**: Everything shuts off suddenly, or low-voltage alarm beeps
- **Robot does automatically**: Pixhawk triggers RTL if battery failsafe configured
- **What to do**:
  1. Paint system stops (relays default off = safe)
  2. Carry charged backup battery
  3. Swap batteries (disconnect → connect, 30 seconds)
  4. Resume mission from last completed waypoint
  5. **Prevention**: monitor battery in telemetry, swap at 20%

### 4.2 DC-DC Converter Failure
- **What you see**: Pixhawk reboots (5V converter) or paint system dies (12V converter)
- **Robot does automatically**: Pixhawk on 5V failure: reboots, enters HOLD
- **What to do**:
  1. Check LED on DC-DC converter
  2. Measure input voltage (should be 33-42V) and output (5V or 12V)
  3. If failed: carry spares ($5 each), field-swap with screw terminals
  4. Check for overload (pump + solenoid > 3A on 12V converter?)

### 4.3 Brownout (Temporary Voltage Drop)
- **What you see**: Pixhawk brown-screen or reboots, motors glitch
- **Robot does automatically**: Pixhawk reboots, enters safe mode
- **What to do**:
  1. Check battery voltage under load (should be >33V)
  2. High current draw from motors on steep surface causes brownout
  3. Ensure DC-DC converters have capacitors on input
  4. Reduce motor current limit if needed

---

## 5. Communication Failures

### 5.1 RC Link Lost
- **What you see**: Mission Planner shows "No RC" or failsafe triggered
- **Robot does automatically**: Executes RC failsafe action (default: HOLD)
- **What to do**:
  1. Check RC transmitter is powered on
  2. Move closer (range: ~500m line of sight)
  3. Re-bind transmitter if necessary
  4. **Note**: Robot continues AUTO mission if RC failsafe = Continue

### 5.2 Telemetry Lost
- **What you see**: Mission Planner disconnects, no data updates
- **Robot does automatically**: Continues mission (telemetry is advisory only)
- **What to do**:
  1. Check telemetry radio power and antenna
  2. Move laptop closer to robot
  3. **Robot is still running its mission** — watch it visually
  4. Use RC to switch to HOLD if you need to stop it

### 5.3 Lua Script Crash
- **What you see**: Paint doesn't respond to mission commands, motors may stop
- **Robot does automatically**: Crashed script stops, others continue
- **What to do**:
  1. Check Mission Planner messages for "Lua:" error messages
  2. Land/stop the robot safely via RC
  3. Check SD card for script errors in logs
  4. Re-copy Lua scripts to SD card, power cycle

---

## 6. Navigation Failures

### 6.1 Waypoint Overshoot
- **What you see**: Robot drives past waypoints, makes wide turns
- **Robot does automatically**: Circles back to missed waypoint
- **What to do**:
  1. Reduce WP_SPEED (default 0.5 m/s should be fine)
  2. Increase WP_RADIUS if overshooting by small amounts
  3. Check motor PID tuning (too aggressive = overshoot)

### 6.2 Circular Looping
- **What you see**: Robot drives in circles at a waypoint
- **Robot does automatically**: Continues trying forever
- **What to do**:
  1. Switch to HOLD via RC immediately
  2. Usually caused by compass error or bad motor calibration
  3. Recalibrate compass away from metal
  4. Check motor direction (both should drive forward)

### 6.3 Wrong Heading
- **What you see**: Robot drives in unexpected direction
- **Robot does automatically**: ArduRover corrects heading using GPS
- **What to do**:
  1. Compass interference from motors or battery
  2. Move compass/Pixhawk farther from motors
  3. Run compass motor calibration (COMPASS_MOT)
  4. Verify declination is set correctly for your location

---

## 7. Safety Failures

### 7.1 E-Stop Triggered
- **What you see**: All motors stop, robot halts
- **Robot does automatically**: Power cut to motors via NC relay
- **What to do**:
  1. Identify why E-stop was pressed
  2. Clear hazard
  3. Release E-stop button (twist to reset)
  4. Re-arm in Mission Planner, resume mission

### 7.2 Geofence Breach
- **What you see**: "FENCE BREACH" in Mission Planner, robot stops
- **Robot does automatically**: RTL mode + paint off (fence_check.lua)
- **What to do**:
  1. Robot will return to launch point
  2. Check geofence polygon — too tight?
  3. Increase fence radius or redraw polygon
  4. Re-arm and resume from last waypoint

### 7.3 Obstacle Detected
- **What you see**: Robot stops, "OBSTACLE STOP" in telemetry
- **Robot does automatically**: HOLD mode + paint off (obstacle_avoid.lua)
- **What to do**:
  1. Remove obstacle (shopping cart, person, etc.)
  2. Robot auto-resumes when obstacle > 1.3m away
  3. If false positive: check sensor alignment, clean sensor face

---

## 8. Environmental

### 8.1 Rain Starts
- **What you do**: Pause mission immediately (HOLD via RC)
- **Why**: Paint won't adhere to wet surface, electronics not waterproof
- **Recovery**: Wait for surface to dry (2+ hours), resume from last waypoint

### 8.2 Wind Too Strong (>10 mph)
- **What you see**: Paint lines are offset or overspray visible
- **What to do**: Pause and wait for wind to calm. Lower nozzle closer to ground.

### 8.3 Temperature Extremes
- **Too cold (<50F)**: Paint won't cure properly. Wait for warmer weather.
- **Too hot (>90F)**: Paint dries too fast, nozzle clogs faster. Paint early morning.
- **Battery**: Li-ion performance degrades below 32F. Keep battery warm before use.
