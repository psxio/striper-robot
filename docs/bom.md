# Striper Robot -- Bill of Materials (BOM)

Detailed bill of materials for the autonomous parking-lot line-striping
robot, grouped by subsystem. Prices are approximate USD as of early 2026
and may vary by vendor.

---

## 1. Compute

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 1 | Raspberry Pi 5 (8 GB) | Quad Cortex-A76, 8 GB LPDDR4X | 1 | $80 | $80 | PiShop.us / SparkFun |
| 2 | Raspberry Pi 5 active cooler | Official fan + heatsink | 1 | $5 | $5 | PiShop.us |
| 3 | MicroSD card (64 GB) | SanDisk Extreme A2 U3 | 1 | $12 | $12 | Amazon |
| 4 | ESP32-DevKitC-32E | ESP32-WROOM-32E, 4 MB flash | 1 | $10 | $10 | Amazon / DigiKey |
| 5 | USB-A to USB-C cable (short) | 30 cm, for RPi power or peripherals | 1 | $6 | $6 | Amazon |

**Compute subtotal: ~$113**

---

## 2. Drive System

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 6 | Pololu 37D metal gearmotor 131:1 | 24V, 80 RPM, 18 kg-cm stall torque, integrated encoder (64 CPR) | 2 | $40 | $80 | Pololu (#4758) |
| 7 | Pololu 37D motor bracket (L-shaped) | Mounting bracket for 37D motors | 2 | $8 | $16 | Pololu (#1084) |
| 8 | BTS7960 43A motor driver module | Dual H-bridge, 5.5-27V, 43A peak | 2 | $12 | $24 | Amazon |
| 9 | 150mm diameter rubber wheel | 6" pneumatic or solid rubber, 8mm bore hub adapter | 2 | $15 | $30 | Amazon / Pololu |
| 10 | Caster wheel (front) | 75mm swivel caster, ball bearing | 1 | $10 | $10 | Amazon |
| 11 | 8mm shaft coupler | Motor shaft to wheel hub | 2 | $4 | $8 | Amazon |

**Drive subtotal: ~$168**

---

## 3. Positioning (GPS + IMU)

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 12 | SparkFun GPS-RTK-SMA (ZED-F9P) | u-blox ZED-F9P, USB-C, SMA connectors | 1 | $275 | $275 | SparkFun (GPS-16481) |
| 13 | GNSS multi-band antenna | u-blox ANN-MB-00 or SparkFun TOP106, L1/L2 | 1 | $65 | $65 | SparkFun / DigiKey |
| 14 | SMA male to SMA male cable | 25 cm, RG316, for antenna connection | 1 | $7 | $7 | Amazon |
| 15 | Antenna ground plane | 100mm aluminum disc, improves multipath rejection | 1 | $10 | $10 | Amazon / custom |
| 16 | Adafruit BNO085 breakout | 9-DOF IMU, I2C/SPI/UART, STEMMA QT | 1 | $30 | $30 | Adafruit (#4754) |
| 17 | STEMMA QT / Qwiic cable | 100mm, JST SH 4-pin, for I2C | 1 | $1 | $1 | Adafruit / SparkFun |

**Positioning subtotal: ~$388**

---

## 4. Paint System

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 18 | 12V DC solenoid valve (normally closed) | 1/2" NPT, brass, 0-80 PSI | 1 | $25 | $25 | Amazon |
| 19 | IRLZ44N N-channel MOSFET | Logic-level gate, TO-220, 47A, 55V | 1 | $2 | $2 | DigiKey / Amazon |
| 20 | 1N4007 rectifier diode | Flyback protection for solenoid | 1 | $0.10 | $0.10 | DigiKey |
| 21 | 220 ohm resistor (1/4W) | Gate resistor for MOSFET | 1 | $0.10 | $0.10 | DigiKey |
| 22 | 10k ohm resistor (1/4W) | Gate pull-down for MOSFET | 1 | $0.10 | $0.10 | DigiKey |
| 23 | Paint reservoir tank | 1-gallon pressurized canister or gravity-fed tank | 1 | $30 | $30 | Amazon / hardware store |
| 24 | 1/2" vinyl tubing | For paint supply line, 3 ft | 1 | $5 | $5 | Hardware store |
| 25 | Hose barb fittings (1/2") | Barb to NPT adapters | 2 | $3 | $6 | Hardware store |
| 26 | Spray nozzle tip | Flat fan pattern, 2-4 inch stripe width | 1 | $8 | $8 | Amazon |

**Paint subtotal: ~$76**

---

## 5. Obstacle Detection

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 27 | HC-SR04 ultrasonic sensor | 2-400 cm range, 5V, 15 deg beam | 2 | $3 | $6 | Amazon |
| 28 | Bi-directional logic level converter | 4-channel, 3.3V <-> 5V (for echo pins) | 1 | $3 | $3 | SparkFun / Amazon |
| 29 | Ultrasonic sensor mounting bracket | 3D-printed or L-bracket, adjustable angle | 2 | $2 | $4 | Amazon / custom |

**Obstacle detection subtotal: ~$13**

---

## 6. Safety

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 30 | Emergency stop button (mushroom head) | 22mm panel mount, 2x N.C. contacts, twist-release | 1 | $15 | $15 | Amazon / DigiKey (e.g., Schneider XB5AS8442) |
| 31 | 30A automotive relay or contactor | 24V coil, 30A N.C. contacts (or use e-stop contacts directly if rated) | 1 | $12 | $12 | Amazon / DigiKey |
| 32 | 30A blade fuse + inline holder | ATC/ATO style, for main battery line | 1 | $5 | $5 | Amazon / auto parts |
| 33 | 3.3V zener diode (1N4728A) | Clamp protection for GPIO 27 | 1 | $0.20 | $0.20 | DigiKey |
| 34 | 10k ohm resistor (voltage divider) | For e-stop signal path | 1 | $0.10 | $0.10 | DigiKey |
| 35 | 5.6k ohm resistor (voltage divider) | For e-stop signal path | 1 | $0.10 | $0.10 | DigiKey |

**Safety subtotal: ~$32**

---

## 7. Status Indicators

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 36 | RGB common-cathode LED (5mm) | or 3x individual LEDs (red, green, blue) | 1 | $1 | $1 | Amazon / DigiKey |
| 37 | 220 ohm resistor (1/4W) | Current limiting, one per LED color | 3 | $0.10 | $0.30 | DigiKey |
| 38 | LED panel mount holder (5mm) | Chrome bezel | 1 | $1 | $1 | Amazon |

**Status indicator subtotal: ~$2**

---

## 8. Power

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 39 | LiFePO4 battery 24V 30Ah | 8S, built-in BMS, 720Wh | 1 | $250 | $250 | Amazon (e.g., Ampere Time / LiTime 25.6V 30Ah) |
| 40 | Battery charger (29.2V LiFePO4) | 5A charge rate, CC/CV | 1 | $35 | $35 | Amazon (matched to battery) |
| 41 | 24V to 5V DC-DC converter | DFRobot DFR0571 or Pololu D24V50F5 (5A, 5V out) | 1 | $15 | $15 | Pololu / Amazon |
| 42 | 24V to 12V DC-DC converter | 3A step-down, isolated preferred | 1 | $12 | $12 | Amazon / Pololu (D24V22F12) |
| 43 | Anderson Powerpole connectors (30A) | Battery quick-disconnect | 1 pair | $5 | $5 | Amazon / Powerwerx |
| 44 | Power distribution bus bar / terminal block | 4-position, 30A rated | 1 | $8 | $8 | Amazon |
| 45 | Toggle switch (main power) | 30A, panel mount, with LED indicator | 1 | $8 | $8 | Amazon |

**Power subtotal: ~$333**

---

## 9. Wiring, Connectors, and Consumables

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 46 | 10 AWG silicone wire (red + black) | Battery to fuse/e-stop, 3 ft each color | 1 set | $10 | $10 | Amazon |
| 47 | 12 AWG silicone wire (red + black) | Motor power rail, 6 ft each color | 1 set | $8 | $8 | Amazon |
| 48 | 14 AWG silicone wire (red + black) | Motor driver to motor, 3 ft each color | 1 set | $7 | $7 | Amazon |
| 49 | 18 AWG hookup wire (assorted colors) | Solenoid, 5V rail, 10 ft total | 1 set | $6 | $6 | Amazon |
| 50 | 22 AWG hookup wire (assorted colors) | Signal wires, GPIO, 25 ft total | 1 spool | $8 | $8 | Amazon |
| 51 | Dupont jumper wire kit | M-M, M-F, F-F, 10cm and 20cm | 1 kit | $7 | $7 | Amazon |
| 52 | JST-XH connector kit | 2/3/4/6 pin, for clean encoder & sensor connections | 1 kit | $12 | $12 | Amazon |
| 53 | Ferrule crimps + crimping tool | For stranded wire terminations | 1 kit | $25 | $25 | Amazon |
| 54 | Heat shrink tubing assortment | 2:1 ratio, various diameters | 1 kit | $8 | $8 | Amazon |
| 55 | Zip ties (assorted) | Cable management | 1 bag | $5 | $5 | Amazon |
| 56 | Adhesive cable clips | Stick-on, for wire routing on chassis | 1 pack | $5 | $5 | Amazon |
| 57 | Breadboard (half-size) | For prototyping signal conditioning circuits | 1 | $5 | $5 | Amazon / SparkFun |
| 58 | Perfboard (70x90mm) | For permanent signal conditioning (voltage dividers, MOSFET driver) | 1 | $3 | $3 | Amazon |
| 59 | M3 standoffs, screws, nuts kit | For mounting PCBs to chassis | 1 kit | $8 | $8 | Amazon |
| 60 | XT60 connectors (male + female) | Inline power connectors for battery and DC-DC modules | 2 pairs | $4 | $8 | Amazon |

**Wiring/consumables subtotal: ~$125**

---

## 10. Chassis / Frame

| # | Component | Specs | Qty | Unit Price | Subtotal | Source |
|---|-----------|-------|-----|------------|----------|--------|
| 61 | Aluminum extrusion (20x20mm, V-slot) | 500mm lengths for frame | 6 | $5 | $30 | Amazon / OpenBuilds |
| 62 | V-slot corner brackets | 90-degree, 20-series | 12 | $1.50 | $18 | Amazon / OpenBuilds |
| 63 | T-nuts (M5, 20-series) | Drop-in, for mounting components | 1 pack (50) | $8 | $8 | Amazon |
| 64 | M5x8mm button head screws | For extrusion assembly | 1 pack (50) | $6 | $6 | Amazon |
| 65 | Aluminum plate (3mm, 300x200mm) | Motor mount / electronics tray | 1 | $15 | $15 | Amazon / OnlineMetals |
| 66 | 3D-printed mounts | Sensor, GPS antenna, nozzle holders (PLA/PETG) | misc | $10 | $10 | Self-printed |
| 67 | Weatherproof electronics enclosure | IP65, ~250x200x120mm, for RPi + converters | 1 | $20 | $20 | Amazon |

**Chassis subtotal: ~$107**

---

## Cost Summary

| Subsystem               | Subtotal |
|--------------------------|----------|
| Compute                  | $113     |
| Drive system             | $168     |
| Positioning (GPS + IMU)  | $388     |
| Paint system             | $76      |
| Obstacle detection       | $13      |
| Safety                   | $32      |
| Status indicators        | $2       |
| Power                    | $333     |
| Wiring & consumables     | $125     |
| Chassis / frame          | $107     |
| **TOTAL**                | **~$1,357** |

> **Note:** Prices exclude shipping and tax. The largest single cost is the
> ZED-F9P RTK GPS module ($275). If centimeter-level accuracy is not needed
> initially, a standard u-blox NEO-M9N (~$50) can be substituted, reducing
> the total to approximately $1,130. The LiFePO4 battery ($250) is the
> second largest cost; a smaller 20Ah pack (~$170) would reduce cost but
> limit runtime to roughly 4 hours of active use.

---

## Vendor Quick Links

| Vendor     | URL                              | Notes                           |
|------------|----------------------------------|---------------------------------|
| Pololu     | https://www.pololu.com           | Motors, motor drivers, DC-DC    |
| SparkFun   | https://www.sparkfun.com         | GPS-RTK, IMU, breakouts         |
| Adafruit   | https://www.adafruit.com         | BNO085, connectors, breakouts   |
| DigiKey    | https://www.digikey.com          | Discrete components, connectors |
| Amazon     | https://www.amazon.com           | General, batteries, wire, misc  |
| OpenBuilds | https://openbuildspartstore.com  | Aluminum extrusion, V-slot      |
| Powerwerx  | https://powerwerx.com            | Anderson Powerpole connectors   |
