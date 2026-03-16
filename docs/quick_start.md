# Striper Robot -- Quick Start Guide

Step-by-step guide from a box of parts to a robot painting its first parking
lot. This guide uses the validated BOM v3 (~$1,011 components, ~$1,200-$1,500 all-in).
See `docs/validated_bom_v3.md` for the full parts list.

Total estimated time: 2 weekends (20-25 hours of hands-on work).

> **Prefer a ready-to-run robot?** The assembled Strype robot ships
> pre-built, pre-flashed, pre-calibrated, and ready to paint in 30 minutes.
> See `docs/business-plan.md` for details on the assembled product vs. DIY.

**Tools required**: soldering iron, multimeter, hex key set (M3, M5), drill
with bits, wire strippers, crimping tool, screwdrivers (Phillips, flat),
tape measure, adjustable wrench, laptop with USB-C port.

**Software required**: Mission Planner (Windows), STM32CubeProgrammer,
hoverboard-firmware-hack-FOC source code and build toolchain
(STM32CubeIDE or PlatformIO).

---

## Weekend 1: Build the Hardware

### Step 1: Unbox and Inventory Check (30 minutes)

Verify every item from the Tier 2 BOM (see `docs/bom.md`). Lay everything
out on a workbench and check off:

| # | Item | Check |
|---|------|-------|
| 1 | Used hoverboard (two 350W hub motors + mainboard + battery) | [ ] |
| 2 | ST-Link V2 programmer | [ ] |
| 3 | 2020 aluminum extrusion (500mm lengths, 4-6 pieces) + corner brackets + T-nuts + M5 screws | [ ] |
| 4 | 3/4" plywood (24"x18" or sized to match frame) | [ ] |
| 5 | Pixhawk 6C Mini | [ ] |
| 6 | Unicore UM982 breakout + 2x multiband GNSS antennas (L1/L2 minimum, dual-antenna heading) | [ ] |
| 7 | Shurflo 8000 diaphragm pump (12V, 60 PSI, 1.8 GPM) | [ ] |
| 8 | 12V solenoid valve (N.C., 3/8" NPT, brass, direct-acting) | [ ] |
| 9 | TeeJet TP8004EVS even-fan nozzle + 60-mesh strainer + adapters + 3 ft 3/8" tubing | [ ] |
| 10 | 36V 18Ah e-bike battery with charger | [ ] |
| 11 | DC-DC converter 36V to 12V (5A minimum, XL4015) | [ ] |
| 12 | Holybro PM06 V2 power module (5V/3A + battery monitoring) | [ ] |
| 13 | E-stop button (22mm mushroom, twist-release, N.C.) + 40A DC contactor | [ ] |
| 14 | 2x HC-SR04 ultrasonic sensors | [ ] |
| 15 | FlySky FS-i6X transmitter + FS-iA6B receiver | [ ] |
| 16 | 2-channel 5V relay module (opto-isolated) | [ ] |
| 17 | Wiring kit: 14/18/22 AWG wire, XT60 connectors, 30A fuse + holder, JST-GH cables, M3 standoffs, zip ties, heat shrink | [ ] |
| 18 | 2x front casters (swivel, 3") | [ ] |
| 19 | 1N4007 diodes (2x, for flyback protection) | [ ] |

Missing anything? Order before proceeding. Do not substitute the GPS module
or Pixhawk without updating the parameter file.

### Step 2: Frame Assembly (2-3 hours)

Build the frame that holds everything together. The frame must be rigid
enough to maintain wheel alignment.

1. Cut 2020 aluminum extrusion to length (if not pre-cut):
   - 2x 500mm side rails
   - 2x 350mm cross members (front and rear)
   - Optional: 2x 200mm uprights for electronics shelf
2. Assemble the rectangular frame using corner brackets and M5 screws
   into T-nuts
3. Cut the plywood deck to fit the top of the frame. Drill mounting holes.
   Screw the deck to the extrusion using M5 bolts into T-nuts
4. Mount the two front casters to the front of the frame (underside of
   plywood). The robot drives with the hoverboard wheels at the rear and
   casters at the front
5. Verify the frame sits level on a flat surface with all four wheels
   (two casters + two hoverboard wheels) touching

**Tip**: leave the rear cross member loose or removable -- you will need to
slide the hoverboard wheels into position.

### Step 3: Motor Mounting and Wiring (2-3 hours)

1. Disassemble the hoverboard:
   - Remove the outer shell (screws on the bottom)
   - Disconnect the two hub motor wheels from the mainboard
   - Remove the mainboard from the hoverboard chassis
   - Save the original battery (useful for bench testing)
   - Save all motor connectors and cables
2. Mount the two hub motor wheels to the rear of the frame:
   - The hoverboard wheel axles typically use 8mm bolts
   - Use L-brackets or custom mounting plates to secure the axles to the
     aluminum extrusion
   - Both wheels must be parallel and at the same height
   - **Measure and record the wheel center-to-center distance** (track
     width). This goes into `WHL_TRACK` in the parameter file. Typical
     hoverboard: 0.40-0.45m
3. Mount the hoverboard mainboard to the frame deck, at least 15cm from
   the hub motors (to reduce electromagnetic interference). Use M3 standoffs to
   elevate it off the deck for airflow
4. Reconnect motor phase wires (3 wires per motor: typically yellow, blue,
   green) and hall sensor cables (5-pin JST-XH) to the mainboard

**Do not connect the battery yet.**

### Step 4: Flash Hoverboard FOC Firmware (1-2 hours)

The hoverboard mainboard ships with the original hoverboard firmware. You
must replace it with the open-source FOC firmware that accepts UART speed
commands.

1. Download hoverboard-firmware-hack-FOC from
   https://github.com/EFeru/hoverboard-firmware-hack-FOC
2. Read the wiki for your specific mainboard variant (split board vs single
   board). Identify the SWD pads (SWDIO, SWCLK, GND, 3.3V)
3. Edit `config.h`:
   - Set the UART input mode (uncomment `CONTROL_SERIAL_USART2` or the
     appropriate UART for your board variant)
   - Set baud rate to 115200
   - Set the UART protocol to the hoverboard protocol (start frame
     0xABCD) -- this is the default
   - Adjust speed limits if desired (default is fine for initial testing)
   - Set `SPEED_COEFFICIENT` and `STEER_COEFFICIENT` to 1.0 for a
     starting point
4. Build the firmware using STM32CubeIDE or PlatformIO
5. Connect the ST-Link V2 to the mainboard SWD pads:
   - SWDIO to SWDIO
   - SWCLK to SWCLK
   - GND to GND
   - 3.3V to 3.3V (or power the mainboard from its battery)
6. Open STM32CubeProgrammer, connect to the target, and flash the
   compiled .bin file
7. After flashing, disconnect the ST-Link

### Step 5: Bench-Test Motors (30 minutes)

Test the motors before integrating with the Pixhawk.

1. Connect the hoverboard battery (or the 36V e-bike battery) to the
   mainboard
2. Connect a USB-to-serial adapter (3.3V level) to the mainboard UART
   pads (TX, RX, GND)
3. Open a serial terminal at 115200 baud
4. Send a test command using the hoverboard protocol:
   - Start frame: 0xCD 0xAB
   - Steer: 0x00 0x00 (no turn)
   - Speed: 0x64 0x00 (speed = 100, slow)
   - Checksum: XOR of the above
5. Both wheels should spin forward slowly
6. Send speed = 0 to stop
7. Try negative speed to verify reverse
8. Try steer commands to verify differential turning
9. Disconnect the serial adapter

**If wheels spin the wrong direction**: swap any two of the three phase wires
on that motor (at the mainboard connector).

### Step 6: Power System Wiring (1-2 hours)

Wire the power distribution system. Refer to `docs/wiring_guide.md` Section
2.

1. Mount the 36V e-bike battery to the frame (use velcro straps or a
   battery tray). Position for best center of gravity
2. Wire the battery positive through the 30A inline fuse holder
3. Wire the fuse output through the DC contactor N.O. contacts. Wire the
   contactor coil: positive to fused battery, negative through the E-stop
   N.C. contacts to GND
4. From the contactor output, create a power distribution point (terminal
   block or solder junction):
   - Run 12 AWG to the hoverboard mainboard VCC input
   - Run 18 AWG to the 36V-to-12V DC-DC converter input
   - Run 18 AWG to the Holybro PM06 V2 input
5. Connect all grounds to a common ground bus (terminal block or solder
   junction)
6. **Before connecting anything to the outputs**: power on and verify
   DC-DC converter outputs with a multimeter:
   - 12V converter: 11.5-12.5V
   - 5V BEC: 4.8-5.2V
7. Test the E-stop: with motors spinning (UART command from laptop), press
   the E-stop. Motors must stop immediately. Twist to release and verify
   power returns

### Step 7: Mount Pixhawk and GPS (1 hour)

1. Mount the Pixhawk 6C Mini on the frame deck using vibration-dampening
   foam or M3 standoffs with silicone grommets. Position it:
   - Flat and level (arrow pointing forward)
   - At least 15cm from the hub motors
   - Away from the hoverboard mainboard power traces
2. Connect the 5V BEC to the Pixhawk POWER port (JST-GH 6-pin cable).
   Pin 1 = VCC (5V), Pin 6 = GND
3. Power on. Verify Pixhawk boots: LED goes through startup sequence and
   settles on a pattern (likely flashing yellow = no GPS)
4. Mount the UM982 GPS breakout board near the Pixhawk
5. Connect the UM982 to Pixhawk using **two serial ports**:
   - **SERIAL3 (GPS1)** — position: Pixhawk TX (pin 2) to UM982 Port 1 RX,
     Pixhawk RX (pin 3) to UM982 Port 1 TX, GND (pin 6) to GND,
     VCC (pin 1, 5V) to UM982 VCC
   - **SERIAL4 (GPS2)** — heading: Pixhawk TX (pin 2) to UM982 Port 2 RX,
     Pixhawk RX (pin 3) to UM982 Port 2 TX, GND (pin 6) to GND
6. Mount **both** GNSS antennas on the highest point of the robot, separated
   by at least 20cm (larger baseline = better heading accuracy). Clear
   360-degree sky view for both
7. Connect the antennas to the UM982 breakout SMA connectors
8. If you have ground plane discs (100mm aluminum), mount them under each
   antenna

---

## Weekend 1, Afternoon: Firmware and Configuration

### Step 8: Flash ArduRover Firmware (30 minutes)

1. Connect the Pixhawk to your laptop via USB-C
2. Open Mission Planner and connect (AUTO baud, the correct COM port)
3. Go to Setup > Install Firmware
4. Select **Rover** and install the latest stable version (4.5+)
5. Wait for the flash to complete and the Pixhawk to reboot
6. Reconnect in Mission Planner

### Step 9: Load Parameters (15 minutes)

1. In Mission Planner, go to Config > Full Parameter List
2. Click "Load from File"
3. Select `ardurover/params/striper.param` from this repository
4. Click "Write Params"
5. The Pixhawk will reboot after writing critical parameters
6. Reconnect and verify key parameters loaded:
   - `FRAME_TYPE` = 2 (skid steer)
   - `SERIAL2_PROTOCOL` = 28 (Scripting)
   - `GPS_TYPE` = 25 (UnicoreMovingBaselineNMEA / UM982)
   - `SCR_ENABLE` = 1
7. Update `WHL_TRACK` to match your measured track width (default 0.40m)

### Step 10: Install Lua Scripts (10 minutes)

1. Power off the Pixhawk
2. Remove the microSD card from the Pixhawk
3. Insert it into your laptop
4. Create the folder `/APM/scripts/` if it does not exist
5. Copy these four files from `ardurover/lua/` in this repository:
   - `motor_bridge.lua`
   - `paint_control.lua`
   - `paint_speed_sync.lua`
   - `fence_check.lua`
6. Eject the SD card and re-insert it into the Pixhawk
7. Power on the Pixhawk and connect in Mission Planner
8. In the Messages tab, verify all four scripts loaded:
   - "motor_bridge.lua loaded - hoverboard FOC UART bridge"
   - "paint_control.lua loaded"
   - "paint_speed_sync.lua loaded"
   - "fence_check.lua loaded"

### Step 11: Wire and Bind RC Transmitter (30 minutes)

1. Wire the FlySky FS-iA6B receiver to the Pixhawk RC IN port:
   - SBUS/IBUS signal wire to Pixhawk RC IN signal pin
   - VCC (5V) to Pixhawk RC IN VCC
   - GND to Pixhawk RC IN GND
2. Bind the transmitter to the receiver:
   - Power off the receiver
   - Hold the bind button on the receiver
   - Power on the receiver (while holding bind button) -- bind LED flashes
   - Put the FS-i6X transmitter in bind mode (long press on the power
     button, or use the menu: System > RX Bind)
   - Bind LED on receiver goes solid = bound successfully
3. In Mission Planner, go to Setup > Mandatory Hardware > Radio Calibration
4. Move all sticks and switches. Verify all channels respond
5. Click "Calibrate Radio" and follow the instructions (move sticks to
   full extents)
6. Set up switches on the FS-i6X:
   - CH5 (SwC): flight mode switch (3-position: MANUAL / HOLD / AUTO)
   - CH6 (SwD): motor emergency stop
   - CH7 (SwA): paint solenoid toggle
   - CH8 (SwB): pump toggle

### Step 12: Verify UM982 Heading in Mission Planner (15 minutes)

Compass is disabled (`COMPASS_ENABLE=0`) because hub motor magnets cause
overwhelming magnetic interference. The UM982 dual-antenna GPS provides
heading instead.

1. Take the robot outdoors, away from vehicles, buildings, and metal
   structures (at least 10 meters clear)
2. In Mission Planner, verify both GNSS antennas have satellite lock
   (GPS status should show 3D Fix or better)
3. Check the heading readout in Mission Planner's HUD -- it should match
   the robot's actual forward direction
4. Verify `EK3_SRC1_YAW=2` (GPS heading) in the parameter list
5. Wait for the "EKF yaw alignment complete" message in the Messages tab
6. UM982 heading works at standstill -- no need to walk the robot in a
   circle to initialize yaw (unlike the old GSF approach with UM980)

**If heading is wrong or erratic**: check both antenna connections, verify
antenna baseline separation (minimum 20cm), and ensure both antennas have
clear sky view.

### Step 13: Motor Direction Test (15 minutes)

1. Put the robot on blocks (wheels off the ground) or prop it up so
   wheels spin freely
2. Connect the hoverboard UART to Pixhawk SERIAL2:
   - Pixhawk TX (pin 2) to hoverboard RX
   - Pixhawk RX (pin 3) to hoverboard TX
   - Pixhawk GND (pin 6) to hoverboard GND
3. Switch the RC transmitter to MANUAL mode (CH5 switch position 1)
4. Arm the robot (throttle down + rudder right for 5 seconds, or use
   Mission Planner Arm button)
5. Push throttle stick forward gently -- both wheels should spin forward
   (same direction the robot would drive)
6. Push steering right -- the robot should turn right (left wheel forward,
   right wheel back or slower)

**If a motor spins the wrong way**: either swap two motor phase wires at
the mainboard, or set `SERVO1_REVERSED=1` or `SERVO3_REVERSED=1` in
the parameter file.

### Step 14: First Drive Test -- Manual RC Control (30 minutes)

1. Place the robot on flat, open pavement (empty parking lot or driveway)
2. Stand behind the robot with the RC transmitter
3. Switch to MANUAL mode (CH5)
4. Arm the robot
5. Gently push throttle forward -- the robot should drive forward
6. Test steering: left and right turns
7. Test reverse
8. Test stopping (release throttle)
9. Test the E-stop: while driving, press the E-stop. Robot must stop
   instantly
10. Adjust if needed:
    - If steering is reversed: `RCMAP_ROLL` or `RC1_REVERSED`
    - If throttle is reversed: `RCMAP_THROTTLE` or `RC3_REVERSED`
    - If the robot is too fast in manual: reduce `CRUISE_SPEED`
    - If turns are too aggressive: increase `ATC_TURN_MAX_G`

---

## Weekend 2: GPS, Paint, and First Mission

### Step 15: GPS Test -- Achieve RTK Fix (1-2 hours)

This step may take some time depending on your RTK correction source setup.

1. Take the robot outdoors with clear sky view
2. Power on and connect Mission Planner
3. Watch the GPS status in Mission Planner (HUD, bottom bar):
   - "No GPS" = wiring issue or module not detected. Check SERIAL3 wiring
   - "No Fix" = module working but no satellite lock. Wait 30-60 seconds
   - "3D Fix" = autonomous fix, 1-3m accuracy. This is your baseline
   - "RTK Float" = receiving corrections but not fully resolved. Wait
   - "RTK Fixed" = full RTK, 8mm accuracy. This is the target
4. To get RTK corrections, set up one of these:
   - **NTRIP via Mission Planner**: in Mission Planner, go to Setup >
     Optional Hardware > RTK/GPS Inject. Enter your NTRIP caster URL,
     port, mountpoint, and credentials (e.g., RTK2Go free service). Click
     Connect. Mission Planner will relay RTCM3 corrections to the Pixhawk
   - **Own base station**: set up a second GPS receiver at a known point,
     configure it to output RTCM3, and connect via a telemetry radio
   - **PointPerfect/Polaris**: commercial service, configure per their
     documentation
5. With corrections flowing, the GPS should converge to RTK Fixed within
   1-5 minutes
6. Walk around the robot and verify the position dot in Mission Planner
   tracks your movement smoothly

**If you cannot get RTK**: the robot will still work with 3D Fix, but line
accuracy will be 1-3 meters instead of 8mm. This is not usable for real
striping work but is fine for testing navigation.

### Step 16: Paint System Assembly (1-2 hours)

1. Mount the 12V solenoid valve and diaphragm pump to the frame deck:
   - Pump input (suction side) faces the paint reservoir
   - Pump output (pressure side) goes to the solenoid valve input
   - Solenoid valve output goes to the nozzle
2. Connect tubing:
   - Paint reservoir (container with lid) to pump input via 1/2" vinyl
     tubing with hose clamp
   - Pump output to solenoid input via 1/2" vinyl tubing
   - Solenoid output to nozzle body via 1/2" vinyl tubing
   - Nozzle body mounted pointing straight down, 6-8 inches above ground
3. Wire the relay module:
   - Relay VCC to 5V BEC output
   - Relay GND to common ground
   - Relay CH1 IN to Pixhawk AUX5 (pin 54) signal wire
   - Relay CH2 IN to Pixhawk AUX6 (pin 55) signal wire
4. Wire the solenoid through relay CH1:
   - Relay CH1 COM to 12V DC-DC output (+)
   - Relay CH1 N.O. to solenoid terminal 1
   - Solenoid terminal 2 to 12V DC-DC output (-) / GND
   - Solder a 1N4007 flyback diode across the solenoid terminals (cathode
     to positive, anode to negative)
5. Wire the pump through relay CH2:
   - Same pattern as solenoid but on relay CH2
   - Add a 1N4007 flyback diode across pump terminals
6. Verify parameters: `RELAY1_PIN=54`, `RELAY2_PIN=55`,
   `RELAY1_DEFAULT=0`, `RELAY2_DEFAULT=0`

### Step 17: Paint System Test -- Bench Test with Water (30 minutes)

Do NOT use paint yet. Test with clean water first.

1. Fill the paint reservoir with clean water
2. Power on the robot
3. In Mission Planner, go to Setup > Optional Hardware > Relay
4. Toggle Relay 2 (pump) ON -- listen for the pump motor, verify water
   flows from reservoir through the system
5. Toggle Relay 1 (solenoid) ON -- water should spray from the nozzle
6. Check spray pattern: should be a flat fan, approximately 4" wide at
   6-8 inches from the ground
7. Toggle Relay 1 OFF -- spray should stop immediately (within 50ms)
8. Toggle Relay 2 OFF -- pump stops
9. Test via RC: toggle CH7 (paint solenoid) and CH8 (pump) on the
   transmitter
10. Check for leaks at all tubing connections. Tighten hose clamps as
    needed
11. Adjust nozzle height if the spray pattern is too wide or too narrow

### Step 18: First Autonomous Mission -- Small Test Pattern (1-2 hours)

The moment of truth. Start with a simple pattern, no paint.

1. Go to a flat, open parking lot with good sky view
2. Set up the robot and achieve RTK Fixed GPS
3. In Mission Planner, go to Plan
4. Create a simple mission:
   - Waypoint 1: starting position
   - Waypoint 2: 5 meters straight ahead
   - Waypoint 3: 5 meters to the right (a simple L-shape)
   - Waypoint 4: back to start
5. Upload the mission to the Pixhawk
6. Draw a geofence polygon around the work area (at least 5 meters
   margin beyond all waypoints). Upload the fence
7. Switch to HOLD mode, arm the robot
8. Stand back with the RC transmitter ready (thumb on mode switch)
9. Switch to AUTO mode -- the robot should start driving toward WP1
10. Watch the robot navigate the mission:
    - Does it drive straight between waypoints?
    - Does it turn at the correct points?
    - Does it stay on the planned path?
    - Does it stop at the end of the mission?
11. If the robot veers off course:
    - Switch to MANUAL immediately and steer to safety
    - Check UM982 heading vs actual heading
    - Check PID tuning (see `docs/troubleshooting.md`)
12. Run the mission 3-5 times until navigation is consistent

### Step 19: First Autonomous Paint Mission -- Test with Water (1 hour)

Now add paint commands to the mission (still using water).

1. Edit the mission in Mission Planner:
   - Between WP1 and WP2, add `DO_SET_RELAY(0,1)` (paint on) and
     `DO_SET_RELAY(1,1)` (pump on)
   - After WP2, add `DO_SET_RELAY(0,0)` (paint off) and
     `DO_SET_RELAY(1,0)` (pump off)
   - This paints a line from WP1 to WP2, then transits to WP3 dry
2. Fill reservoir with water
3. Run the mission
4. Verify:
   - Water sprays between WP1 and WP2 only
   - No spraying during transit segments
   - Clean start and stop of spray at waypoints
   - paint_control.lua lead/lag compensation produces clean line ends
5. Measure the water line on the ground:
   - Width should be approximately 4" (from TeeJet TP8004EVS)
   - Line should be straight (no S-curves or wobble)
   - Start and end points should be clean (no pooling or drips)

### Step 20: First Real Parking Lot Job (2-4 hours)

You are ready for paint. Start with a small job (5-10 spaces).

1. **Survey the lot**:
   - Walk the lot and identify all lines to be painted
   - Note obstacles (curbs, drains, bollards, light poles)
   - Note multipath risk areas (near buildings, large metal surfaces)
   - Measure a reference distance (e.g., one parking space width) to
     verify GPS accuracy on-site

2. **Generate the mission**:
   - Use `scripts/pathgen_cli.py` to generate waypoints for the lot layout
   - Or manually create the mission in Mission Planner
   - Include `DO_SET_RELAY` commands to toggle paint at line start/end
   - Save the mission file

3. **Set up on-site**:
   - Position the robot at the starting point
   - Achieve RTK Fixed GPS
   - Upload the mission and geofence
   - Fill the reservoir with traffic paint (strained through 60-mesh
     filter). Estimate: ~350 linear feet per gallon for 4" lines
   - Prime the pump with paint (run briefly until paint reaches the nozzle)
   - Test spray pattern with one short burst

4. **Run the job**:
   - Arm, switch to AUTO
   - Monitor from 10-20 meters away with the RC transmitter
   - Watch for: straight lines, correct paint width, clean start/stop,
     no overshoot at turns
   - Be ready to switch to MANUAL or hit E-stop at any moment

5. **Post-job**:
   - Walk the lot and inspect all painted lines
   - Note any quality issues for parameter tuning
   - Follow the post-job checklist (`docs/maintenance.md` Section 2)

---

## Time Estimate Summary

| Step | Task | Time |
|------|------|------|
| 1 | Unbox and inventory | 30 min |
| 2 | Frame assembly | 2-3 hrs |
| 3 | Motor mounting and wiring | 2-3 hrs |
| 4 | Flash hoverboard FOC firmware | 1-2 hrs |
| 5 | Bench-test motors | 30 min |
| 6 | Power system wiring | 1-2 hrs |
| 7 | Mount Pixhawk and GPS | 1 hr |
| **Weekend 1 subtotal** | | **8-12 hrs** |
| 8 | Flash ArduRover firmware | 30 min |
| 9 | Load parameters | 15 min |
| 10 | Install Lua scripts | 10 min |
| 11 | RC transmitter binding and channel setup | 30 min |
| 12 | Verify UM982 heading | 15 min |
| 13 | Motor direction test | 15 min |
| 14 | First drive test (manual RC) | 30 min |
| 15 | GPS test (achieve RTK fix) | 1-2 hrs |
| 16 | Paint system assembly | 1-2 hrs |
| 17 | Paint system test (water) | 30 min |
| 18 | First autonomous mission (no paint) | 1-2 hrs |
| 19 | First autonomous paint mission (water) | 1 hr |
| 20 | First real parking lot job | 2-4 hrs |
| **Weekend 2 subtotal** | | **8-13 hrs** |
| **Total** | | **16-25 hrs** |

---

## Common First-Build Issues

| Problem | Likely Cause | Quick Fix |
|---------|-------------|-----------|
| Pixhawk does not boot | 5V BEC output wrong voltage or not connected | Measure BEC output with multimeter. Must be 4.8-5.2V |
| No GPS satellites | Antenna not connected or has no sky view | Check SMA connector. Move outdoors, clear of overhead cover |
| Motors do not respond | UART wiring wrong, SERIAL2_PROTOCOL not set to 28, or Lua scripts not loaded | Check TX/RX crossover, check parameters, check SD card |
| Robot drives backward | Motor phase wires swapped or SERVO_REVERSED wrong | Swap two phase wires, or set SERVO1_REVERSED=1 |
| Robot turns wrong way | Steering channel reversed or left/right motors swapped | Set RC1_REVERSED or swap motor connectors |
| Relay does not click | 5V not reaching relay module, or signal wire disconnected from AUX5/AUX6 | Check relay VCC, GND, and signal connections |
| Cannot arm | Pre-arm checks failing | Read the pre-arm failure message in Mission Planner HUD. Most common: GPS no fix, UM982 heading not converged, battery voltage too low |
| RC transmitter not bound | Binding procedure not completed | Re-do binding: hold bind button on receiver during power-on, then bind from transmitter menu |

---

## What Is Next

After your first successful job:

1. **Tune PIDs**: drive several test patterns and adjust `ATC_STR_RAT_P`,
   `ATC_STR_RAT_I`, `ATC_SPEED_P`, and `ATC_SPEED_I` for tighter line
   tracking
2. **Optimize speed**: gradually increase `WP_SPEED` from 0.50 to 0.75 m/s
   as navigation quality allows, to paint lots faster
3. **Generate complex missions**: use `scripts/pathgen_cli.py` with
   templates for standard lot layouts (parallel rows, angled spaces, handicap
   markings)
4. **Add telemetry radio**: a SiK 915MHz radio lets you monitor from your
   vehicle instead of standing with the laptop
5. **Calibrate paint**: adjust nozzle height, pump pressure, and robot speed
   to achieve consistent line width and coverage
6. **Build a spare parts kit**: see `docs/maintenance.md` for the
   recommended field spares list
