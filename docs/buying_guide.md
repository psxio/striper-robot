# Robot Buying Guide

Date: 2026-03-21

This is the short version of the BOM for when you actually want to buy parts.

If you want the exact buyer-safe purchase sheet, use [approved_sku_sheet.md](approved_sku_sheet.md).
If you want the engineering rationale, use [validated_bom_v3.md](validated_bom_v3.md).
If you want the production-grade upgrade analysis, use [parts_audit_best_possible.md](parts_audit_best_possible.md).

---

## Buy From This File

Use this list as the default purchase plan.

| Subsystem | Buy now | Notes |
|-----------|---------|-------|
| Autopilot | Holybro Pixhawk 6C Mini | Correct default for prototype and pilot builds |
| GNSS + heading | Holybro H-RTK UM982 dual-antenna kit | Do not substitute UM980 |
| Drivetrain | Used hoverboard with STM32F103 or GD32F103 single-board controller | Prototype-only compromise; verify chip before buying |
| Pump | Shurflo 8000-543-236 | Keep |
| Nozzle | TeeJet TP8004EVS | Keep |
| Battery | 36V 18Ah pack from a vendor that discloses cell brand and BMS specs | Do not buy the cheapest unknown pack |
| Power | Holybro PM06 V2 plus separate sealed DC-DC rails for pump and control loads | Do not share one hobby buck across all loads |
| Paint valve | 12V direct-acting valve, 3/8 NPT, from a named supplier if possible | Avoid pilot-operated valves |
| E-stop | 22mm mushroom switch driving a 40A DC contactor | Keep |
| Manual override | FlySky FS-i6X | Acceptable default |
| Obstacle stop layer | Outdoor-rated distance sensor or physical bumper strip | Do not rely on HC-SR04 for production |
| Frame | 2020 extrusion frame for prototype builds | Fine for now; not the final production chassis |

Power converter minimums:

- Pump rail: sealed 36V→12V converter, at least 10A continuous, outdoor/automotive-grade preferred
- Control rail: separate from the pump rail so startup surge cannot brown out Pixhawk/GNSS
- Pixhawk power: Holybro PM06 V2 remains the default regulated power module

### Prototype-only compromises

- Used hoverboard drivetrain: acceptable for prototype and pilot builds, not the long-term commercial answer
- HC-SR04: acceptable only for bench testing and early experiments, not a production safety layer
- Open hobby buck converters: acceptable only on the bench, not as the final outdoor power solution

---

## Do Not Buy Blindly

These are the parts most likely to create avoidable field failures if purchased by price alone.

- Hoverboards without confirmed STM32F103 or GD32F103 single-board controllers
- Cheapest generic 36V battery packs with no disclosed cells or BMS rating
- Open XL4015 buck modules as the final outdoor power solution
- HC-SR04 as the planned production obstacle-stop device
- Anonymous pilot-operated valves
- Generic diaphragm pumps instead of the Shurflo 8000

---

## Default Build Profile

This is the build profile I would follow if you want the best current answer without redesigning the whole robot:

1. Keep UM982.
2. Keep Shurflo 8000.
3. Keep TeeJet TP8004EVS.
4. Keep the contactor-based hard e-stop.
5. Use Pixhawk 6C Mini unless you are already committing to a production fleet.
6. Use hoverboard drive only for prototype and pilot builds.
7. Buy a better battery and better DC-DC hardware than the cheapest marketplace listings.
8. Replace HC-SR04 with a real outdoor stop sensor or physical bumper before you trust unattended field operation.

---

## When To Spend More

Spend more immediately on these parts if you want fewer surprises in the field:

1. Battery pack quality
2. DC-DC converters and fused power distribution
3. Obstacle-stop hardware
4. Valve switching hardware

Spend more later only if you are moving beyond prototype and pilot builds:

1. Full-size autopilot hardware
2. Production drivetrain instead of salvage hoverboards
3. Sealed chassis and harnessing