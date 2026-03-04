# Striper Robot -- Wiring Guide

Complete wiring reference for the ArduRover + hoverboard architecture.
This guide covers the Tier 2 "Best Value" build (Pixhawk 6C Mini +
UM980 GPS + hoverboard motors). Tier 1 (ESP32) and Tier 3 (full-size
Pixhawk 6C) builders: adapt as noted inline.

A builder should be able to wire the entire robot from this document.

---

## 1. System Diagram

```
                    +=========================+
                    |  36V E-BIKE BATTERY     |
                    |  (10Ah / 360Wh)         |
                    +=========================+
                       |         |         |
                  [30A FUSE]     |         |
                       |         |         |
                  [DC CONTACTOR] |         |  ←── coil driven by E-STOP N.C.
                       |         |         |
              +--------+    +---+----+ +---+---------+
              |             | 36V→12V| | Holybro     |
              |             | DC-DC  | | PM06 V2     |
              |             | (5A)   | | (5V/3A +    |
              |             +---+----+ |  batt mon.) |
              |                 |      +---+---------+
              |            12V RAIL        5V RAIL
              |           (pump,         (Pixhawk,
              |          solenoid)        GPS, RC rx)
              |
     +--------+--------+
     | HOVERBOARD       |
     | MAINBOARD         |
     | (FOC firmware)    |
     | STM32F103RCT6     |
     |                   |
     | LEFT MOTOR ←──────|──── Left hub motor
     | RIGHT MOTOR ←─────|──── Right hub motor
     |                   |
     | UART RX ←─────────|──── Pixhawk SERIAL1/2 TX
     | UART TX ──────────|───→ Pixhawk SERIAL1/2 RX
     | GND ──────────────|──── Pixhawk GND
     +-------------------+


     +===========================================+
     |           PIXHAWK 6C MINI                 |
     |                                           |
     | SERIAL3 ────── UM980 GPS (UART, 4 wires)  |
     |                                           |
     | SERIAL1/2 ──── Hoverboard UART (TX/RX/GND)|
     |                                           |
     | AUX5 (pin 54) → Relay CH1 ──→ 12V Solenoid |
     |                                           |
     | AUX6 (pin 55) → Relay CH2 ──→ 12V Pump     |
     |                (optional,                 |
     |                 or wire pump always-on)    |
     |                                           |
     | SBUS IN ←────── RC Receiver (FlySky)      |
     |                                           |
     | SAFETY ←──────── E-stop button (signal)   |
     |                                           |
     | POWER IN ←────── Holybro PM06 V2 (5V+mon.)|
     |                                           |
     | USB-C ←───────── Laptop (config/telemetry)|
     +===========================================+
```

> **Tier 1 builders:** Replace the Pixhawk with an ESP32-S3. The ESP32
> reads GPS over UART, sends motor commands to the hoverboard over a
> second UART, and toggles the relay with a GPIO pin. Same power and
> motor wiring applies.

---

## 2. Power Distribution

### 2.1 Overview

The 36V e-bike battery is the single power source. Three rails are
derived from it:

| Rail | Source | Supplies | Wire Gauge |
|------|--------|----------|------------|
| 36V direct | Battery through fuse, contactor, and e-stop | Hoverboard mainboard (motors) | **12 AWG** min |
| 12V | 36V to 12V DC-DC converter (**5A min**) | Shurflo pump, solenoid valve | 18 AWG |
| 5V | Holybro PM06 V2 (5V/3A + battery monitoring) | Pixhawk, UM980 GPS, RC receiver | 22 AWG |

### 2.2 Wiring

```
Battery (+) ──[30A blade fuse]──[DC CONTACTOR N.O.]──┬── Hoverboard mainboard VCC
                                                       ├── 36V→12V DC-DC IN+
                                                       └── PM06 V2 IN+

                                    DC CONTACTOR coil (+) ←── Battery + (after fuse)
                                    DC CONTACTOR coil (−) ←── E-STOP N.C. ──→ GND

Battery (−) ──────────────────────────────────────────┬── Hoverboard mainboard GND
                                                       ├── 36V→12V DC-DC IN−
                                                       ├── PM06 V2 IN−
                                                       └── Common GND bus
```

