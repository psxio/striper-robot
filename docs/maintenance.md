# Striper Robot -- Maintenance Guide

Complete maintenance checklists for the autonomous parking lot line striper.
Following these procedures will prevent most field failures and extend the
life of all components.

Hardware reference: Pixhawk 6C Mini, Unicore UM980 GPS, hoverboard hub motors
(350W x2) with FOC firmware, 36V 10Ah e-bike battery, 12V diaphragm pump +
solenoid valve + TeeJet 8004 nozzle, FlySky FS-i6X RC.

---

## 1. Pre-Job Checklist (Before Every Use)

Run through this list before leaving for the job site. Estimated time: 15-20
minutes.

### 1.1 Power System

- [ ] Battery fully charged (42.0V at rest for 10S lithium-ion)
- [ ] Battery securely mounted to frame, XT60 connector seated firmly
- [ ] E-stop button released (twist to reset) and functional -- press to
      verify power cuts, then release
- [ ] 30A blade fuse intact (visual inspection through clear holder)
- [ ] DC-DC converter outputs verified with multimeter: 12V rail reads
      11.5-12.5V, 5V rail reads 4.8-5.2V

### 1.2 Electronics

- [ ] Pixhawk boots normally (green LED after startup sequence)
- [ ] GPS antenna SMA connector hand-tight, cable routed without kinks
- [ ] GPS achieves 3D Fix within 60 seconds (full RTK fix not needed yet,
      just confirm module is working)
- [ ] RC transmitter powered on, bound to receiver (solid LED on receiver)
- [ ] RC stick inputs visible in Mission Planner Radio Calibration page
- [ ] Flight mode switch (CH5) toggles between MANUAL / HOLD / AUTO
- [ ] SD card inserted in Pixhawk (Lua scripts will not load without it)
- [ ] GCS messages show all four Lua scripts loaded:
  - `motor_bridge.lua loaded`
  - `paint_control.lua loaded`
  - `paint_speed_sync.lua loaded`
  - `fence_check.lua loaded`

### 1.3 Motors

- [ ] Both wheels spin freely by hand (no grinding, no binding)
- [ ] Motor phase wires secure at mainboard connectors
- [ ] Hall sensor cables connected at both motor and mainboard ends
- [ ] UART cable from Pixhawk SERIAL2 to hoverboard mainboard connected
      (TX/RX/GND, JST-GH secure)
- [ ] In MANUAL mode, both wheels respond to RC throttle and steering
- [ ] Motor direction correct: throttle forward drives robot forward, steering
      right turns robot right

### 1.4 Paint System

- [ ] Paint reservoir filled and strained through 60-mesh filter
- [ ] Pump primed (run briefly with solenoid open until steady flow)
- [ ] Solenoid clicks when toggled via RC (CH7) -- listen for relay click
- [ ] Spray pattern tested with short burst: clean 4" fan, no drips, no
      deflection
- [ ] Nozzle height set correctly (TeeJet 8004 at 6-8 inches from ground)
- [ ] All tubing connections tight (no leaks at barb fittings)
- [ ] Flyback diodes installed across solenoid and pump (visual check)

### 1.5 Frame and Mechanical

- [ ] Frame bolts and screws tight (spot check 5-6 critical fasteners)
- [ ] Caster wheels spin freely, swivel plates not binding
- [ ] All cables zip-tied to frame, no loose wires near wheels
- [ ] No visible damage from previous use (bent frame, cracked plywood)

### 1.6 Mission

