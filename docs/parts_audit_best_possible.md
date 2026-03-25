# Best Parts Audit: What Is Best-Value vs Best-Possible

Date: 2026-03-21

This document answers a narrower question than the validated BOM: not "what works," and not
"what is the best value," but "what would we choose if we wanted the strongest production-grade
parts we can reasonably justify for this robot."

The current BOM is good. It is not uniformly the best possible. Several selections are optimized
for cost or hackability rather than production robustness.

---

## Executive Verdict

Keep these as-is:

- GNSS: Holybro H-RTK UM982
- Pump: Shurflo 8000-543-236
- Paint nozzle: TeeJet TP8004EVS for 4-inch work
- Autopilot family: Pixhawk / ArduRover
- Hard e-stop architecture: mushroom switch driving a DC contactor

Upgrade these if the goal is best possible hardware rather than cheapest workable hardware:

- Drive system: used hoverboard -> industrial geared drive package or at least new, known-good motor/controller set
- Obstacle sensing: HC-SR04 -> industrial ToF lidar or automotive-grade radar-backed stop layer
- Power conversion: generic XL4015 buck converters -> sealed, name-brand DC-DC modules with surge margin
- Battery: generic 36V e-bike pack -> branded pack with documented cells, BMS, fuse, and enclosure
- Fluid switching: generic Amazon direct-acting valve + hobby relay -> industrial solenoid + MOSFET or sealed relay stage
- Frame and enclosure: open extrusion / plywood -> sealed aluminum chassis with proper cable glands and service loops

---

## Part-by-Part Audit

### 1. GNSS and Heading

Current choice: Holybro H-RTK UM982

Verdict: Keep.

Why:

- The repo already identified the critical issue correctly: UM980 is not good enough for reliable
  heading at paint speed because GSF heading depends on motion.
- UM982 dual-antenna heading removes the standstill and low-speed heading problem.
- This is already the right production decision, not a compromise.

Best-possible recommendation:

- Stay with UM982.
- Do not downgrade to UM980 or single-antenna F9P for production.
- If operating regularly near reflective buildings, add better antennas and a cleaner mount before
  changing the receiver itself.

Practical upgrade path:

- Use a rigid antenna mast.
- Maintain at least 30-40 cm baseline separation.
- Prefer higher-grade antennas and ground-plane discipline before spending more on another GNSS core.

### 2. Flight Controller / Autopilot

Current choice: Pixhawk 6C Mini

Verdict: Good, but not best possible.

Why:

- The 6C Mini is good enough and correctly aligned with ArduRover.
- "Mini" hardware is a packaging and expandability compromise.
- For a production machine, extra I/O margin, cleaner power redundancy, and easier service access matter.

Best-possible recommendation:

- Prefer a full-size Pixhawk 6X / 6C-class controller or Cube Orange+ class hardware for production units.

Decision rule:

- If this robot stays a prototype fleet under 10 units, 6C Mini is acceptable.
- If this becomes a field-serviceable commercial platform, move to a full-size, better-supported controller.

### 3. Drive System

Current choice: used hoverboard motors + salvaged hoverboard controller flashed with FOC firmware

Verdict: Best-value, not best possible.

Why:

- The repo already documents the real weaknesses: MCU compatibility traps, low-speed stall behavior,
  field replacement dependence on used boards, and controller fragility.
- Salvaged hoverboards are excellent for proving the product. They are not the strongest production choice.
- The biggest hidden cost is not purchase price. It is variance between donor boards, repair time,
  and support burden.

Best-possible recommendation:

- Replace the salvaged hoverboard stack with a known, repeatable drivetrain:
  - sealed geared DC or BLDC drive motors with documented torque curves
  - matching production motor controllers from a known vendor
  - encoder support that does not depend on reverse-engineered boards

If you keep hoverboards for now:

- Buy and qualify a fixed donor SKU in batches.
- Keep flashed spare boards in inventory.
- Treat the drivetrain as a temporary platform, not the final commercial answer.

### 4. Paint Pump

Current choice: Shurflo 8000-543-236

Verdict: Keep.

Why:

- The repo correctly rejected cheap diaphragm pumps.
- The Shurflo unit has the right chemistry tolerance, prime behavior, and field reputation.
- For the low-pressure nozzle architecture in this robot, this is already near the right ceiling.

When to upgrade:

- Only move beyond Shurflo if you move the entire fluid system to a more industrial high-duty cycle
  or airless paint architecture.
- That is a product architecture change, not a simple part substitution.

### 5. Nozzle and Tip

Current choice: TeeJet TP8004EVS

Verdict: Keep for current spray architecture.

Why:

- The repo’s flow-rate analysis is sound.
- The EVS pattern is the correct correction over the standard 8004.
- For a 4-inch low-pressure robotic paint system, this is a strong choice.

Best-possible nuance:

- If the mission changes from best-value low-pressure striping to higher uptime production work,
  a Graco-style reversible professional tip system is more service-friendly.
- That is best for maintainability and clog recovery, not necessarily for the current pressure/flow model.

Decision rule:

- Keep TeeJet TP8004EVS for the present architecture.
- Upgrade to a Graco-grade reversible-tip assembly if clog clearing speed and field serviceability become more important than BOM cost.

### 6. Solenoid Valve and Switching

