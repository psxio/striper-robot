# Hoverboard Motor Integration Guide

## Table of Contents

1. [Sourcing Hoverboards](#sourcing-hoverboards)
2. [Hoverboard Internals Overview](#hoverboard-internals-overview)
3. [Flashing FOC Firmware](#flashing-foc-firmware)
4. [FOC Firmware Configuration](#foc-firmware-configuration)
5. [UART Wiring to Pixhawk](#uart-wiring-to-pixhawk)
6. [Testing Motor Control](#testing-motor-control)
7. [Mechanical Integration](#mechanical-integration)
8. [Troubleshooting](#troubleshooting)

---

## Sourcing Hoverboards

Used hoverboards are the cheapest source of high-quality BLDC motors, motor
controllers, and 36V battery packs for robotics projects.

### Where to Buy

| Source | Typical Price | Notes |
|---|---|---|
| Facebook Marketplace | $20-50 | Most common, often with dead batteries |
| OfferUp / Craigslist | $20-60 | Negotiate hard, many are gathering dust |
| Goodwill / thrift stores | $15-40 | Check electronics section, test if possible |
| eBay (used) | $30-80 | Higher prices but reliable shipping |
| Amazon (new, budget) | $80-130 | New boards if you cannot find used |
| Bulk liquidation lots | $10-30 each | Good if building multiple robots |

### What to Look For

- **Working motors**: Spin the wheels by hand. They should turn smoothly with
  slight magnetic cogging. Grinding or roughness means bad bearings.
- **Working mainboard**: The mainboard (STM32-based) is what we flash with FOC
  firmware. It must be functional. Look for burn marks or swollen capacitors.
- **Battery condition matters less**: Even if the battery is dead, the motors
  and mainboard are still usable. You can replace the battery or use a
  different 36V power source.
- **6.5-inch wheels**: The standard size. Some boards have 8" or 10" wheels,
  which also work but change the gear ratio and top speed. Update `WHL_TRACK`
  in the params if you use a different size.
- **Two-board vs one-board design**: Most hoverboards have TWO circuit boards
  (one main board with STM32, one sensor/secondary board). Some newer boards
  have a single board. The FOC firmware supports both designs.

### Common Hoverboard Mainboard Chips

| Chip | Notes |
|---|---|
| GD32F130C8 | Most common. GigaDevice clone of STM32F103C8. Fully supported. |
| STM32F103C8 | Original STMicro chip. Fully supported. |
| GD32F130C6 | 32KB flash variant. Supported but tight on space. |
| AT32F413 | Artery chip. Requires a different firmware fork. |

The FOC firmware repo supports GD32 and STM32 variants. Check your board
before ordering an ST-Link.

---

## Hoverboard Internals Overview

### Mainboard Layout (Typical)

```
+------------------------------------------------------------+
|  HOVERBOARD MAINBOARD (top view)                           |
|                                                             |
|  [Battery connector]    [Power MOSFETs]   [Power MOSFETs]  |
|   + and - from battery    (Left motor)      (Right motor)  |
|                                                             |
|  [STM32/GD32]           [Hall sensor       [Hall sensor    |
|   Main MCU               connector L]       connector R]   |
|                                                             |
|  [USART pads]           [LED/buzzer]       [Gyro sensor]   |
|   TX  RX  GND            connector          (MPU6050)      |
|                                                             |
|  [Sideboards conn L]                    [Sideboards conn R]|
|   (to secondary board)                   (to sensors)      |
+------------------------------------------------------------+
```

### Key Components

- **STM32/GD32 MCU**: The main processor. This is what we flash with FOC firmware.
- **Power MOSFETs**: 6 per motor (3 half-bridges). These drive the BLDC motors.
  They are rated for the motor current and do not need replacement.
- **Hall sensor connectors**: 3-wire Hall effect sensors in each motor provide
  rotor position feedback. The FOC firmware uses these for commutation.
- **USART pads**: Solder points for TX, RX, and GND. This is the UART interface
  we connect to the Pixhawk.
- **Battery connector**: Typically an XT60 or XT30. Accepts 36V (10S lithium).
- **Sideboard connectors**: Connect to the secondary boards (foot sensors, LEDs).
  Not used with FOC firmware but can be repurposed.

### Motor Specifications (Typical 6.5" Hoverboard Motor)

| Specification | Value |
|---|---|
| Type | Brushless DC (BLDC), hub motor |
| Voltage | 36V nominal |
| Power | 250-350W per motor |
| Wheel diameter | 6.5" (165mm) |
| Hall sensors | 3x, built into motor |
| Tire | Solid rubber (no air) |
| Max RPM | ~300 RPM (at 36V) |
| Max speed | ~2.6 m/s with 6.5" wheels |
| Weight per motor | ~2.5 kg |

---

## Flashing FOC Firmware

### Required Hardware

| Item | Purpose | Where to Buy | Cost |
|---|---|---|---|
| ST-Link V2 (or clone) | SWD programming/debug adapter | Amazon, AliExpress | $3-10 |
| Dupont jumper wires (F-F) | Connect ST-Link to mainboard | Amazon | $3 |
| Soldering iron + solder | Solder header pins to UART pads | Any electronics store | -- |
| USB-to-serial adapter (3.3V) | Test UART before connecting Pixhawk | Amazon, FTDI/CP2102 | $5-10 |
| Pin headers (2.54mm) | Solder to USART/SWD pads on the board | Amazon | $2 |

### Required Software

- **STM32CubeProgrammer** (free): https://www.st.com/en/development-tools/stm32cubeprog.html
  Used to flash the firmware via ST-Link SWD.
- **Git**: To clone the firmware repository.
- **Platform IO** or **STM32CubeIDE** (optional): Only if you want to modify
  and recompile the firmware.
- **Serial terminal** (e.g., PuTTY, Tera Term, or `minicom`): For testing UART.

### Step 1: Clone the FOC Firmware Repository

```bash
git clone https://github.com/EFeru/hoverboard-firmware-hack-FOC.git
cd hoverboard-firmware-hack-FOC
```

This is the most actively maintained fork. It supports:
- Field-Oriented Control (FOC) for smooth, efficient motor driving
- UART, PWM, PPM, I2C, and ADC input modes
- Speed mode, torque mode, and voltage mode
- Configurable PID gains for speed control
- Hall sensor and sensorless operation

**Repository**: https://github.com/EFeru/hoverboard-firmware-hack-FOC
**Wiki**: https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki

### Step 2: Identify Your Board Variant

Open the hoverboard and look at the mainboard. Find the main MCU chip and
read the part number printed on it:

- `GD32F130C8T6` or `STM32F103C8T6` -> use the default firmware target
- `GD32F130C6T6` -> use the C6 target (less flash)
- If you see a different chip, check the firmware wiki for compatibility

Also identify the board layout variant by looking at the connector positions
and comparing with the images in the firmware wiki.

### Step 3: Connect the ST-Link V2

Find the SWD (Serial Wire Debug) pads on the mainboard. They are usually
labeled or located near the MCU chip.

| ST-Link Pin | Mainboard Pad | Description |
|---|---|---|
| SWDIO | SWDIO (or DIO) | Serial Wire Data |
| SWCLK | SWCLK (or CLK) | Serial Wire Clock |
| GND | GND | Ground reference |
| 3.3V | 3.3V (optional) | Power from ST-Link (only if board is not powered) |

**Wiring diagram:**

```
ST-Link V2              Hoverboard Mainboard
+----------+            +------------------+
| 3.3V  o--+-----+------o 3.3V (optional)  |
| SWDIO o--+-----+------o SWDIO            |
| SWCLK o--+-----+------o SWCLK            |
| GND   o--+-----+------o GND              |
+----------+            +------------------+
```

**Important notes:**
- Do NOT connect the battery while using ST-Link 3.3V power. Either power
  from the ST-Link OR from the battery, not both.
- If using battery power, connect only SWDIO, SWCLK, and GND from the
  ST-Link. Leave 3.3V disconnected.
- Solder header pins to the SWD pads for reliable connections. Holding wires
  against pads with your fingers will cause intermittent failures.

### Step 4: Configure the Firmware

Edit `Inc/config.h` in the firmware source. Key settings for our robot:

```c
// ===========================================================================
// CONTROL INPUT: UART (serial from Pixhawk)
// ===========================================================================
// Enable UART control on USART2 (main UART, directly connected to pads)
#define CONTROL_SERIAL_USART2

// UART baud rate: must match Pixhawk SERIAL2_BAUD (115 = 115200)
#define USART2_BAUD          115200

// Uncomment to use USART3 instead if your board has pads on USART3:
// #define CONTROL_SERIAL_USART3
// #define USART3_BAUD          115200

// ===========================================================================
// CONTROL MODE: Speed
// ===========================================================================
// Use speed control mode (closed-loop RPM control using Hall sensor feedback)
// This gives the smoothest and most predictable response for a robot.
#define CONTROL_MODE_LEFT    3    // 1=voltage, 2=torque, 3=speed
#define CONTROL_MODE_RIGHT   3

// ===========================================================================
// SPEED PID GAINS
// ===========================================================================
// These tune how aggressively the motor controller tracks the commanded speed.
// Start with these conservative values and increase P if motors are sluggish.
#define SPEED_P              0.004
#define SPEED_I              0.003
#define SPEED_D              0.0
#define SPEED_COEFFICIENT    1.0
#define SPEED_SHIFT          0

// ===========================================================================
// MOTOR DIRECTION
// ===========================================================================
// Invert motor direction if wheels spin the wrong way.
// Test with a low speed command and flip these if needed.
#define INVERT_L_DIRECTION   0    // 0 = normal, 1 = inverted
#define INVERT_R_DIRECTION   0

// ===========================================================================
// SPEED AND CURRENT LIMITS
// ===========================================================================
// Maximum speed (RPM). 6.5" wheel at 300 RPM = ~2.6 m/s
// For a paint robot, we do not need max speed. Limit to 150 RPM (~1.3 m/s)
#define SPEED_MAX_TEST       300  // RPM limit for testing
#define SPEED_MAX            300  // RPM limit in normal operation

// Maximum phase current per motor (Amps). Hoverboard MOSFETs handle 15-20A.
// Limit to 10A for a robot application to reduce heat and stress.
#define I_MOT_MAX            10

// DC current limit (total from battery). Prevents overcurrent on the battery.
#define I_DC_MAX             15

// ===========================================================================
// UART PROTOCOL FORMAT
// ===========================================================================
// The UART protocol sends and receives 2x int16 values:
//   TX from Pixhawk to FOC:  [START, steer (int16), speed (int16), CHECKSUM]
//   RX from FOC to Pixhawk:  [START, cmd1 (int16), cmd2 (int16), speedR, speedL,
//                              batVoltage, boardTemp, cmdLed, CHECKSUM]
//
// Start frame: 0xABCD
// Checksum: XOR of all payload bytes
//
// steer:  -1000 to +1000 (left/right)
// speed:  -1000 to +1000 (forward/reverse)
//
// The Lua script on the Pixhawk converts SERVO1/SERVO3 PWM (1000-2000us)
// to these steer/speed int16 values.

// ===========================================================================
// TIMEOUTS AND SAFETY
// ===========================================================================
// UART receive timeout (ms). If no command received within this time,
// motors stop. Acts as a watchdog.
#define TIMEOUT              500  // 500ms timeout

// Enable electric braking when speed command is 0
#define ELECTRIC_BRAKE_ENABLE   1
#define ELECTRIC_BRAKE_MAX      100  // braking intensity (0-500)

// Standstill hold: apply a small holding torque when stopped
#define STANDSTILL_HOLD_ENABLE  0   // 0=disabled (let wheels freewheel when stopped)

// ===========================================================================
// BUZZER AND LED (optional, can disable for stealth operation)
// ===========================================================================
#define BEEPS_BACKWARD       0    // 0=no beep in reverse
```

### Step 5: Build the Firmware

**Option A: Using PlatformIO (recommended):**

```bash
cd hoverboard-firmware-hack-FOC

# Install PlatformIO CLI if not already installed:
pip install platformio

# Build for GD32 (most common hoverboard chip):
pio run -e VARIANT_HOVERBOARD

# The compiled binary is at:
# .pio/build/VARIANT_HOVERBOARD/firmware.bin
```

**Option B: Using STM32CubeIDE:**

1. Open STM32CubeIDE
2. File > Import > Existing Projects into Workspace
3. Select the firmware directory
4. Build (hammer icon or Ctrl+B)
5. The `.bin` file is in the `build/` directory

**Option C: Using Makefile (Linux/WSL):**

```bash
# Install ARM toolchain
sudo apt install gcc-arm-none-eabi

# Build
make
# Output: build/hover.bin
```

### Step 6: Flash the Firmware

**Using STM32CubeProgrammer:**

1. Connect the ST-Link V2 to the mainboard (see Step 3)
2. Open STM32CubeProgrammer
3. Select "ST-LINK" as the connection method (top-right dropdown)
4. Click "Connect" -- you should see the chip ID and memory contents
5. If "Connect" fails:
   - Check wiring (SWDIO, SWCLK, GND)
   - Try holding the board's RESET button while clicking Connect
   - Check that the ST-Link driver is installed
6. Click "Open File" and select the compiled `.bin` file
7. Set the start address to `0x08000000`
8. Click "Download" to flash
9. Click "Disconnect" when done
10. Remove the ST-Link wires

**Using ST-Link utility (command line):**

```bash
# Linux:
st-flash write firmware.bin 0x08000000

# Or using OpenOCD:
openocd -f interface/stlink-v2.cfg -f target/stm32f1x.cfg \
  -c "program firmware.bin 0x08000000 verify reset exit"
```

**Important: Read-out protection (RDP)**
Many hoverboards ship with flash read-out protection enabled. You must
disable it before flashing:

1. In STM32CubeProgrammer, go to Option Bytes (OB icon on the left)
2. Set RDP to "Level 0" (no protection)
3. Click "Apply"
4. **WARNING**: This erases the original firmware permanently. You cannot
   go back to the stock hoverboard firmware after this step.

---

## FOC Firmware Configuration

### Understanding the UART Protocol

The FOC firmware uses a simple binary protocol over UART:

**Command packet (Pixhawk to FOC board):**

```
Byte 0-1:  Start frame marker (0xABCD, little-endian: 0xCD, 0xAB)
Byte 2-3:  steer value (int16, little-endian, range: -1000 to +1000)
Byte 4-5:  speed value (int16, little-endian, range: -1000 to +1000)
Byte 6-7:  Checksum (XOR of bytes 2-5)
```

**Feedback packet (FOC board to Pixhawk):**

```
Byte 0-1:  Start frame marker (0xABCD)
Byte 2-3:  cmd1 feedback (int16)
Byte 4-5:  cmd2 feedback (int16)
Byte 6-7:  right motor speed (int16, RPM)
Byte 8-9:  left motor speed (int16, RPM)
Byte 10-11: battery voltage (int16, fixed point x100)
Byte 12-13: board temperature (int16, degrees C x10)
Byte 14-15: cmdLed (int16)
Byte 16-17: Checksum (XOR of bytes 2-15)
```

### Speed vs. Steer Mode

There are two ways to command the motors over UART:

**Mode 1: steer + speed (default)**

The `steer` value controls differential steering and `speed` controls forward
speed. The firmware internally converts these to left/right motor speeds:
- Left motor  = speed + steer
- Right motor = speed - steer

**Mode 2: independent left/right speed**

Set `#define CONTROL_IBUS` or modify the firmware to accept two independent
speed values instead of steer+speed. This gives the Pixhawk direct control
over each wheel and may be more predictable for a differential-drive robot.

For our application, either mode works. The Lua bridge script on the Pixhawk
handles the conversion from ArduRover's ThrottleLeft/ThrottleRight (SERVO1/
SERVO3) outputs to the appropriate UART format.

### PID Tuning for Speed Mode

The FOC firmware has its own PID loop for motor speed control (separate from
ArduRover's navigation PID). Tune these values for your specific load:

| Parameter | Default | Robot Recommendation | Effect |
|---|---|---|---|
| SPEED_P | 0.004 | 0.004 - 0.010 | Proportional: increases with load mass |
| SPEED_I | 0.003 | 0.003 - 0.005 | Integral: eliminates steady-state error |
| SPEED_D | 0.0 | 0.0 - 0.001 | Derivative: damps oscillation (usually 0) |

**Tuning procedure:**
1. Start with the default values
2. Command a constant speed (e.g., 200 RPM)
3. If the motor responds sluggishly: increase P
4. If the motor oscillates at constant speed: decrease P, add a tiny D
5. If the motor does not reach the exact commanded speed: increase I
6. For a ~50kg robot, you may need P=0.006 to 0.010 depending on surface

---

## UART Wiring to Pixhawk

### Soldering UART Pads

Most hoverboard mainboards have exposed pads labeled TX, RX, and GND
(sometimes near the STM32 chip, sometimes near the edge of the board).

1. Identify the UART pads on your mainboard. Refer to the firmware wiki
   for your specific board variant:
   https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki

2. Solder 3 wires (or a 3-pin header) to the TX, RX, and GND pads.
   Use stranded wire for flexibility if the board will be mounted in the robot.

3. **Check which USART the pads connect to** (USART2 or USART3). This must
   match the `#define` in `config.h`:
   - If pads are on USART2: use `#define CONTROL_SERIAL_USART2`
   - If pads are on USART3: use `#define CONTROL_SERIAL_USART3`

### Connection to Pixhawk TELEM2

| Hoverboard Pad | Wire | Pixhawk TELEM2 Pin | Notes |
|---|---|---|---|
| TX | Signal out | Pin 3 (RX) | FOC transmits feedback to Pixhawk |
| RX | Signal in | Pin 2 (TX) | Pixhawk sends commands to FOC |
| GND | Ground | Pin 6 (GND) | Common ground required |

**The Pixhawk TELEM2 connector is JST-GH 6-pin:**

```
Pin 1: VCC (5V) -- DO NOT CONNECT to hoverboard
Pin 2: TX  (Pixhawk transmit) --> connect to hoverboard RX
Pin 3: RX  (Pixhawk receive)  --> connect to hoverboard TX
Pin 4: CTS -- not used
Pin 5: RTS -- not used
Pin 6: GND --> connect to hoverboard GND
```

**Critical warnings:**
- Do NOT connect Pin 1 (5V) to the hoverboard. The hoverboard runs on 36V
  and has its own 3.3V regulator. Connecting 5V could damage the board.
- Both the Pixhawk and the hoverboard MCU use 3.3V logic levels on their
  UART pins. No level shifter is needed.
- The GND connection is essential. Without a common ground reference, the
  UART signals will be unreliable.

### Cable Routing

- Route the UART cable away from the motor phase wires (the thick wires
  carrying high-current AC to the motors). Motor phase noise can corrupt
  UART data.
- Use shielded cable or twisted pair if the cable run is longer than 30cm.
- Secure the cable so it cannot be caught in the wheels.

---

## Testing Motor Control

### Test 1: Verify FOC Firmware is Running

After flashing, power the mainboard from the battery (or a 36V power supply):

1. The board should beep briefly (startup tone)
2. If using the LED connector, the LED may blink
3. If no beep or LED: check that the firmware was flashed correctly
4. If the board beeps continuously: there may be a motor or Hall sensor error

### Test 2: UART Communication with USB-to-Serial Adapter

Before connecting to the Pixhawk, test with a USB-to-serial adapter (3.3V
logic level, e.g., FTDI FT232RL or CP2102).

**Wiring:**

```
USB-to-Serial         Hoverboard Mainboard
+-----------+         +------------------+
| TX   o----+---------o RX               |
| RX   o----+---------o TX               |
| GND  o----+---------o GND              |
+-----------+         +------------------+
```

**Power the hoverboard from its battery** (not from the USB adapter).

**Send a test command** using a serial terminal (PuTTY, Tera Term, or minicom):

Settings: 115200 baud, 8N1 (8 data bits, no parity, 1 stop bit)

You can use the Python test script from the firmware repo:

```python
#!/usr/bin/env python3
"""
Test script for hoverboard FOC firmware UART control.
Sends a low-speed command and reads feedback.
"""
import serial
import struct
import time

# Open serial port (adjust port name for your system)
# Windows: 'COM3', Linux: '/dev/ttyUSB0', macOS: '/dev/tty.usbserial-xxxx'
ser = serial.Serial('COM3', 115200, timeout=0.1)

def send_command(steer, speed):
    """Send steer and speed command to the hoverboard."""
    # Pack as little-endian int16 values
    payload = struct.pack('<hh', steer, speed)
    # Calculate checksum (XOR of all payload bytes, as uint16)
    checksum = 0
    for i in range(0, len(payload), 2):
        checksum ^= struct.unpack('<H', payload[i:i+2])[0]
    # Build frame: start marker + payload + checksum
    frame = struct.pack('<H', 0xABCD) + payload + struct.pack('<H', checksum)
    ser.write(frame)

def read_feedback():
    """Read and parse feedback from the hoverboard."""
    data = ser.read(18)  # feedback frame is 18 bytes
    if len(data) == 18:
        start = struct.unpack('<H', data[0:2])[0]
        if start == 0xABCD:
            cmd1, cmd2, speedR, speedL, batV, temp, led = struct.unpack(
                '<hhhhhhh', data[2:16])
            print(f"SpeedR={speedR} SpeedL={speedL} Bat={batV/100.0:.1f}V "
                  f"Temp={temp/10.0:.1f}C")
            return True
    return False

# Test: send low speed forward, zero steering
print("Sending speed=100, steer=0 (gentle forward)")
print("Press Ctrl+C to stop")
print()

try:
    while True:
        send_command(steer=0, speed=100)  # gentle forward
        read_feedback()
        time.sleep(0.05)  # 20Hz update rate
except KeyboardInterrupt:
    # Stop motors
    send_command(steer=0, speed=0)
    print("\nMotors stopped.")
    ser.close()
```

**Expected behavior:**
- The wheels should spin slowly forward
- The terminal should show feedback with speed, battery voltage, and temperature
- Press Ctrl+C to stop

### Test 3: Motor Direction Verification

Send positive speed (+100) and verify both wheels spin in the same direction
(forward). If one wheel spins backward:

1. Check `INVERT_L_DIRECTION` and `INVERT_R_DIRECTION` in `config.h`
2. Flip the inverted motor's setting (0 to 1 or 1 to 0)
3. Rebuild and reflash the firmware
4. Retest

### Test 4: Steering Response

Send steer=+200 with speed=100. The robot should turn right (left wheel
faster, right wheel slower). If it turns the wrong way, invert the steer
sign in the Lua bridge script on the Pixhawk.

### Test 5: Full Speed Range

Gradually increase speed from 0 to 500 in steps of 50. Verify:
- Motors accelerate smoothly without jerking
- No overcurrent warnings (beeping)
- Board temperature stays reasonable (under 50C)
- Battery voltage does not sag excessively under load

---

## Mechanical Integration

### Mounting the Motors

Hoverboard hub motors mount using the axle bolt that originally held the
hoverboard frame. Options:

1. **Use the original hoverboard frame**: Cut the hoverboard frame in half.
   Each half has a motor mount, wheel, and mudguard. Bolt these to your
   robot chassis.

2. **Custom axle mount**: Machine or 3D-print axle brackets. The motor axle
   is typically 8mm diameter. Use U-bolts, clamps, or bearing blocks.

3. **Plate mount**: Bolt the motor forks directly to a flat plate using the
   existing holes in the hoverboard frame arms.

### Motor Cable Management

Each motor has 5 wires:
- **3 thick phase wires** (motor power, typically yellow/green/blue)
- **5 thin Hall sensor wires** (5V, GND, Hall A, Hall B, Hall C in a JST connector)

Route these cables through the chassis with strain relief. Keep phase wires
away from the UART and GPS cables to prevent electromagnetic interference.

### Weight Distribution

For a ~50kg robot:
- Center of gravity should be between the two drive wheels
- If the nozzle and paint tank are at the front, add a caster wheel for
  stability
- The GPS antenna should be at the highest point, centered if possible
- The battery should be low and centered for stability

---

## Troubleshooting

### ST-Link Cannot Connect to Mainboard

- Verify SWDIO and SWCLK wires are making good contact (solder, do not
  just press wires against pads)
- Try holding the RESET button on the mainboard while clicking Connect
- Check that the ST-Link driver is installed (device should appear in
  Device Manager on Windows)
- If read-out protection is enabled, you must first disable RDP in
  STM32CubeProgrammer's Option Bytes before flashing

### Motors Do Not Spin After Flashing

- Verify the correct chip variant was selected during build
  (GD32 vs STM32, C8 vs C6)
- Check that Hall sensor connectors are plugged in correctly
- Check motor phase wire connections (each motor has 3 phase wires)
- Listen for error beep codes (refer to firmware wiki)
- Check `CONTROL_SERIAL_USART2` vs `USART3` matches your board's pads

### Motors Spin But in the Wrong Direction

- Change `INVERT_L_DIRECTION` or `INVERT_R_DIRECTION` in config.h
- Rebuild and reflash
- Alternatively, swap any two of the three phase wires on the affected motor

### UART Communication Fails

- Verify baud rate: both sides must be 115200
- Check TX/RX crossover: Pixhawk TX goes to hoverboard RX and vice versa
- Verify common GND connection
- Use an oscilloscope or logic analyzer to verify signals on the UART lines
- If using long wires (>30cm), add 100-ohm termination resistors

### Motors Stutter or Jerk

- Hall sensor issue: check connector and wires. A broken Hall wire causes
  commutation errors.
- PID gains too aggressive: reduce SPEED_P
- Motor phase wire issue: check all 3 phase connections per motor
- Power supply issue: verify battery voltage is above 30V under load

### Board Overheats

- Reduce `I_MOT_MAX` to limit motor current
- Reduce `I_DC_MAX` to limit total current
- Add heatsinks to the MOSFETs if operating at high continuous load
- Check for short circuits in the wiring
- Reduce maximum speed to lower the duty cycle

---

## Reference Links

- **FOC Firmware Repository**: https://github.com/EFeru/hoverboard-firmware-hack-FOC
- **Firmware Wiki (board variants, wiring diagrams)**: https://github.com/EFeru/hoverboard-firmware-hack-FOC/wiki
- **Firmware Configuration Generator**: https://eferu.github.io/hoverboard-firmware-hack-FOC/
- **STM32CubeProgrammer**: https://www.st.com/en/development-tools/stm32cubeprog.html
- **PlatformIO**: https://platformio.org/
- **Hoverboard motor specs and teardown**: https://hackaday.io/project/170932-hoverboard-motor-controller
- **ArduPilot Lua scripting for serial devices**: https://ardupilot.org/rover/docs/common-lua-scripts.html
- **FOC firmware Discord community**: Link in the firmware repo README