- [ ] Mission file loaded in Mission Planner and uploaded to Pixhawk
- [ ] Geofence polygon uploaded and encompasses all waypoints plus 2m margin
- [ ] Paint usage estimated (350 linear feet per gallon for 4" lines)
- [ ] Sufficient paint loaded for the job plus 20% margin

---

## 2. Post-Job Checklist (After Every Use)

Do this immediately after completing the job, before loading the robot into
your vehicle. Estimated time: 20-30 minutes.

### 2.1 Paint System Flush (Critical)

This is the single most important maintenance task. Dried paint in the system
causes clogs and kills pumps.

1. Empty remaining paint from the reservoir back into the paint container
   (strain it for reuse)
2. Fill the reservoir with warm water
3. Run the pump with solenoid open for 60 seconds, flushing water through
   the entire system (pump, tubing, solenoid, nozzle)
4. Repeat step 2-3 with clean water until the output runs clear
5. Remove the nozzle tip and inspect the orifice -- clear any residue with
   the cleaning pin
6. Leave the solenoid open (de-energized, N.C. closes on its own) to prevent
   paint drying in the valve seat
7. Wipe down the nozzle bracket and any paint drips on the frame

### 2.2 Battery

- [ ] Note remaining voltage in Mission Planner before disconnecting
- [ ] Disconnect battery (pull XT60 connector)
- [ ] Charge the battery to full (42.0V) if using again within the next week
- [ ] If storing for more than a week, charge to storage voltage (see
      Section 6)

### 2.3 Electronics

- [ ] Download dataflash log from Pixhawk SD card (for post-mission
      analysis and troubleshooting)
- [ ] Check SD card free space -- clear old logs if below 500MB
- [ ] Power off RC transmitter to save batteries

### 2.4 Mechanical

- [ ] Inspect wheels for embedded debris (rocks, glass, staples)
- [ ] Inspect tires for cuts or flat spots
- [ ] Check hub motor axle bolts for looseness
- [ ] Wipe down the frame, removing paint drips and road grime

### 2.5 Documentation

- [ ] Note any issues encountered during the job (GPS problems, paint
      quality issues, waypoint misses) in a job log
- [ ] Note the lot layout and any special considerations for future re-stripe
      jobs at the same location
- [ ] Save the mission file with the job name and date

---

## 3. Weekly Maintenance (If Used Regularly)

Perform these tasks once per week when the robot is in regular use (2+ jobs
per week). Estimated time: 30-45 minutes.

### 3.1 Electrical Connections

- [ ] Inspect all wire connections at the power distribution point (terminal
      block or solder joints) -- look for discoloration, corrosion, or
      looseness
- [ ] Check all JST-GH connectors on the Pixhawk -- gently tug each cable to
      verify retention
- [ ] Inspect the relay module: check for burn marks on relay contacts,
      verify opto-isolator LEDs work
- [ ] Inspect flyback diodes across solenoid and pump -- verify they are not
      cracked or dislodged

### 3.2 Motor System

- [ ] Inspect hoverboard mainboard for swollen capacitors, darkened MOSFETs,
      or loose solder joints
- [ ] Check motor phase wires at the mainboard solder points -- re-solder
      any cold joints
- [ ] Check hall sensor cable connectors for corrosion or bent pins
- [ ] Spin each wheel by hand and listen for bearing noise (grinding,
      clicking, or roughness indicates bearing wear)

### 3.3 Frame

- [ ] Torque-check all frame bolts (aluminum extrusion corner brackets,
      plywood deck screws, motor mounting bolts)
- [ ] Check caster wheel axle bolts and swivel bearings
- [ ] Inspect for frame cracks, especially around motor mounting points

### 3.4 GPS Antenna

- [ ] Inspect SMA connector for corrosion or looseness
- [ ] Inspect cable for cuts, kinks, or abrasion against frame edges
- [ ] Clean the antenna element surface (wipe with damp cloth -- no
      solvents)
- [ ] Verify ground plane disc (if installed) is securely mounted

### 3.5 Firmware and Software

- [ ] Check ArduRover firmware version against latest stable release
      (ardupilot.org/rover)
- [ ] Review Lua scripts on SD card -- verify all four files are present
      and have correct file sizes (not 0 bytes)
- [ ] Back up the current parameter file from Mission Planner (Full
      Parameter List > Save to File)

---

## 4. Monthly Maintenance

Perform these tasks once per month during the operating season. Estimated
time: 1-2 hours.

### 4.1 Deep Clean

- [ ] Remove all electronics from the frame
- [ ] Clean the frame thoroughly with soap and water
- [ ] Clean paint residue from nozzle bracket, tubing clamps, and frame
      underside
- [ ] Inspect all wiring for chafing, especially where wires pass through
      holes or run along frame edges
- [ ] Replace any zip ties that are cracked, sun-bleached, or cutting into
      wire insulation

### 4.2 Paint System Deep Clean

- [ ] Disassemble the paint system: disconnect tubing at all joints
- [ ] Soak the solenoid valve body in warm water + paint thinner for 30
      minutes, then flush with clean water
- [ ] Soak the pump head (disconnect from motor if possible) in warm water
- [ ] Replace any tubing sections that are stiff, discolored, or have
      internal paint buildup
- [ ] Inspect the TeeJet nozzle tip under magnification -- replace if the
      orifice is worn or chipped (replace every 3-6 months with regular use)

### 4.3 Compass Recalibration

- [ ] Perform a full compass calibration outdoors, away from vehicles and
      metal structures
- [ ] Rotate the robot through all orientations (figure-8 in three axes)
- [ ] Verify compass heading matches a known reference (smartphone compass
      or physical landmark)
- [ ] Run compass motor compensation: `COMPASS_MOT_TYPE=2`, follow Mission
      Planner compass-mot wizard

### 4.4 Accelerometer Calibration

- [ ] Level the robot on a known flat surface
- [ ] Perform accelerometer calibration in Mission Planner (Mandatory
      Hardware > Accel Calibration)

### 4.5 RC Transmitter

- [ ] Replace transmitter batteries (4x AA)
- [ ] Verify all channel endpoints and trims in Mission Planner Radio
      Calibration
- [ ] Check switch assignments (CH5 flight mode, CH6 E-stop, CH7 paint,
      CH8 pump)

### 4.6 Battery Health Check

- [ ] Fully charge the battery, then measure resting voltage of each cell
      group if possible (balanced = all cells within 0.05V)
- [ ] Note the total charge capacity accepted vs rated capacity -- if less
      than 70% of rated (e.g., less than 7Ah for a 10Ah pack), the battery
      is nearing end of life
- [ ] Inspect battery pack for swelling, unusual warmth, or damaged
      wrapping
- [ ] Clean battery contacts (XT60 connector pins) with contact cleaner

---

## 5. Seasonal Storage

When storing the robot for more than 2 weeks (off-season, winter, or between
project phases).

### 5.1 Paint System

1. Perform a complete flush (Section 2.1) with warm water
2. After flushing, run a small amount of propylene glycol (RV antifreeze)
   through the system if storing in freezing temperatures -- this prevents
   ice damage to the pump diaphragm and solenoid
3. Remove the nozzle tip and store it in a sealed bag
4. Leave all tubing disconnected and open to air dry

### 5.2 Battery Storage

1. Charge the battery to storage voltage: 3.7-3.8V per cell = 37-38V for
   the 10S pack (NOT fully charged, NOT fully empty)
2. Disconnect the battery from the robot (pull XT60)
3. Store the battery indoors at room temperature (60-75 degrees F /
   15-24 degrees C)
4. Never store below 32 degrees F (0 degrees C) or above 110 degrees F
   (43 degrees C)
5. Check voltage once per month during storage -- if it drops below 35V,
   top up to 37V
6. Store in a LiPo-safe bag or on a concrete floor away from flammables

### 5.3 Electronics

1. Remove the Pixhawk SD card and store separately (prevents corrosion
   of contacts)
2. Cover all connectors with dust caps or tape (JST-GH, USB-C, SMA)
3. If storing in a humid environment, place silica gel packets inside the
   electronics enclosure (Tier 3) or in a sealed bag with the Pixhawk
   (Tier 2)
4. Remove batteries from the RC transmitter

### 5.4 Mechanical

1. Clean the frame and remove all paint residue
2. Lightly oil any bare metal contact points (bolts, axles, swivel
   bearings) with a thin film of machine oil or WD-40
3. Inflate or position tires so they are not bearing the weight of the
   robot in one spot (prevents flat spots on hoverboard rubber tires)
4. Cover the robot with a tarp or store in a dry area

### 5.5 Spring Startup (After Storage)

1. Charge battery to full (42V) and verify all cell groups are balanced
2. Reinstall SD card in Pixhawk
3. Connect battery, verify Pixhawk boots and all Lua scripts load
4. Verify GPS lock
5. Recalibrate compass (magnetization can shift during storage)
6. Perform RC calibration
7. Test motors in MANUAL mode
8. Flush the paint system with clean water and test spray pattern
9. Run a short test mission before the first real job

---

## 6. Battery Care (36V Li-ion)

The 36V 10Ah e-bike battery is a 10S lithium-ion pack with an integrated BMS
(Battery Management System). Proper care extends its life from 300 to 800+
charge cycles.

### 6.1 Charging

| Parameter | Value |
|-----------|-------|
| Charger type | 42V 2A lithium-ion charger (10S) |
| Full charge voltage | 42.0V (4.2V per cell) |
| Charge time (empty to full) | 3-5 hours at 2A |
| Charge temperature range | 32-113 degrees F (0-45 degrees C) |

- Always use the charger supplied with the battery or one rated for 10S
  lithium-ion (42V max output)
- Never charge unattended overnight in early uses -- monitor until you trust
  the charger
- Stop charging immediately if the battery swells, smells, or becomes
  unusually hot

### 6.2 Discharge Limits

| Parameter | Value | Param |
|-----------|-------|-------|
| Nominal voltage | 36V (3.6V/cell) | -- |
| Low voltage warning | 33V (3.3V/cell) | `BATT_LOW_VOLT` |
| Critical voltage (stop) | 30V (3.0V/cell) | `BATT_CRT_VOLT` |
| Minimum arming voltage | 35V (3.5V/cell) | `BATT_ARM_VOLT` |
| Absolute minimum | 28V (2.8V/cell) -- BMS cutoff | -- |

- Never discharge below 30V. The BMS should cut off at ~28V, but relying on
  the BMS shortens battery life
- The ArduRover `BATT_FS_LOW_ACT=2` (Hold) failsafe stops the robot at 33V
  to provide margin

### 6.3 Storage Voltage

| Storage Duration | Target Voltage | Per Cell |
|------------------|----------------|----------|
| Less than 1 week | 42V (full charge OK) | 4.2V |
| 1-4 weeks | 38-39V | 3.8-3.9V |
| More than 1 month | 37-38V | 3.7-3.8V |

### 6.4 Temperature Limits

| Condition | Temperature Range |
|-----------|-------------------|
| Charging | 32-113 degrees F (0-45 degrees C) |
| Discharging (operation) | 14-140 degrees F (-10 to 60 degrees C) |
| Storage | 50-77 degrees F (10-25 degrees C) ideal |
| Absolute storage limits | 32-113 degrees F (0-45 degrees C) |

- In cold weather: warm the battery to above 50 degrees F before charging
  (charging below freezing causes permanent damage)
- In hot weather: do not leave the battery in direct sun or in a closed
  vehicle (temperatures can exceed 150 degrees F)

### 6.5 Lifespan

| Usage Pattern | Expected Cycles | Expected Life |
|---------------|-----------------|---------------|
| Full discharge every cycle (42V to 30V) | 300-500 cycles | 1-2 years |
| Partial discharge (42V to 35V, 70% DoD) | 500-800 cycles | 2-3 years |
| Gentle use with storage voltage care | 800-1000 cycles | 3-4 years |

- Partial discharges extend battery life significantly
- For a typical 50-space lot job using 30-40 minutes of runtime, one full
  charge provides 3-5 jobs

---

## 7. Paint System Cleaning

### 7.1 After Every Use (Quick Flush)

Time: 5-10 minutes.

1. Pour remaining paint back into the container through a filter
2. Add 1 quart warm water to the reservoir
3. Run the pump with solenoid open for 30 seconds
4. Drain and repeat until water runs clear (usually 2-3 cycles)
5. Wipe the nozzle exterior with a damp rag

### 7.2 Weekly Deep Flush

Time: 15-20 minutes.

1. Perform the quick flush above
2. Add a capful of dish soap to 1 quart of warm water in the reservoir
3. Run the pump for 60 seconds with solenoid open
4. Drain soapy water
5. Flush with 2 quarts of clean warm water
6. Remove the nozzle tip, inspect the orifice, clean with the provided pin
7. Run the pump for 10 seconds without the nozzle to flush the tip holder

### 7.3 Nozzle Replacement Schedule

| Nozzle Type | Replacement Interval | Sign of Wear |
|-------------|---------------------|--------------|
| TeeJet 8004 (plastic) | Every 50-100 gallons or 3 months | Fan width increases >10%, uneven pattern |
| TeeJet 8004 (stainless) | Every 200-400 gallons or 12 months | Same as above, but slower wear |
| Graco RAC 5 LL5319 (Tier 3) | Every 100-200 gallons or 6 months | Tailing on pattern edges |

- Carry 2-3 spare nozzle tips at all times
- Replace immediately if the spray pattern shows tailing (heavy edges),
  streaking, or uneven distribution

### 7.4 Solenoid Valve Maintenance

- Monthly: disassemble and inspect the plunger and seat for paint buildup
- Quarterly: replace the solenoid valve O-rings/seals if the valve starts
  leaking or responding slowly
- The solenoid valve is a $15 consumable -- replace if it becomes unreliable
  rather than spending hours cleaning it

### 7.5 Pump Maintenance

- Monthly: listen for unusual sounds (grinding = bearing wear, knocking =
  diaphragm issue)
- Quarterly: check the pump pressure relief valve -- it should hold 60-80
  PSI without leaking
- The diaphragm pump is a $30 consumable -- replace at the first sign of
  pressure loss or inconsistent flow

---

## 8. Motor Inspection

### 8.1 Hub Motor Bearings

Hoverboard hub motors use sealed ball bearings that are designed for the life
of the hoverboard (typically 500+ hours of riding). In a line striping robot
operating at low speeds (0.5 m/s), bearing wear is minimal.

- **Monthly**: spin each wheel by hand and listen. Smooth and quiet = good.
  Grinding, clicking, or roughness = bearing wear
- **Quarterly**: check for lateral play in the wheel (grab the tire and try
  to wobble it side-to-side on the axle). Any play indicates bearing wear
- **Replacement**: hub motor bearings can be pressed out and replaced, but
  it is generally easier to replace the entire hub motor (~$15-25 for a
  spare hoverboard motor on eBay)

### 8.2 Tire Wear

Hoverboard tires are solid rubber (no flats possible) but they do wear:

- **Monthly**: inspect tread depth and look for flat spots (from sitting in
  one position under load)
- **Quarterly**: measure tire diameter and compare to the original 6.5"
  (165mm). If worn more than 5mm, update `WHL_TRACK` and any speed
  calibration parameters
- **Replacement**: hoverboard tires pull off the hub rim. Replacements are
  available on Amazon/AliExpress for $5-10 each

### 8.3 Motor Alignment

- **Monthly**: with the robot on a flat surface, check that both wheels
  contact the ground evenly. Uneven contact indicates a bent axle or
  misaligned frame mount
- **Quarterly**: measure the track width (center-to-center of the two drive
  wheels) and verify it matches `WHL_TRACK` (default 0.40m) in the param
  file. Frame flexing or mounting shifts can change this

### 8.4 Hoverboard Mainboard

- **Weekly**: visual inspection for swollen capacitors, discolored MOSFETs,
  or loose wires
- **Monthly**: check the temperature of MOSFETs after a 10-minute run
  (warm is normal, too hot to touch = inadequate cooling or excessive load)
- **Quarterly**: re-solder any cold or cracked solder joints, especially on
  the UART pads and power input terminals

---

## 9. GPS Antenna Care

### 9.1 Physical Care

- Keep the antenna element clean -- wipe with a damp cloth (no solvents,
  no abrasives)
- Do not paint over the antenna or cover it with metallic tape
- Protect the SMA connector from bending forces -- use a right-angle SMA
  adapter if the cable comes off at a sharp angle
- Replace the antenna cable if the SMA connector is loose, corroded, or
  shows signs of water ingress

### 9.2 Mounting

- The antenna must have an unobstructed 360-degree view of the sky
- Mount on the highest point of the robot
- Use an aluminum ground plane disc (100mm diameter, 1-2mm thick) under the
  antenna for better multipath rejection
- Keep the antenna at least 10cm from the Pixhawk compass to avoid magnetic
  interference with GPS signals (the GPS signals are not affected, but the
  compass is affected by the antenna's ground plane if too close)

### 9.3 Cable

- Route the SMA cable away from motor power wires (electromagnetic
  interference can degrade GPS signal quality)
- Secure the cable to the frame with zip ties at 10cm intervals
- Avoid sharp bends in the cable (minimum bend radius: 5x cable diameter
  for RG316 coax)
- Inspect the cable monthly for cuts, kinks, or abrasion

---

## 10. Firmware Update Procedure

### 10.1 ArduRover Firmware Update

**When to update**: check for new stable releases every 1-2 months at
https://ardupilot.org/rover. Update if there are bug fixes relevant to your
setup or new features you need. Do NOT update mid-season unless you have a
specific reason.

**Procedure**:

1. **Back up your current parameters**: In Mission Planner, go to Config >
   Full Parameter List > Save to File. Save as
   `striper_params_backup_YYYYMMDD.param`
2. **Back up your Lua scripts**: Copy all files from the Pixhawk SD card
   `/APM/scripts/` to your laptop
3. **Connect the Pixhawk** to your laptop via USB-C
4. **Open Mission Planner** and connect (AUTO, 115200)
5. Go to **Setup > Install Firmware**
6. Select **Rover** and choose the latest stable version
7. Click **Install** and wait for the process to complete (do not
   disconnect during flashing)
8. After flashing, the Pixhawk will reboot. Reconnect in Mission Planner
9. **Reload your parameters**: Config > Full Parameter List > Load from
   File > select your backup file > Write Params
10. **Verify Lua scripts** are still on the SD card (firmware update does
    not erase the SD card, but verify anyway)
11. **Test thoroughly** before the next job:
    - Motor response in MANUAL mode
    - GPS lock
    - Relay operation
    - All Lua scripts loading (check GCS messages)
    - A short test mission in an empty area

### 10.2 Hoverboard FOC Firmware Update

**When to update**: only if you need a specific bug fix or feature from a
newer version of hoverboard-firmware-hack-FOC. The FOC firmware is mature
and updates are infrequent.

**Procedure**:

1. **Save your current config.h**: this contains your UART settings, motor
   parameters, and speed limits
2. Download the latest release from
   https://github.com/EFeru/hoverboard-firmware-hack-FOC
3. Copy your config.h settings to the new version's config.h
4. Build the firmware using STM32CubeIDE or PlatformIO
5. Connect the ST-Link V2 to the hoverboard mainboard SWD pads
   (SWDIO, SWCLK, GND, 3.3V)
6. Flash using STM32CubeProgrammer
7. After flashing, power cycle the mainboard
8. Test motor response with a USB-serial adapter before reconnecting to the
   Pixhawk
9. Reconnect to Pixhawk SERIAL2 and verify motor_bridge.lua communicates
   correctly

### 10.3 Lua Script Updates

**Procedure**:

1. Power off the Pixhawk
2. Remove the SD card
3. Insert the SD card in your laptop
4. Navigate to `/APM/scripts/`
5. Replace or update the .lua files:
   - `motor_bridge.lua`
   - `paint_control.lua`
   - `paint_speed_sync.lua`
   - `fence_check.lua`
6. Verify file sizes are non-zero and files are not corrupted (open each
   in a text editor)
7. Re-insert the SD card in the Pixhawk
8. Power on and verify all scripts load (check GCS messages for "loaded"
   text from each script)

---

## Maintenance Schedule Summary

| Task | Frequency | Time |
|------|-----------|------|
| Pre-job checklist | Every use | 15-20 min |
| Post-job paint flush | Every use | 10-15 min |
| Post-job battery and log | Every use | 5-10 min |
| Electrical connection inspection | Weekly | 15 min |
| Motor system inspection | Weekly | 10 min |
| Frame bolt check | Weekly | 10 min |
| GPS antenna inspection | Weekly | 5 min |
| Deep clean and paint system overhaul | Monthly | 60-90 min |
| Compass recalibration | Monthly | 15 min |
| Battery health check | Monthly | 15 min |
| RC transmitter battery replacement | Monthly | 5 min |
| Nozzle tip replacement | Every 3-6 months | 5 min |
| Firmware version check | Every 1-2 months | 10 min |
| Full parameter backup | Monthly | 5 min |
| Seasonal storage prep | End of season | 45-60 min |
| Spring startup procedure | Start of season | 60-90 min |

---

## Spare Parts Kit

Keep these in your vehicle for field repairs:

| Part | Qty | Approx Cost |
|------|-----|-------------|
| TeeJet 8004 nozzle tips | 3 | $10 |
| Relay module (2-channel, 5V) | 1 | $5 |
| DC-DC converter 36V to 12V | 1 | $5 |
| DC-DC converter 36V to 5V (BEC) | 1 | $5 |
| 30A blade fuses | 5 | $3 |
| 5A blade fuses | 5 | $2 |
| JST-GH 6-pin cables (Pixhawk) | 2 | $5 |
| XT60 connectors (pair) | 2 | $3 |
| 14 AWG silicone wire (3 ft red, 3 ft black) | 1 lot | $5 |
| Zip ties (assorted) | 1 bag | $3 |
| Heat shrink tubing (assorted) | 1 kit | $5 |
| Vinyl tubing 1/2" (3 ft) | 1 | $3 |
| Hose clamps (assorted small) | 5 | $3 |
| 1N4007 diodes | 5 | $2 |
| Multimeter | 1 | $15 |
| Soldering iron (battery-powered) | 1 | $20 |
| Solder and flux | 1 | $5 |
| Nozzle cleaning pins | 1 set | $3 |
| **Total** | | **~$102** |

Optional but recommended:

| Part | Qty | Approx Cost |
|------|-----|-------------|
| Spare hoverboard mainboard (pre-flashed) | 1 | $30 |
| Spare 12V diaphragm pump | 1 | $30 |
| Spare solenoid valve | 1 | $15 |
| Second 36V 10Ah battery | 1 | $100 |
