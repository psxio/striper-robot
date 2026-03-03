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
                  [E-STOP N.C.]  |         |
                       |         |         |
              +--------+    +---+----+ +---+--------+
              |             | 36V→12V| | 36V→5V BEC |
              |             | DC-DC  | | DC-DC      |
              |             | (3A)   | | (2A)       |
              |             +---+----+ +---+--------+
              |                 |           |
              |            12V RAIL      5V RAIL
              |           (pump,       (Pixhawk,
              |          solenoid)      GPS, RC rx)
              |
     +--------+--------+
     | HOVERBOARD       |
     | MAINBOARD         |
     | (FOC firmware)    |
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
     | SERIAL3/4 ──── UM980 GPS (UART, 4 wires)  |
     |                                           |
     | SERIAL1/2 ──── Hoverboard UART (TX/RX/GND)|
     |                                           |
     | MAIN OUT 1 ──→ Relay CH1 ──→ 12V Solenoid |
     |                                           |
     | MAIN OUT 2 ──→ Relay CH2 ──→ 12V Pump     |
     |                (optional,                 |
     |                 or wire pump always-on)    |
     |                                           |
     | SBUS IN ←────── RC Receiver (FlySky)      |
     |                                           |
     | SAFETY ←──────── E-stop button (signal)   |
     |                                           |
     | POWER IN ←────── 5V BEC (36V→5V DC-DC)    |
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
| 36V direct | Battery through fuse and e-stop | Hoverboard mainboard (motors) | 14 AWG min |
| 12V | 36V to 12V DC-DC converter (3A) | Diaphragm pump, solenoid valve | 18 AWG |
| 5V | 36V to 5V DC-DC BEC (2A) | Pixhawk, UM980 GPS, RC receiver | 22 AWG |

### 2.2 Wiring

```
Battery (+) ──[30A blade fuse]──[E-stop N.C. contacts]──┬── Hoverboard mainboard VCC
                                                         ├── 36V→12V DC-DC IN+
                                                         └── 36V→5V DC-DC IN+

Battery (−) ────────────────────────────────────────────┬── Hoverboard mainboard GND
                                                         ├── 36V→12V DC-DC IN−
                                                         ├── 36V→5V DC-DC IN−
                                                         └── Common GND bus
```

**Key points:**
- The 30A blade fuse goes inline on the positive wire, directly at the
  battery. Use a waterproof inline fuse holder.
- The e-stop N.C. contacts are wired in series AFTER the fuse. When
  pressed, they break the 36V supply to the hoverboard (motors stop
  immediately) AND to the DC-DC converters (everything powers down).
- Use XT60 connectors for the battery connection (easy disconnect).
- All grounds share a common bus (terminal block or solder joint). This
  is critical -- the Pixhawk, GPS, hoverboard, and relay module must
  share a common ground.

### 2.3 DC-DC Converter Selection

| Converter | Input Range | Output | Min Current Rating | Example Module |
|-----------|-------------|--------|-------------------|----------------|
| 36V to 12V | 8-60V in | 12V fixed | 3A (5A preferred) | LM2596-based buck, XL4015 |
| 36V to 5V | 8-60V in | 5V fixed | 2A (3A preferred) | LM2596 5V fixed, MP1584 |

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

> The exact protocol number depends on whether you use ArduRover's
> built-in skid-steering output (which sends PWM to motor drivers) or a
> custom Lua script that writes UART commands directly to the hoverboard.
> The simplest approach: configure ArduRover for skid steering
> (`FRAME_TYPE = 0`), route MAIN OUT 1/3 PWM signals through a small
> Arduino/ESP32 translator that converts PWM to the hoverboard UART
> protocol. Alternatively, use a Lua script on the Pixhawk to write
> UART commands directly.

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
SERIAL3_BAUD = 115200
GPS_TYPE = 25              (Unicore UM980)
GPS_RATE_MS = 100          (10 Hz update, or 50 for 20 Hz)
```

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

Pixhawk MAIN OUT 1 (signal wire) ──→ Relay CH1 IN
Pixhawk GND ──────────────────────→ Relay GND
5V BEC ───────────────────────────→ Relay VCC

Relay CH1 COM ──→ 12V DC-DC output (+)
Relay CH1 N.O. ──→ Solenoid valve terminal 1
Solenoid valve terminal 2 ──→ 12V DC-DC output (−) / GND


PUMP CIRCUIT (if using relay control):

Pixhawk MAIN OUT 2 (signal wire) ──→ Relay CH2 IN
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
RELAY1_PIN = 50            (MAIN OUT 1 -- check your Pixhawk's pin mapping)
RELAY2_PIN = 51            (MAIN OUT 2)
RELAY1_DEFAULT = 0         (off at startup)
RELAY2_DEFAULT = 0         (off at startup)
```

Paint on/off is triggered by `DO_SET_RELAY` mission commands or by the
AC_Sprayer library. See the Lua script in `docs/research_report.md` for
waypoint-based paint control.

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

The e-stop button has normally-closed (N.C.) contacts wired in series
with the 36V battery positive line, between the fuse and the hoverboard
mainboard. Pressing the button opens the contacts and immediately kills
power to the motors.

```
Battery (+) ──[30A Fuse]──[E-Stop N.C.]──→ Hoverboard VCC / DC-DC inputs
                                ↑
                          OPEN = motors stop
                          CLOSED = motors run
```

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
- The e-stop must be rated for the full motor stall current (at least
  20A at 36V). If the button's contacts are rated lower, use them to
  drive a 40A relay/contactor coil instead.
- The 30A fuse protects against wiring faults. It does NOT replace the
  e-stop.

---

## 8. Safety Notes

### Wire Gauge Reference

| Circuit | Recommended Gauge | Max Current |
|---------|-------------------|-------------|
| Battery to fuse / e-stop | 14 AWG (12 AWG for Tier 3) | 20-30A |
| Hoverboard mainboard power | 14 AWG | 20A |
| 12V pump / solenoid | 18 AWG | 5A |
| 5V BEC rail | 22 AWG | 2A |
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
      hall sensor cables neatly.

### Phase 2: Power System (Steps 6-8)

- [ ] **6.** Install the 36V e-bike battery on the frame. Wire the battery
      positive through the 30A inline fuse, then through the e-stop
      button N.C. contacts, then to a power distribution point (terminal
      block or bus bar).
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
       Planner. Flash ArduRover firmware. Set `FRAME_TYPE = 0`
       (skid steering).
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
       relay module signal inputs to Pixhawk MAIN OUT 1 and MAIN OUT 2.
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
| MAIN OUT 1-8 | JST-GH (servo rail) | OUT 1: solenoid relay, OUT 2: pump relay |
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
