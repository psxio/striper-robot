# Approved SKU Sheet

Date: 2026-03-21

This is the buyer-safe purchase sheet for the current prototype and pilot-build baseline.

Use this file when you are actively ordering parts.
Use [buying_guide.md](buying_guide.md) for the short rationale.
Use [validated_bom_v3.md](validated_bom_v3.md) for engineering justification.

Where an exact seller SKU is not frozen, that is intentional. For batteries, valves,
converters, and obstacle-stop hardware, the acceptance criteria matter more than any
single marketplace listing.

---

## Approved Exact Parts

These are the parts that are approved by exact model or part number.

| Subsystem | Approved part | Buy spec / part number | Notes |
|-----------|---------------|------------------------|-------|
| Autopilot | Holybro Pixhawk 6C Mini | Holybro Pixhawk 6C Mini Set | Default autopilot for prototype and pilot builds |
| GNSS + heading | Holybro H-RTK UM982 kit | Holybro H-RTK Unicore UM982 dual-antenna kit | Includes the dual-antenna heading hardware; do not substitute UM980 |
| Pump | Shurflo diaphragm pump | Shurflo 8000-543-236 | Keep |
| Nozzle | TeeJet flat fan nozzle | TeeJet TP8004EVS | Keep for 4-inch line work |
| Pixhawk power module | Holybro PM06 V2 | Holybro PM06 V2 | Default regulated Pixhawk power + battery monitoring |
| Manual override radio | FlySky transmitter | FlySky FS-i6X | Acceptable baseline radio |

---

## Approved Spec-Locked Purchases

These parts are approved by purchase specification rather than a single seller listing.

| Subsystem | Approved purchase spec | Minimum acceptance criteria | Reject if |
|-----------|------------------------|-----------------------------|-----------|
| Drivetrain | Used hoverboard donor | Single-board controller using STM32F103 or GD32F103; salvageable motors; acceptable only for prototype/pilot use | AT32 board, split-board architecture, unknown controller chipset |
| Battery | 36V 18Ah e-bike pack | 10S pack, XT60 output, disclosed cell brand, documented BMS rating, continuous-current spec, charger included, enclosure suitable for field mounting | Cheapest anonymous listing with no cell/BMS disclosure |
| Pump rail converter | Sealed 36V to 12V converter | Fixed 12V output, at least 10A continuous, 8-60V input range or equivalent full-pack coverage, IP65/IP67 or potted aluminum housing, chassis-mount tabs, and documented connector style (pigtails or screw terminals) | Open bench buck module, no continuous current rating, no ingress protection, unclear mounting method |
| Auxiliary control rail | Separate sealed low-voltage rail for non-pump loads if needed | Separate from pump rail so pump startup cannot brown out avionics or accessories; same sealed/potted housing standard as the pump converter | Shared with pump rail under field use |
| Paint valve | 12V direct-acting normally closed valve | 3/8 NPT, direct-acting, documented duty rating, named supplier preferred | Pilot-operated valve, anonymous surplus listing |
| E-stop button | 22mm mushroom emergency stop | Normally closed contact block suitable for driving contactor coil | Bare switch intended to interrupt traction current directly |
| Main contactor | DC-rated contactor | 40A DC or better, coil voltage matched to chosen wiring scheme | AC-only relay or under-rated automotive relay |
| Main fuse | Inline blade fuse holder + fuse | 30A waterproof or enclosed fuse holder near battery positive | Unfused battery lead |
| Obstacle stop layer | Outdoor-rated stop sensor or physical bumper | Outdoor-rated sensing hardware or contact strip, validated stop behavior, treated as safety upgrade before trusting unattended field autonomy | HC-SR04 as the planned field safety device |
| Frame | 2020 extrusion prototype frame | Repeatable, rigid build with protected wiring runs and service access | Loose plywood-only structure or unsupported mast geometry |

---

## Required Small Parts

These are the supporting parts that should be treated as required, not optional cleanup.

| Part | Buy spec |
|------|----------|
| Inline paint strainer | 50-mesh |
| Flyback diodes | 1N4007 across pump and solenoid |
| Battery connector | XT60 |
| Main power wire | 12 AWG minimum |
| Hose | 3/8-inch ID reinforced hose |
| Nozzle fittings | Compatible with TeeJet TP8004EVS mounting stack |
| Quick disconnects | Paint-compatible flush-service fittings |

---

## Do Not Substitute

Do not substitute these without re-opening the hardware decision:

1. Do not replace UM982 with UM980 for the current rover.
2. Do not buy a 10Ah battery as the default pack.
3. Do not use HC-SR04 as the intended field obstacle-stop layer.
4. Do not use open XL4015-style buck modules as final installed field power hardware.
5. Do not use pilot-operated paint valves.

---

## Prototype-Only Exception

If you are only doing bench bring-up or very early supervised test runs, you can still wire the
HC-SR04 rangefinder bridge as a prototype aid. That does not make it an approved field-safety
purchase. The buyer-safe path is still an outdoor-rated stop sensor or physical bumper.

---

## Checkout Checklist

Before you place the order, confirm these five things:

1. GNSS order explicitly says UM982 dual-antenna kit.
2. Battery listing discloses cell brand, BMS, current rating, and connector.
3. Pump converter is sealed and rated for at least 10A continuous.
4. Hoverboard donor controller chipset is confirmed before purchase.
5. If you temporarily wire the HC-SR04 bridge for bench or bring-up work, it is explicitly treated
	as prototype-only and not the approved field-safety purchase.