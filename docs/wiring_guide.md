# Striper Robot -- Hardware Wiring Guide

Complete wiring reference for the autonomous line-striping robot. This
document covers the system architecture, every pin assignment, power
distribution, the safety circuit, and a step-by-step assembly checklist.

---

## 1. System Architecture Diagram

```
                            +=============================+
                            |   24 V 30 Ah LiFePO4 PACK  |
                            +=============================+
                               |            |          |
                               |            |          |
                         +-----+---+  +-----+---+  +--+--------+
                         | 24V->5V |  | 24V->12V|  | 24V direct|
                         | DC-DC   |  | DC-DC   |  | (motors)  |
                         | (5A)    |  | (3A)    |  |           |
                         +----+----+  +----+----+  +-----+-----+
                              |            |              |
                              |            |              |
         +====================+=====+      |     +========+========+
         |    Raspberry Pi 5 (5V)   |      |     |  E-STOP RELAY   |
         |                          |      |     | (N.C. contacts) |
         |  USB0: ZED-F9P GPS ------+----------->[breaks 24V to   ]
         |  USB1: (spare / WiFi)    |      |     [ motor drivers  ]
         |                          |      |     +========+========+
         |  I2C1 (SDA=2, SCL=3):   |      |              |
         |    BNO085 IMU @ 0x4A     |      |              |
         |                          |      |     +--------+--------+
         |  UART TX/RX (GPIO 14/15):|      |     |   BTS7960 x2    |
         |    ESP32 serial link ----+------+---->|  Motor Drivers   |
         |                          |      |     +---+---------+---+
         |  GPIO 17: paint solenoid-+--+   |         |         |
         |  GPIO 27: e-stop input   |  |   |     +---+---+ +---+---+
         |  GPIO 22: LED green      |  |   |     | LEFT  | | RIGHT |
         |  GPIO 23: LED red        |  |   |     | MOTOR | | MOTOR |
         |  GPIO 24: LED blue       |  |   |     | 24V   | | 24V   |
         |  GPIO  5: US FL trig     |  |   |     +-------+ +-------+
         |  GPIO  6: US FL echo     |  |   |
         |  GPIO 13: US FR trig     |  |   |
         |  GPIO 19: US FR echo     |  |   |
         +==========================+  |   |
                                       |   |
              +------------------------+   |
              |                            |
         +----+----+              +--------+--------+
         | MOSFET  |              | 12V SOLENOID    |
         | driver  +------------->| VALVE (paint)   |
         | (logic- |              +-----------------+
         |  level) |
         +---------+

         +==========================+
         |        ESP32             |
         |  (Motor Controller FW)   |
         |                          |
         |  RX/TX: serial to RPi   |
         |                          |
         |  GPIO 25: L motor PWM   |
         |  GPIO 26: L motor DIR1  |
         |  GPIO 27: L motor DIR2  |
         |  GPIO 14: R motor PWM   |
         |  GPIO 12: R motor DIR1  |
         |  GPIO 13: R motor DIR2  |
         |                          |
         |  GPIO 34: L encoder A   |
         |  GPIO 35: L encoder B   |
         |  GPIO 36: R encoder A   |
         |  GPIO 39: R encoder B   |
         |                          |
         |  GPIO  2: status LED    |
         +==========================+
```

### Data Flow Summary

```
GPS (USB) --> RPi gps_node --> /gps/fix
                                  |
                                  v
                          ntrip_client_node --> NTRIP caster (Internet)
                                  |                    |
                                  |   <-- RTCM3 ------+
                                  v
                          /rtcm_corrections --> gps_node --> ZED-F9P
                                                  |
                                                  v
IMU (I2C) --> RPi imu_node --> /imu/data --> robot_localization (EKF)
                                                  |
                                                  v
                                          /odometry/global --> Nav2
                                                  |
                                                  v
                                  /cmd_vel --> motor_driver_node
                                                  |
                                          UART serial link
                                                  |
                                                  v
                                        ESP32 motor controller
                                          |               |
                                     Left motor      Right motor
                                     + encoder       + encoder
```