**Key points:**
- The 30A blade fuse goes inline on the positive wire, directly at the
  battery. Use a waterproof inline fuse holder.
- The **DC contactor** (40A rated) is controlled by the e-stop button.
  The e-stop's N.C. contacts energize the contactor coil; pressing the
  e-stop de-energizes the coil and the contactor opens, cutting all 36V
  power. A bare 22mm e-stop button cannot reliably interrupt 40A DC —
  the DC arc will weld the contacts. The contactor handles the high
  current safely.
- Use XT60 connectors for the battery connection (easy disconnect).
- All grounds share a common bus (terminal block or solder joint). This
  is critical -- the Pixhawk, GPS, hoverboard, and relay module must
  share a common ground.
- Use **12 AWG silicone wire** for the 36V main power run (not 14 AWG).
  Peak motor current can reach 30A; 14 AWG is marginal.

### 2.3 DC-DC Converter Selection

| Converter | Input Range | Output | Min Current Rating | Example Module |
|-----------|-------------|--------|-------------------|----------------|
| 36V to 12V | 8-60V in | 12V fixed | **5A (10A preferred)** | XL4015 5A buck module |
| 36V to 5V | 7-42V in | 5.2V regulated | 3A | **Holybro PM06 V2** |

> **Why 5A minimum for 12V:** The Shurflo 8000 pump has a startup inrush
> of 15-24A for ~50ms. A 3A converter will brownout and may reset the
> Pixhawk if sharing a ground bus. A 5A converter handles steady-state
> (pump draws ~3A running); 10A handles inrush with margin.

> **Why Holybro PM06 V2 for 5V:** Replaces the generic BEC. The PM06 V2
> includes an INA226 current/voltage sensor that reports battery state to
> the Pixhawk via its POWER port. This gives you battery % remaining,
> voltage, and current draw in Mission Planner — critical for knowing
> when to end a mission. Input range: 7-42V (works with 36V battery).

Verify output voltage with a multimeter before connecting anything.

---

## 3. Hoverboard Mainboard UART Wiring