Current choice: generic direct-acting 12V brass valve, hobby relay module, 1N4007 flyback

Verdict: Adequate, not best possible.

Why:

- The repo is correct that the valve must be direct-acting.
- What remains weak is vendor quality control and the hobby-grade relay layer.
- Cheap relays and generic valves are exactly where intermittent failures, sticking, and water ingress appear first.

Best-possible recommendation:

- Use a named industrial solenoid valve with known response time and duty cycle rating.
- Use a sealed automotive or industrial switching stage instead of a generic relay board.
- Keep flyback protection, but move from improvised wiring to a protected harnessed assembly.

### 7. Battery Pack

Current choice: generic 36V 18Ah e-bike battery

Verdict: Capacity is correct; sourcing quality is not yet best possible.

Why:

- The repo correctly moved to roughly 640 Wh class capacity.
- The unresolved risk is pack quality, cell provenance, BMS behavior, connector quality, and weather resistance.

Best-possible recommendation:

- Buy from a vendor that discloses cell brand, BMS specs, continuous current rating, fuse protection,
  and enclosure details.
- Do not optimize this around the cheapest Hailong pack listing.

What matters more than nominal Ah:

- verified cell source
- BMS with proper balancing and protection
- connector robustness
- vibration retention
- charger quality

### 8. DC-DC Conversion and Power Distribution

Current choice: XL4015-class buck converters plus PM06 V2

Verdict: Functional, not best possible.

Why:

- The repo already discovered the pump inrush problem and split the rails correctly.
- The remaining weakness is the converter class itself. Generic buck modules are fine for bench work,
  but they are not the right endpoint for a vibration-heavy outdoor commercial machine.

Best-possible recommendation:

- Use sealed, name-brand DC-DC converters with headroom over startup surge.
- Use a proper fused distribution block.
- Preserve rail separation between logic/autopilot loads and the pump.

Minimum production bar:

- dedicated pump rail
- dedicated avionics/control rail
- sealed converter housings
- documented surge/current ratings

### 9. Obstacle Detection

Current prototype-era choice in the repo: 2x HC-SR04 ultrasonic sensors

Current buy recommendation: replace that prototype obstacle layer before trusting field autonomy.

Verdict: Not best possible. This is the weakest current part selection.

Why:

- HC-SR04 is a hobby sensor. It is cheap, fragile, and poor in wet, noisy, reflective outdoor environments.
- For a robot operating around vehicles and people, this is not the part to defend.
- The repo even describes it more as logging/assist hardware than a trustworthy autonomous stop layer.

Best-possible recommendation:

- Replace HC-SR04 with outdoor-rated ToF lidar or a validated short-range safety sensing layer.
- At minimum, use a higher-quality distance sensor intended for real robot use.
- For any serious commercial deployment, pair perception with a physical bumper or contact strip as a last-resort stop input.

Plain answer:

- If you ask me for the single most urgent hardware upgrade, it is this one.

### 10. RC Link

Current choice: FlySky FS-i6X

Verdict: Good enough, not best possible.

Why:

- FlySky is an acceptable low-cost manual override radio.
- It is not the strongest link budget, ecosystem, or serviceability choice.

Best-possible recommendation:

- Move to a better-supported RC ecosystem if you need more robust field behavior and cleaner failsafe confidence.

### 11. Frame, Harnessing, and Enclosure

Current choice: aluminum extrusion + plywood / open prototype frame

Verdict: Best-value prototype, not best possible.

Why:

- It is ideal for iteration.
- It is not ideal for ingress protection, repeatable assembly, or supportability.

Best-possible recommendation:

- Move to a welded or repeatably fabricated aluminum chassis.
- Use proper cable glands, sealed connectors, abrasion protection, and service loops.
- Remove plywood from any intended production configuration.

---

## Final Ranking

### Already Best or Close Enough

1. UM982 dual-antenna GNSS
2. Shurflo 8000 pump
3. TeeJet TP8004EVS nozzle
4. DC contactor e-stop architecture

### Good but Worth Upgrading for Production

1. Pixhawk 6C Mini -> full-size / higher-end controller
2. FlySky RC -> stronger radio ecosystem
3. Extrusion + plywood frame -> sealed production chassis

### Not Best Possible and Should Be Replaced First

1. HC-SR04 obstacle sensing
2. Generic XL4015 buck converters
3. Generic battery pack sourcing
4. Generic relay module and generic solenoid sourcing
5. Salvaged hoverboard drivetrain for commercial units

---

## Recommended Production-Grade Direction

If the goal is the best practical hardware stack without losing the product thesis, use this direction:

- Autopilot: full-size Pixhawk / Cube-class controller
- GNSS: Holybro H-RTK UM982
- Drivetrain: repeatable production motor/controller set, not salvage-dependent hoverboards
- Pump: Shurflo 8000-543-236
- Nozzle: TeeJet TP8004EVS unless serviceability pushes you to a Graco reversible tip system
- Power: sealed branded DC-DC converters with separate rails
- Battery: branded 36V ~640Wh pack with documented cells and BMS
- Safety sensing: outdoor-rated ToF lidar or better, plus physical bumper stop
- Enclosure: sealed electronics bay with proper harnessing and glands

That stack will cost more than the current recommended BOM, but it is the correct answer if the requirement is truly best possible parts rather than best-value parts.