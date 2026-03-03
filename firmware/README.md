# ESP32 Motor Controller Firmware

Firmware for the autonomous line-striping robot's drive system.  Runs on an
ESP32 dev board and communicates with the ROS 2 `motor_driver_node` over USB
serial.

## Features

- Dual brushed-DC motor control through an H-bridge (L298N or BTS7960)
- Interrupt-driven x4 quadrature encoder decoding
- PID speed control (rad/s setpoint from ROS 2)
- 500 ms watchdog -- motors stop automatically if the host goes silent
- Status LED blink patterns (idle / driving / watchdog tripped)

## Serial Protocol

| Direction      | Format                              | Example               |
|----------------|-------------------------------------|-----------------------|
| Host -> ESP32  | `M,<left_rad_s>,<right_rad_s>\n`    | `M,1.500,-1.500\n`   |
| ESP32 -> Host  | `E,<left_ticks>,<right_ticks>\n`    | `E,14320,-14280\n`   |

Baud rate: **115200** (configurable in `config.h`).

## Hardware Requirements

- ESP32 development board (ESP32-DevKitC, NodeMCU-32S, etc.)
- L298N or BTS7960 dual H-bridge motor driver
- Two DC gear-motors with quadrature encoders
- 12 V battery (motor power)
- USB cable for serial communication with the host computer

## Wiring Diagram

```
                         ESP32 Dev Board
                    +-----------------------+
                    |                       |
         GPIO 25 --| LEFT_MOTOR_PWM    3V3 |-- Encoder VCC
         GPIO 26 --| LEFT_MOTOR_DIR1       |
         GPIO 27 --| LEFT_MOTOR_DIR2       |
                    |                       |
         GPIO 14 --| RIGHT_MOTOR_PWM       |
         GPIO 12 --| RIGHT_MOTOR_DIR1      |
         GPIO 13 --| RIGHT_MOTOR_DIR2      |
                    |                       |
         GPIO 34 --| LEFT_ENC_A            |
         GPIO 35 --| LEFT_ENC_B            |
         GPIO 36 --| RIGHT_ENC_A           |
         GPIO 39 --| RIGHT_ENC_B           |
                    |                       |
          GPIO 2 --| STATUS_LED (built-in) |
                    |                       |
              GND --| GND              GND |-- Motor Driver GND
                    +-----------------------+

         L298N / BTS7960 Motor Driver
    +-------------------------------------+
    |                                     |
    |  ENA / RPWM_L <-- GPIO 25          |
    |  IN1 / R_EN_L <-- GPIO 26          |   Left
    |  IN2 / L_EN_L <-- GPIO 27          |   Motor
    |  OUT1, OUT2   --> Left Motor        |
    |                                     |
    |  ENB / RPWM_R <-- GPIO 14          |
    |  IN3 / R_EN_R <-- GPIO 12          |   Right
    |  IN4 / L_EN_R <-- GPIO 13          |   Motor
    |  OUT3, OUT4   --> Right Motor       |
    |                                     |
    |  VCC          <-- 12 V Battery (+)  |
    |  GND          <-- Battery (-) & ESP |
    +-------------------------------------+

    Encoder Connections (repeat for each motor):
        Encoder VCC --> ESP32 3.3 V
        Encoder GND --> ESP32 GND
        Encoder A   --> ESP32 GPIO (see pin table above)
        Encoder B   --> ESP32 GPIO (see pin table above)
```

**Important notes on pins:**

- GPIOs 34, 35, 36, 39 are input-only on the ESP32 -- perfect for encoders.
- GPIO 2 is the built-in LED on most ESP32 boards.
- All pin assignments can be changed in `config.h`.

## Building and Flashing

### Arduino IDE

1. **Install ESP32 board support:**
   - Open *File > Preferences*.
   - Add this URL to *Additional Board Manager URLs*:
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Open *Tools > Board > Boards Manager*, search for "esp32", install
     **esp32 by Espressif Systems**.

2. **Select your board:**
   - *Tools > Board > ESP32 Arduino > ESP32 Dev Module*
   - *Tools > Upload Speed*: 921600
   - *Tools > Port*: select the COM/ttyUSB port of your ESP32

3. **Open the sketch:**
   - *File > Open* and navigate to
     `firmware/esp32_motor_controller/esp32_motor_controller.ino`.
   - Arduino IDE will automatically pick up all `.h` and `.cpp` files in the
     same directory.

4. **Upload:**
   - Click the Upload button (right-arrow icon).

### PlatformIO (alternative)

```bash
cd firmware/esp32_motor_controller
# Create a platformio.ini if you prefer PlatformIO:
# [env:esp32dev]
# platform = espressif32
# board = esp32dev
# framework = arduino
pio run --target upload
```

No external libraries are required -- the firmware uses only the Arduino core
and ESP32 LEDC built-ins.

## Configuration

All tuneable parameters live in `config.h`:

| Parameter              | Default | Description                        |
|------------------------|---------|------------------------------------|
| `SERIAL_BAUD_RATE`     | 115200  | Must match motor_driver_node.py    |
| `ENCODER_TICKS_PER_REV`| 1440   | Encoder CPR x4 (after decoding)    |
| `WHEEL_RADIUS_M`       | 0.075  | Wheel radius in metres             |
| `WHEEL_SEPARATION_M`   | 0.40   | Wheel-to-wheel distance in metres  |
| `PID_KP`               | 2.0    | Proportional gain                  |
| `PID_KI`               | 5.0    | Integral gain                      |
| `PID_KD`               | 0.01   | Derivative gain                    |
| `CONTROL_LOOP_INTERVAL_MS` | 50 | Control loop period (20 Hz)        |
| `WATCHDOG_TIMEOUT_MS`  | 500    | Stop motors after this silence     |

## PID Tuning

1. Set `PID_KI` and `PID_KD` to 0.
2. Increase `PID_KP` until the motor responds quickly but does not oscillate.
3. Slowly increase `PID_KI` to eliminate steady-state error.
4. Add a small `PID_KD` if there is overshoot.

You can also monitor the PID behaviour by temporarily adding debug prints
in the main loop (e.g. printing setpoint, measured velocity, and PWM output).

## File Structure

```
firmware/esp32_motor_controller/
    esp32_motor_controller.ino   -- Main sketch (setup/loop, serial protocol)
    config.h                     -- All pin and parameter definitions
    motor.h / motor.cpp          -- Motor driver abstraction
    encoder.h / encoder.cpp      -- Quadrature encoder reader
    pid.h / pid.cpp              -- PID controller with anti-windup
```

## Troubleshooting

- **Motors do not spin:** Check wiring, verify 12 V supply to the H-bridge,
  confirm GPIO assignments in `config.h`.
- **Encoders read zero:** Ensure encoder VCC is 3.3 V (not 5 V unless your
  encoder is 5 V tolerant and you have level shifters).  Check that the
  encoder A/B pins match `config.h`.
- **Watchdog keeps tripping:** Verify the USB serial connection is active
  and `motor_driver_node` is running.  Check baud rate matches on both sides.
- **Motors oscillate:** Reduce `PID_KP`.  If they are sluggish, increase it
  gradually.