The hoverboard mainboard running
[hoverboard-firmware-hack-FOC](https://github.com/EFeru/hoverboard-firmware-hack-FOC)
exposes a UART interface for receiving speed commands. The FOC firmware
supports multiple UART ports; the most common is the one exposed on the
sensor board connector pads.

### 3.1 Hoverboard Side

Find the UART pads on the hoverboard mainboard. In the FOC firmware
`config.h`, the default UART is typically on the auxiliary/sensor
connector:

| Pad Label | Function | Wire Color (typical) |
|-----------|----------|---------------------|
| GND | Ground | Black |
| TX | Transmit (data out from hoverboard) | Green or Yellow |
| RX | Receive (data in to hoverboard) | Blue or White |

> Check the [FOC firmware wiki](https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki)
> for your specific mainboard variant. Common variants: split board
> (two separate boards) and single board. Pin locations differ.

### 3.2 Pixhawk Side

Connect to **SERIAL1** (TELEM1) or **SERIAL2** (TELEM2) on the Pixhawk 6C
Mini. These are JST-GH 6-pin connectors. You need three wires:

| Pixhawk Pin | Function | Connects To |
|-------------|----------|-------------|
| Pin 2 | TX (out) | Hoverboard RX |
| Pin 3 | RX (in) | Hoverboard TX |
| Pin 6 | GND | Hoverboard GND |

> **Logic levels:** The Pixhawk outputs 3.3V UART. Most hoverboard
> mainboards accept 3.3V logic. If yours requires 5V, add a simple
> logic level shifter on the TX line.

### 3.3 ArduRover Configuration

In Mission Planner, set the serial port parameters:

```
SERIAL1_PROTOCOL = 2       (MAVLink -- if using SERIAL1 for telemetry, use SERIAL2 instead)
SERIAL2_PROTOCOL = <motor driver protocol number>
SERIAL2_BAUD = 115200
```

> Set `SERIAL2_PROTOCOL = 28` (Scripting) and `SERIAL2_BAUD = 115200`.
> The `motor_bridge.lua` Lua script on the Pixhawk reads ArduRover's
> SERVO1/SERVO3 PWM outputs, converts them to the hoverboard FOC UART
> protocol, and sends them over Serial2. This is handled automatically
> when you load the Lua scripts -- no external Arduino is needed.
> Set `FRAME_TYPE = 2` (differential drive / skid steering).

---

## 4. GPS Wiring (UM980)

### 4.1 Connections

The UM980 breakout board communicates with the Pixhawk over UART.
Connect to **SERIAL3** (GPS1) or **SERIAL4** (GPS2) on the Pixhawk.

| Pixhawk GPS Port Pin | Function | Connects To |
|-----------------------|----------|-------------|
| Pin 1 | VCC (5V) | UM980 VCC (5V input) |
| Pin 2 | TX (out) | UM980 RX |
| Pin 3 | RX (in) | UM980 TX |
| Pin 6 | GND | UM980 GND |

> **Important:** TX-to-RX crossover. Pixhawk TX goes to UM980 RX, and
> vice versa.

### 4.2 Antenna

Connect a multiband GNSS antenna (L1/L2 minimum, L1/L2/L5 preferred) to
the UM980 breakout's SMA connector using an SMA cable. Mount the antenna
on top of the robot with a clear view of the sky. Use an aluminum ground
plane disc (100mm diameter) under the antenna for better multipath
rejection.

### 4.3 ArduRover Configuration

```
SERIAL3_PROTOCOL = 5       (GPS)
SERIAL3_BAUD = 115         (115200 baud — ArduPilot uses shorthand)
GPS_TYPE = 24              (UnicoreNMEA — single UM980)
GPS_RATE_MS = 200          (5 Hz update, or 100 for 10 Hz)
COMPASS_ENABLE = 0         (disable compass — hub motor magnets cause
                            overwhelming interference; use GPS-based heading)
```

> **GPS_TYPE values:** `24` = UnicoreNMEA (single UM980). `25` =
> UnicoreMovingBaselineNMEA (dual-antenna UM982 for GPS-based heading).
> Use 24 unless you upgrade to UM982.

> **Compass-less operation:** ArduRover uses GSF (Gaussian Sum Filter) to
> estimate heading from GPS velocity vectors. Works reliably at 0.5+ m/s
> in open sky. After GPS lock, walk the robot in a small circle (~2m)
> to initialize yaw. Wait for "EKF yaw alignment complete" in Mission
> Planner before arming.

> **Tier 1 (ZED-F9P):** Set `GPS_TYPE = 2` (u-blox). The simpleRTK2B
> board can connect via USB to the ESP32 or via UART.

### 4.4 RTK Corrections

For centimeter-level accuracy, the GPS needs RTCM3 corrections from a
base station or NTRIP service. Options:

1. **Mission Planner NTRIP:** Configure Mission Planner to connect to an
   NTRIP caster (e.g., RTK2Go, free) and relay corrections to the
   Pixhawk over the telemetry link.
2. **Own base station:** A second UM980 or LC29H module at a known
   location, transmitting corrections via a telemetry radio.
3. **PointPerfect / Polaris:** Commercial correction services ($50/month).

---

## 5. Solenoid + Pump Relay Wiring

The Pixhawk controls the paint solenoid valve (and optionally the pump)
through a relay module. The Pixhawk's MAIN OUT pins output PWM servo
signals; a relay module converts these to on/off switching of the 12V
devices.

### 5.1 Relay Module

Use a 2-channel 5V relay module (opto-isolated preferred). These modules
trigger when the signal pin goes HIGH (or LOW, depending on module --
check yours).

### 5.2 Wiring

```
SOLENOID CIRCUIT:

Pixhawk AUX5 (signal wire, pin 54) ──→ Relay CH1 IN
Pixhawk GND ──────────────────────→ Relay GND
5V BEC ───────────────────────────→ Relay VCC

Relay CH1 COM ──→ 12V DC-DC output (+)
Relay CH1 N.O. ──→ Solenoid valve terminal 1
Solenoid valve terminal 2 ──→ 12V DC-DC output (−) / GND


PUMP CIRCUIT (if using relay control):

Pixhawk AUX6 (signal wire, pin 55) ──→ Relay CH2 IN
(GND and VCC already connected above)

Relay CH2 COM ──→ 12V DC-DC output (+)
Relay CH2 N.O. ──→ Pump terminal (+)
Pump terminal (−) ──→ 12V DC-DC output (−) / GND
```

> **Flyback protection:** Add a 1N4007 diode across each solenoid/pump
> terminal (cathode to positive, anode to negative) to suppress voltage
> spikes when the relay opens.

> **Simpler pump option:** If you do not need variable or software-
> controlled pump operation, wire the pump directly to the 12V rail with
> a manual toggle switch. The solenoid alone controls paint on/off.

### 5.3 ArduRover Configuration

```
RELAY1_PIN = 54            (AUX5 / SERVO13 on Pixhawk 6C)
RELAY2_PIN = 55            (AUX6 / SERVO14 on Pixhawk 6C)
RELAY1_DEFAULT = 0         (off at startup)
RELAY2_DEFAULT = 0         (off at startup)
```

> **Important:** The relay pins use AUX outputs (54/55), NOT MAIN outputs
> (50/51). This keeps the relay signals separate from the motor servo
> outputs on SERVO1/SERVO3. Wire the relay module signal inputs to the
> Pixhawk AUX5 and AUX6 pins, not MAIN OUT 1/2.

Paint on/off is triggered by `DO_SET_RELAY` mission commands or by the
AC_Sprayer library. See the Lua script in `docs/research_report.md` for
waypoint-based paint control.

### 5.4 Paint Plumbing (Physical)

```
Paint Tank ──→ [60-mesh strainer] ──→ Shurflo Pump ──→ [T-valve] ──→ Solenoid ──→ Nozzle
                                                          ↑
                                                    Water Tank (500ml)
                                                    (flush reservoir)
```

**Paint prep:** Thin water-based traffic latex 10-15% with water before
filling the tank. Use **normal-dry** paint only — fast-dry formulations
will clog the nozzle in under 2 minutes.

**Flush system:** The 3-way T-valve switches between paint and water.
Before any pause longer than 30 seconds, flush the system with water to
prevent paint drying in the nozzle. The `paint_control.lua` script can
trigger an automatic flush cycle.

**Flyback diodes:** Install a **1N4007 diode** across each inductive load
(solenoid and pump motor). Cathode to positive terminal, anode to
negative terminal. This suppresses the voltage spike when the relay
opens, protecting the relay contacts and nearby electronics.

---

## 6. RC Receiver Wiring

The FlySky FS-i6X receiver connects to the Pixhawk's SBUS/RC input for
manual override and mode switching.

### 6.1 Connections

| Receiver Pin | Connects To |
|--------------|-------------|
| SBUS / IBUS out | Pixhawk RC IN (SBUS port) |
| VCC (5V) | Pixhawk RC IN VCC (powered by Pixhawk) |
| GND | Pixhawk RC IN GND |

> The Pixhawk 6C Mini's RC IN port is a JST-GH 3-pin connector. The
> receiver is powered directly from this port (5V from the Pixhawk).

### 6.2 Channel Assignment (suggested)

| RC Channel | Function |
|------------|----------|
| CH1 | Steering (left stick horizontal) |
| CH2 | Throttle (left stick vertical) |
| CH3 | (spare) |
| CH4 | (spare) |
| CH5 | Flight mode switch (3-position: MANUAL / HOLD / AUTO) |
| CH6 | Spray toggle (switch or knob) |

### 6.3 ArduRover Configuration

```
RC5_OPTION = 0             (flight mode channel)
FLTMODE_CH = 5
FLTMODE1 = 0               (MANUAL)
FLTMODE3 = 4               (HOLD)
FLTMODE6 = 10              (AUTO)
```

---

## 7. E-Stop Wiring

The emergency stop provides a **hard electrical cutoff** of motor power.
It does not rely on software.

### 7.1 Design

The e-stop button drives a **40A DC contactor** that switches the main
36V power. The button's N.C. contacts carry only the contactor coil
current (~0.5A), not the full motor current. Pressing the e-stop
de-energizes the contactor coil, which opens the contactor and
immediately kills power to everything.

```
Battery (+) ──[30A Fuse]──[DC CONTACTOR N.O. contacts]──→ Hoverboard VCC / DC-DC inputs
                 |
                 └── Contactor coil (+)
                            |
                     [E-Stop N.C. contacts]
                            |
                           GND

          E-STOP released (N.C. closed) → coil energized → contactor closed → power ON
          E-STOP pressed (N.C. open) → coil de-energized → contactor open → power OFF
```

> **Why a contactor?** A 22mm mushroom e-stop button is typically rated
> for 5-10A AC. At 36V DC with motor loads up to 40A, the DC arc when
> breaking the circuit will weld the button contacts shut. A DC contactor
> (Hella 4RA, EV200 style, or automotive 40A relay) handles this safely.

### 7.2 Optional: Signal to Pixhawk

For software awareness of the e-stop state, use the e-stop button's
second N.C. contact pair (if available) to signal the Pixhawk:

```
5V BEC ──[10k resistor]──┬──→ Pixhawk SAFETY pin or spare GPIO
                          |
                    [E-Stop N.C. contact pair 2]
                          |
                         GND
```

When contacts are closed (normal): pin reads HIGH (5V through 10k).
When contacts are open (e-stop pressed): pin reads LOW (pulled to GND).

> **Most builders can skip the signal wire.** The hard power cutoff is
> the primary safety mechanism. ArduRover's RC failsafe (loss of RC
> signal) provides a software-level emergency stop.