---

## 2. Pin Assignment Tables

### 2.1 Raspberry Pi 5 GPIO (BCM numbering)

| BCM Pin | Physical Pin | Function               | Direction | Notes                          |
|---------|-------------|------------------------|-----------|--------------------------------|
| 2       | 3           | I2C1 SDA               | bidir     | BNO085 IMU data                |
| 3       | 5           | I2C1 SCL               | bidir     | BNO085 IMU clock               |
| 5       | 29          | Ultrasonic FL trigger   | OUT       | Front-left HC-SR04 trigger     |
| 6       | 31          | Ultrasonic FL echo      | IN        | Front-left HC-SR04 echo (3.3V) |
| 13      | 33          | Ultrasonic FR trigger   | OUT       | Front-right HC-SR04 trigger    |
| 14      | 8           | UART TX                 | OUT       | Serial to ESP32 RX             |
| 15      | 10          | UART RX                 | IN        | Serial from ESP32 TX           |
| 17      | 11          | Paint solenoid control   | OUT       | MOSFET gate -> 12V solenoid    |
| 19      | 35          | Ultrasonic FR echo      | IN        | Front-right HC-SR04 echo (3.3V)|
| 22      | 15          | Status LED green        | OUT       | RGB status indicator           |
| 23      | 16          | Status LED red          | OUT       | RGB status indicator           |
| 24      | 18          | Status LED blue         | OUT       | RGB status indicator           |
| 27      | 13          | E-stop input            | IN        | Pulled HIGH; LOW = e-stop      |

### 2.2 USB Port Assignments (Raspberry Pi 5)

| Port    | Device                     | Baud Rate | Protocol     |
|---------|----------------------------|-----------|------------- |
| USB 0   | u-blox ZED-F9P GPS         | 115200    | NMEA / UBX   |
| USB 1   | (spare / Wi-Fi adapter)    | --        | --           |

### 2.3 I2C Bus Assignments

| Bus   | Address | Device        | Voltage | Pull-ups    |
|-------|---------|---------------|---------|-------------|
| I2C1  | 0x4A   | BNO085 IMU    | 3.3V    | On breakout |

### 2.4 ESP32 GPIO (motor controller firmware)

| GPIO | Function               | Direction | Notes                            |
|------|------------------------|-----------|----------------------------------|
| 25   | Left motor PWM         | OUT       | LEDC ch0, 20 kHz, 8-bit         |
| 26   | Left motor DIR1        | OUT       | IN1 / R_EN on H-bridge          |
| 27   | Left motor DIR2        | OUT       | IN2 / L_EN on H-bridge          |
| 14   | Right motor PWM        | OUT       | LEDC ch1, 20 kHz, 8-bit         |
| 12   | Right motor DIR1       | OUT       | IN3 / R_EN on H-bridge          |
| 13   | Right motor DIR2       | OUT       | IN4 / L_EN on H-bridge          |
| 34   | Left encoder A         | IN        | Interrupt-driven, input-only pin |
| 35   | Left encoder B         | IN        | Interrupt-driven, input-only pin |
| 36   | Right encoder A        | IN        | VP pin, input-only               |
| 39   | Right encoder B        | IN        | VN pin, input-only               |
| 2    | Status LED             | OUT       | On-board LED                     |
| RX0  | Serial from RPi TX     | IN        | 115200 baud                      |
| TX0  | Serial to RPi RX       | OUT       | 115200 baud                      |

---

## 3. Power Budget

### 3.1 Component Power Draw