### 7.3 Key Rules

- Use a **twist-release** mushroom-head button so it cannot be
  accidentally released.
- Mount it where the operator can reach it instantly (top of the robot
  or on a tethered remote panel).
- The e-stop button drives a **DC contactor coil** (not the main power
  directly). The contactor must be rated for at least 40A at 36V DC.
- The 30A fuse protects against wiring faults. It does NOT replace the
  e-stop.

---

## 8. Safety Notes

### Wire Gauge Reference

| Circuit | Recommended Gauge | Max Current |
|---------|-------------------|-------------|
| Battery to fuse / contactor | **12 AWG** | 30-40A |
| Hoverboard mainboard power | **12 AWG** | 20-30A |
| 12V pump / solenoid | 18 AWG | 5A |
| PM06 V2 input (36V side) | 18 AWG | 1A |
| 5V rail (PM06 output) | 22 AWG | 3A |
| Signal wires (UART, SBUS, GPIO) | 22-26 AWG | < 1A |
| GPS antenna cable | RG316 coax (SMA) | N/A |

### Fuses

- **30A blade fuse** inline on battery positive, before anything else.
- **5A fuse** inline on the 12V rail (optional but recommended).
- If using a fuse panel (Tier 3), fuse each rail separately.

### Waterproofing (Tier 3)