| Component               | Voltage | Typical Current | Peak Current | Power (typ) |
|--------------------------|---------|-----------------|--------------|-------------|
| Raspberry Pi 5           | 5V      | 3.0 A           | 5.0 A        | 15.0 W      |
| ESP32 DevKit             | 3.3V*   | 0.24 A          | 0.5 A        | 0.8 W       |
| Left drive motor         | 24V     | 1.5 A           | 8.0 A (stall)| 36.0 W      |
| Right drive motor        | 24V     | 1.5 A           | 8.0 A (stall)| 36.0 W      |
| BTS7960 driver x2        | 24V     | 0.05 A          | --           | 2.4 W       |
| Paint solenoid valve     | 12V     | 2.0 A           | 2.5 A        | 24.0 W      |
| u-blox ZED-F9P GPS       | 5V      | 0.15 A          | 0.2 A        | 0.75 W      |
| BNO085 IMU               | 3.3V    | 0.04 A          | 0.05 A       | 0.13 W      |
| Ultrasonic sensors x2    | 5V      | 0.03 A          | 0.04 A       | 0.15 W      |
| RGB status LEDs          | 3.3V    | 0.06 A          | 0.06 A       | 0.20 W      |
| **TOTAL (typical)**      |         |                 |              | **115.4 W** |
| **TOTAL (peak/stall)**   |         |                 |              | **~220 W**  |

*ESP32 is powered from its on-board USB regulator or a 3.3V rail from the 5V converter.*

### 3.2 DC-DC Converter Requirements

| Converter   | Input  | Output  | Min Rating         | Notes                          |
|-------------|--------|---------|--------------------|--------------------------------|
| 24V -> 5V   | 24V    | 5V      | 6 A (30 W)         | RPi 5 + GPS + ultrasonics      |
| 24V -> 12V  | 24V    | 12V     | 3 A (36 W)         | Solenoid valve                 |
| Direct 24V  | 24V    | 24V     | 20 A (fused/relay) | Motor drivers (through e-stop) |

### 3.3 Battery Life Estimate

| Scenario                  | Avg Draw | 24V 30 Ah Battery | Runtime   |
|---------------------------|----------|--------------------|-----------|
| Driving + painting        | ~4.8 A @ 24V (115 W) | 720 Wh    | ~6.3 hours |
| Driving only (no paint)   | ~3.8 A @ 24V (91 W)  | 720 Wh    | ~7.9 hours |
| Idle (compute only)       | ~0.7 A @ 24V (17 W)  | 720 Wh    | ~42 hours  |

---

## 4. Safety Circuit (E-Stop)

The e-stop provides **two independent safety mechanisms**: a hardware motor
power cutoff and a software signal to the Raspberry Pi.

### 4.1 Circuit Design

```
                24V BATTERY
                    |
                    |
             +------+------+
             |  MAIN FUSE  |  (30A blade fuse)
             |   (30 A)    |
             +------+------+
                    |
        +-----------+-----------+
        |                       |
   +----+----+            +-----+-----+
   | E-STOP  |            | E-STOP    |
   | BUTTON  |            | BUTTON    |
   | (N.C.   |            | (N.C.     |
   | contact |            | contact   |
   | pair 1) |            | pair 2)   |
   +----+----+            +-----+-----+
        |                       |
        |  [Motor 24V rail]     |  [RPi signal]
        |                       |
   +----+----+            +-----+-----+
   | CONTACTOR|           | Voltage   |
   | or RELAY |           | divider   |
   | (30A)    |           | 24V->3.3V |
   +----+----+            +-----+-----+
        |                       |
   +----+----+                  +-----> RPi GPIO 27 (e-stop input)
   |BTS7960  |                          (internal pull-up enabled;
   |drivers  |                           LOW = e-stop pressed)
   |(24V in) |
   +----+----+
        |
   +----+----+
   | MOTORS  |
   +---------+
```

### 4.2 How It Works

1. **Normal operation**: The e-stop button is in its released position. The
   normally-closed (N.C.) contacts are closed. 24V flows through contact
   pair 1 to the motor drivers. Contact pair 2 holds RPi GPIO 27 HIGH
   through a voltage divider.

2. **E-stop pressed**: Both N.C. contact pairs open simultaneously.
   - **Pair 1** immediately breaks the 24V supply to the BTS7960 motor
     drivers. Motors coast to a stop. This is a hard electrical cutoff
     that does not depend on any software.
   - **Pair 2** pulls RPi GPIO 27 LOW (through the pull-down resistor in
     the voltage divider). The safety_supervisor node detects the LOW
     signal and triggers a software emergency stop: it commands zero
     velocity, closes the paint valve, and publishes an e-stop event.