- Route all cables through cable glands into the IP65 enclosure.
- Use silicone-filled butt connectors or heat-shrink solder connectors
  for outdoor splices.
- Conformal-coat the Pixhawk and relay module PCBs if operating in rain.

### General

- **Always disconnect the battery** before wiring changes.
- **Verify DC-DC converter output** with a multimeter before connecting
  the Pixhawk or GPS. A converter set to the wrong voltage will destroy
  them.
- **Common ground is mandatory.** Every device (Pixhawk, GPS, hoverboard,
  relay module, DC-DC converters) must share a common ground reference.
- **Keep signal wires away from motor power wires.** Route them on
  opposite sides of the frame to avoid electromagnetic interference.
- **Secure all wires** with zip ties or adhesive cable clips. Loose wires
  near spinning wheels are a hazard.

---

## 9. Step-by-Step Assembly Checklist

Follow this order. Do not proceed until the current step is verified.

### Phase 1: Frame + Motors (Steps 1-5)

- [ ] **1.** Build the frame. Cut plywood (or assemble aluminum extrusion).
      Mount casters at the front. Leave the rear open for hoverboard
      wheels.
- [ ] **2.** Disassemble the hoverboard. Extract the mainboard and both
      hub-motor wheels. Mount the wheels to the rear of the frame (they
      are the drive wheels).
- [ ] **3.** Flash the hoverboard mainboard with FOC firmware using the
      ST-Link V2. Follow the
      [firmware wiki](https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki).
      Configure `config.h` for UART control input.
- [ ] **4.** Bench-test the motors. Connect the hoverboard mainboard to a
      36V power supply (or the hoverboard battery). Send UART speed
      commands from a USB-serial adapter on your laptop. Verify both
      motors spin and respond to speed/direction commands.
- [ ] **5.** Mount the mainboard on the frame. Route motor phase wires and
      hall sensor cables neatly. **Measure the wheel center-to-center
      distance** (track width) with a tape measure and record it. Update
      `WHL_TRACK` in the param file to match (default is 0.40m).

### Phase 2: Power System (Steps 6-8)

- [ ] **6.** Install the 36V e-bike battery on the frame. Wire the battery
      positive through the 30A inline fuse, then through the DC contactor
      N.O. contacts, then to a power distribution point (terminal block
      or bus bar). Wire the contactor coil: positive to fused battery,
      negative through the e-stop N.C. contacts to GND.
- [ ] **7.** Install the two DC-DC converters. Wire their inputs to the
      36V bus (after the fuse/e-stop). Verify outputs with a multimeter:
      12V and 5V.
- [ ] **8.** Test the e-stop. With motors connected, spin them up with a
      UART command, then press the e-stop. Motors must stop immediately.
      Release (twist) the e-stop and verify power returns.

### Phase 3: Pixhawk + GPS (Steps 9-12)

- [ ] **9.** Mount the Pixhawk 6C Mini on the frame using vibration-
      dampening foam or standoffs. Keep it away from motors and magnets.
- [ ] **10.** Power the Pixhawk from the 5V BEC. Use a JST-GH power cable
       to the POWER port, or wire 5V/GND to the appropriate pins. Verify
       the Pixhawk boots (LED sequence).
- [ ] **11.** Connect the Pixhawk to your laptop via USB-C. Open Mission
       Planner. Flash ArduRover firmware. Set `FRAME_TYPE = 2`
       (differential drive / skid steering).
- [ ] **12.** Wire the UM980 GPS to Pixhawk SERIAL3 (GPS1 port). Connect
       the GNSS antenna. Take the robot outdoors. In Mission Planner,
       verify GPS fix (3D fix, then RTK float/fixed when corrections
       are available).

### Phase 4: Motor Control via Pixhawk (Steps 13-15)

- [ ] **13.** Wire the hoverboard UART to Pixhawk SERIAL1 or SERIAL2
       (TX/RX/GND, with crossover). Configure the serial port protocol
       and baud rate in Mission Planner.
- [ ] **14.** In Mission Planner, set up skid steering outputs and verify
       the Pixhawk sends correct commands. With the robot on blocks
       (wheels off the ground), test MANUAL mode with the RC transmitter.
       Both wheels should respond to throttle/steering.
- [ ] **15.** Test AUTO mode. Create a simple 3-waypoint mission in Mission
       Planner. Upload to Pixhawk. Switch to AUTO mode. Verify the robot
       drives between waypoints (wheels off ground or in a safe open
       area).

### Phase 5: RC Receiver (Step 16)

- [ ] **16.** Wire the FlySky receiver to the Pixhawk RC IN port
       (SBUS signal + 5V + GND). Bind the transmitter to the receiver.
       In Mission Planner, verify RC input on the Radio Calibration page.
       Calibrate sticks and set up the flight mode switch (CH5).

### Phase 6: Paint System (Steps 17-19)

- [ ] **17.** Install the 12V solenoid valve and diaphragm pump. Wire them
       through the relay module as described in Section 5. Connect the
       relay module signal inputs to Pixhawk AUX5 (pin 54) and AUX6 (pin 55).
       Add flyback diodes across both the solenoid and pump.