3. **Recovery**: The operator twists/pulls the e-stop button to reset it.
   N.C. contacts close again. GPIO 27 goes HIGH. The safety_supervisor
   re-enables the system after a configurable holdoff period (default 3
   seconds).

### 4.3 Key Design Rules

- The e-stop button must have at least **two independent N.C. contact pairs**
  (one for power, one for signaling).
- The motor power cutoff pair must be rated for the full stall current of
  both motors combined (at least 20 A at 24 V).
- The 30 A main fuse protects against wiring faults; it does **not** replace
  the e-stop.
- The signal path to GPIO 27 uses a **voltage divider** (10k + 5.6k) to
  bring 24V down to ~3.3V, plus a 3.3V zener clamp for protection.
- GPIO 27 has its internal pull-up enabled so that a broken wire reads as
  HIGH (safe default = assume e-stop is NOT pressed only when the circuit
  actively drives the pin HIGH). If using a voltage divider from the
  second N.C. pair, the divider drives the pin HIGH when contacts are
  closed. If the wire breaks, the pull-up keeps it HIGH, so the design
  should add a pull-DOWN or invert the logic so that a broken wire is
  treated as e-stop active. **Recommended**: use the RPi internal pull-down
  on GPIO 27 and read HIGH = e-stop released, LOW = e-stop pressed or
  wire fault.

---

## 5. Step-by-Step Assembly Checklist

Follow this order to build and test each subsystem incrementally. Do not
proceed to the next step until the current step is verified.

### Phase 1: Compute Platform

- [ ] 1. Mount the Raspberry Pi 5 to the chassis with standoffs.
- [ ] 2. Install the 24V-to-5V DC-DC converter. Connect its output to the
         RPi 5V GPIO header pins (pin 2/4 = 5V, pin 6 = GND) **or** to the
         USB-C power input via a USB-C PD trigger board.
- [ ] 3. Power on the RPi with the 24V battery. Verify boot, SSH access,
         and ROS 2 installation.
- [ ] 4. Connect the ESP32 DevKit to the RPi via UART (RPi GPIO 14 TX ->
         ESP32 RX0, RPi GPIO 15 RX -> ESP32 TX0, common GND). Power the
         ESP32 from the 5V rail.
- [ ] 5. Flash the ESP32 motor controller firmware. Verify serial comms by
         running `ros2 run striper_hardware motor_driver` and checking for
         mock encoder data.

### Phase 2: Drive System

- [ ] 6. Wire the two BTS7960 motor drivers: power input from 24V rail,
         PWM/DIR pins from ESP32 (see ESP32 pin table above).
- [ ] 7. Connect the left motor to driver 1, right motor to driver 2.
         **Do not connect encoders yet.**
- [ ] 8. With wheels off the ground (robot on blocks), send test `cmd_vel`
         commands. Verify both motors spin in the correct direction. If a
         motor spins backward, swap DIR1/DIR2 wires or invert in firmware.
- [ ] 9. Connect quadrature encoders (ESP32 GPIO 34/35 for left, 36/39
         for right). Verify tick counts increase when wheels are spun
         forward by hand.
- [ ] 10. Run a closed-loop PID test: send a low `cmd_vel` and verify
          smooth, controlled wheel motion.

### Phase 3: Positioning

- [ ] 11. Connect the u-blox ZED-F9P GPS module to RPi USB port 0. Verify
          it appears as `/dev/ttyACM0`.
- [ ] 12. Run `ros2 run striper_hardware gps_node`. Verify `/gps/fix`
          publishes valid latitude/longitude. Take the robot outdoors for
          this test.
- [ ] 13. Connect the BNO085 IMU breakout to RPi I2C1 (SDA=GPIO 2,
          SCL=GPIO 3, VCC=3.3V, GND). Verify I2C detection with
          `i2cdetect -y 1` (should show address 0x4A).