- [ ] **18.** Test relay operation. In Mission Planner, manually toggle
       RELAY1. The solenoid should click open/closed. Toggle RELAY2 and
       verify the pump runs.
- [ ] **19.** Connect tubing: paint reservoir to pump to solenoid to nozzle.
       Test with water first. Verify spray pattern width and consistency.

### Phase 7: Final Integration (Steps 20)

- [ ] **20.** Full system test in an open parking lot.
       - Start in MANUAL mode (RC control). Drive around, toggle spray.
       - Switch to AUTO mode. Run a test mission with `DO_SET_RELAY`
         commands to turn paint on/off at specific waypoints.
       - Test e-stop under AUTO mode. Press it mid-mission. Motors must
         stop immediately.
       - Verify GPS accuracy (walk the painted line with a tape measure).
       - If using ultrasonics: mount HC-SR04 sensors at the front, wire
         to spare Pixhawk GPIO or an Arduino, and verify obstacle stop.

---

## Appendix A: Pixhawk 6C Mini Port Map

| Port | Connector | Typical Use in This Build |
|------|-----------|--------------------------|
| POWER | JST-GH 6-pin | 5V BEC input |
| TELEM1 (SERIAL1) | JST-GH 6-pin | Hoverboard UART (or telemetry radio) |
| TELEM2 (SERIAL2) | JST-GH 6-pin | Hoverboard UART (alt) or telemetry |
| GPS1 (SERIAL3) | JST-GH 6-pin | UM980 GPS UART |
| GPS2 (SERIAL4) | JST-GH 6-pin | (spare / 2nd GPS) |
| RC IN | JST-GH 3-pin | FlySky SBUS receiver |
| MAIN OUT 1-8 | JST-GH (servo rail) | AUX5 (pin 54): solenoid relay, AUX6 (pin 55): pump relay |
| USB-C | USB-C | Laptop (Mission Planner) |
| SAFETY | JST-GH 3-pin | Safety switch (or e-stop signal) |
| I2C | JST-GH 4-pin | (spare / compass / sensor) |

## Appendix B: Hoverboard Mainboard Pinout (FOC Firmware)

Refer to the
[hoverboard-firmware-hack-FOC wiki](https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki)
for your specific board variant. Common pinout for the "split board"
variant:

| Connector / Pad | Function | Notes |
|-----------------|----------|-------|
| Battery + / − | 36V power input | Through fuse and e-stop |
| Left motor (3 phase wires) | U/V/W motor phases | Yellow/Blue/Green (varies) |
| Left hall sensor (5 wires) | Hall A/B/C + 5V + GND | JST-XH connector |
| Right motor (3 phase wires) | U/V/W motor phases | Yellow/Blue/Green (varies) |
| Right hall sensor (5 wires) | Hall A/B/C + 5V + GND | JST-XH connector |
| UART TX/RX/GND pads | Serial control interface | Solder wires to these pads |
| SWD pads (SWDIO/SWCLK/GND/3.3V) | Programming interface | Connect ST-Link V2 here |

## Appendix C: Tier 1 (ESP32) Wiring Differences

If building Tier 1 without a Pixhawk:

| Function | Pixhawk (Tier 2/3) | ESP32 (Tier 1) |
|----------|-------------------|----------------|
| GPS input | Pixhawk SERIAL3 UART | ESP32 UART1 (GPIO 16 RX, GPIO 17 TX) |
| Motor commands | Pixhawk SERIAL1/2 | ESP32 UART2 (GPIO 25 RX, GPIO 26 TX) |
| Solenoid control | Pixhawk MAIN OUT 1 to relay | ESP32 GPIO 4 to relay IN |
| RC override | SBUS receiver to Pixhawk | Not available (or add custom RC) |
| Power | 5V BEC to Pixhawk POWER port | 5V BEC to ESP32 VIN pin |
| Configuration | Mission Planner | Custom firmware + serial monitor |

The ESP32 runs custom waypoint-following firmware. You lose ArduRover's
autopilot, Mission Planner, geofencing, and RC failsafe. Recommended
only for bench testing and proof of concept.