- [ ] 14. Run `ros2 run striper_hardware imu_node`. Verify `/imu/data`
          publishes orientation quaternion. Rotate the IMU by hand and
          confirm values change.
- [ ] 15. (Optional) Configure NTRIP corrections for RTK. Run
          `ros2 run striper_hardware ntrip_client` with your mountpoint
          parameters. Verify `/gps/fix_quality` shows "RTK fixed" or
          "RTK float".

### Phase 4: Paint System

- [ ] 16. Install the 24V-to-12V DC-DC converter. Verify 12V output with
          a multimeter.
- [ ] 17. Wire the MOSFET solenoid driver: RPi GPIO 17 -> MOSFET gate
          (through 220 ohm resistor), MOSFET drain -> solenoid negative,
          solenoid positive -> 12V supply. Add a flyback diode (1N4007)
          across the solenoid terminals (cathode to positive).
- [ ] 18. Run `ros2 run striper_hardware paint_valve`. Publish a test
          `PaintCommand` message. Verify the solenoid clicks open/closed
          (or use an LED in place of the solenoid for bench testing).

### Phase 5: Obstacle Detection

- [ ] 19. Mount the two HC-SR04 ultrasonic sensors at the front of the
          chassis (left and right). Use 5V-to-3.3V level shifters on the
          echo pins (or use voltage dividers: 1k + 2k) since HC-SR04 echo
          is 5V and RPi GPIO is 3.3V tolerant only.
- [ ] 20. Wire trigger and echo pins per the pin table (GPIO 5/6 left,
          GPIO 13/19 right). Verify range readings.

### Phase 6: Status LEDs

- [ ] 21. Wire an RGB common-cathode LED (or three discrete LEDs) to
          GPIO 22 (green), GPIO 23 (red), GPIO 24 (blue) through 220 ohm
          current-limiting resistors.
- [ ] 22. Verify each color by toggling GPIO pins manually or via the
          safety_supervisor node.

### Phase 7: Safety Circuit

- [ ] 23. Install the e-stop button in an accessible location on the
          chassis.
- [ ] 24. Wire N.C. contact pair 1 in series with the 24V motor power
          rail (before the BTS7960 drivers). Install a 30A fuse upstream.
- [ ] 25. Wire N.C. contact pair 2 through a voltage divider to RPi
          GPIO 27. Verify GPIO 27 reads HIGH when e-stop is released and
          LOW when pressed.
- [ ] 26. Test: press e-stop while motors are spinning. Motors must stop
          immediately (electrical cutoff) AND the safety_supervisor node
          must log the e-stop event.
- [ ] 27. Test recovery: release e-stop, verify motors can be commanded
          again after the holdoff period.

### Phase 8: Full System Integration

- [ ] 28. Launch the full system: `ros2 launch striper_bringup striper.launch.py`.
- [ ] 29. Verify all topics are publishing (`ros2 topic list` and
          `ros2 topic hz` on key topics).
- [ ] 30. Perform a slow autonomous drive test in an open area. Monitor
          for correct localization (GPS + IMU fusion), path following, and
          paint valve operation.
- [ ] 31. Test geofence boundaries -- verify the robot stops if it
          approaches the geofence edge.
- [ ] 32. Final e-stop test under autonomous operation.

---

## Appendix: Wire Gauge Reference

| Circuit                   | Recommended Gauge | Max Current |
|---------------------------|-------------------|-------------|
| Battery to fuse           | 10 AWG            | 30 A        |
| Fuse to e-stop to drivers | 12 AWG            | 20 A        |
| Motor driver to motor     | 14 AWG            | 15 A        |
| 12V solenoid              | 18 AWG            | 5 A         |
| 5V power rail             | 18 AWG            | 6 A         |
| Signal wires (GPIO, I2C)  | 22-26 AWG         | <1 A        |
| Serial (UART)             | 22-26 AWG         | <1 A        |
| Encoder signals           | 24-26 AWG         | <100 mA     |
