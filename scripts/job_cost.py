#!/usr/bin/env python3
"""Job costing calculator for striper robot missions.

Reads a QGC WPL 110 .waypoints file and produces a detailed cost estimate
including mission time, paint usage, robot operating cost, manual labor
comparison, and ROI analysis.

Usage:
    python scripts/job_cost.py examples/output/sample_lot.waypoints
    python scripts/job_cost.py mission.waypoints --json
    python scripts/job_cost.py mission.waypoints --csv --labor-rate 75 --paint-cost 32
"""

import argparse
import csv
import io
import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS = 6_378_137.0
PAINT_SPEED = 0.50       # m/s (WP_SPEED)
TRANSIT_SPEED = 1.00     # m/s (CRUISE_SPEED)
TURN_OVERHEAD_S = 2.0    # seconds per waypoint turn
FLOW_RATE_GPM = 1.2      # pump flow rate (gallons per minute)
NOZZLE_WIDTH_M = 0.10    # 4-inch flat fan nozzle
WASTE_FACTOR = 1.15      # 15% paint waste

# Manual striping benchmarks
MANUAL_SPEED_FT_HR = 200    # linear feet per hour (2-person crew)
MANUAL_WASTE_FACTOR = 1.35  # 35% waste (drips, overspray, stencils)
DEFAULT_LABOR_RATE = 65.0   # $/hr per person
CREW_SIZE = 2
DEFAULT_PAINT_COST = 30.0   # $/gallon (traffic latex)

# Robot costs
ROBOT_BOM_COST = 631.0      # Tier 2 BOM
ELECTRICITY_KWH = 0.12      # $/kWh
BATTERY_WH = 360             # 36V * 10Ah
WEAR_PER_JOB = 2.0          # nozzle, seals, etc.

CMD_WAYPOINT = 16
CMD_CHANGE_SPEED = 178
CMD_SET_RELAY = 181


# ---------------------------------------------------------------------------
# Waypoint parser (mirrors simulate_mission.py)
# ---------------------------------------------------------------------------
def parse_waypoints(filepath):
    commands = []
    with open(filepath, "r") as f:
        header = f.readline().strip()
        if not header.startswith("QGC WPL"):
            raise ValueError(f"Not a QGC WPL file: {header}")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 12:
                continue
            commands.append({
                "seq": int(parts[0]),
                "cmd_id": int(parts[3]),
                "p1": float(parts[4]),
                "p2": float(parts[5]),
                "lat": float(parts[8]),
                "lon": float(parts[9]),
            })
    return commands


def haversine(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def analyze_mission(commands):
    """Extract mission metrics from waypoint commands."""
    paint_on = False
    paint_dist = 0.0
    transit_dist = 0.0
    paint_segments = 0
    wp_count = 0
    last_lat = None
    last_lon = None

    for cmd in commands:
        if cmd["cmd_id"] == CMD_SET_RELAY:
            relay_idx = int(cmd["p1"])
            relay_state = int(cmd["p2"])
            if relay_idx == 0:
                if relay_state == 1 and not paint_on:
                    paint_on = True
                    paint_segments += 1
                elif relay_state == 0 and paint_on:
                    paint_on = False

        elif cmd["cmd_id"] == CMD_WAYPOINT:
            lat, lon = cmd["lat"], cmd["lon"]
            if lat == 0 and lon == 0:
                continue
            wp_count += 1
            if last_lat is not None:
                d = haversine(last_lat, last_lon, lat, lon)
                if paint_on:
                    paint_dist += d
                else:
                    transit_dist += d
            last_lat, last_lon = lat, lon

    return {
        "paint_dist_m": paint_dist,
        "transit_dist_m": transit_dist,
        "total_dist_m": paint_dist + transit_dist,
        "paint_segments": paint_segments,
        "waypoint_count": wp_count,
    }


def compute_costs(metrics, labor_rate=DEFAULT_LABOR_RATE, paint_cost_gal=DEFAULT_PAINT_COST):
    """Compute all cost estimates from mission metrics."""
    m = metrics
    paint_m = m["paint_dist_m"]
    transit_m = m["transit_dist_m"]
    paint_ft = paint_m * 3.28084
    transit_ft = transit_m * 3.28084

    # Robot mission time
    paint_time_s = paint_m / PAINT_SPEED
    transit_time_s = transit_m / TRANSIT_SPEED
    turn_time_s = m["waypoint_count"] * TURN_OVERHEAD_S
    total_time_s = paint_time_s + transit_time_s + turn_time_s
    total_time_min = total_time_s / 60

    # Paint usage (robot) — coverage-based estimate
    # Traffic paint at 4" (100mm) width: ~350 linear ft per gallon
    # This matches real-world paint usage for line striping machines
    paint_time_min = paint_time_s / 60
    coverage_gal = paint_ft / 350
    gallons = coverage_gal * WASTE_FACTOR
    paint_cost_robot = gallons * paint_cost_gal

    # Robot operating cost
    runtime_hrs = total_time_min / 60
    electricity = (BATTERY_WH / 1000) * ELECTRICITY_KWH * (runtime_hrs / 0.5)  # ~0.5hr per charge
    robot_op_cost = electricity + WEAR_PER_JOB + paint_cost_robot

    # Manual comparison
    manual_time_hr = paint_ft / MANUAL_SPEED_FT_HR
    manual_labor = manual_time_hr * CREW_SIZE * labor_rate
    manual_gallons = gallons * MANUAL_WASTE_FACTOR / WASTE_FACTOR  # more waste
    manual_paint = manual_gallons * paint_cost_gal
    manual_total = manual_labor + manual_paint

    # Savings
    time_saved_hr = manual_time_hr - (total_time_min / 60)
    cost_saved = manual_total - robot_op_cost
    jobs_to_breakeven = ROBOT_BOM_COST / max(cost_saved, 1)

    return {
        "mission": {
            "paint_dist_m": round(paint_m, 1),
            "paint_dist_ft": round(paint_ft, 0),
            "transit_dist_m": round(transit_m, 1),
            "transit_dist_ft": round(transit_ft, 0),
            "total_dist_m": round(paint_m + transit_m, 1),
            "paint_segments": m["paint_segments"],
            "waypoints": m["waypoint_count"],
            "paint_time_min": round(paint_time_min, 1),
            "transit_time_min": round(transit_time_s / 60, 1),
            "total_time_min": round(total_time_min, 1),
        },
        "paint": {
            "gallons": round(gallons, 2),
            "cost_low": round(gallons * 25, 2),
            "cost_mid": round(gallons * paint_cost_gal, 2),
            "cost_high": round(gallons * 35, 2),
            "waste_pct": 15,
        },
        "robot_cost": {
            "electricity": round(electricity, 2),
            "wear": WEAR_PER_JOB,
            "paint": round(paint_cost_robot, 2),
            "total": round(robot_op_cost, 2),
        },
        "manual_cost": {
            "time_hr": round(manual_time_hr, 1),
            "crew_size": CREW_SIZE,
            "labor_rate": labor_rate,
            "labor_cost": round(manual_labor, 2),
            "paint_gallons": round(manual_gallons, 2),
            "paint_cost": round(manual_paint, 2),
            "total": round(manual_total, 2),
        },
        "savings": {
            "time_saved_hr": round(time_saved_hr, 1),
            "cost_saved_per_job": round(cost_saved, 2),
            "robot_cost": ROBOT_BOM_COST,
            "jobs_to_breakeven": round(jobs_to_breakeven, 1),
            "annual_savings_20_jobs": round(cost_saved * 20, 2),
        },
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------
M_TO_FT = 3.28084

def fmt_box(title, rows, width=60):
    """Format a section with ASCII box drawing."""
    lines = []
    lines.append("+" + "-" * (width - 2) + "+")
    lines.append("|  " + title.upper().ljust(width - 4) + "|")
    lines.append("+" + "-" * (width - 2) + "+")
    for label, value in rows:
        left = f"  {label}"
        right = f"{value}  "
        pad = width - len(left) - len(right) - 2
        if pad < 1:
            pad = 1
        lines.append("|" + left + "." * pad + right + "|")
    lines.append("+" + "-" * (width - 2) + "+")
    return "\n".join(lines)


def print_pretty(costs, filepath):
    """Print a pretty terminal report."""
    m = costs["mission"]
    p = costs["paint"]
    r = costs["robot_cost"]
    mc = costs["manual_cost"]
    s = costs["savings"]

    print()
    print("=" * 60)
    print("  STRIPER ROBOT - JOB COST ESTIMATE")
    print(f"  Mission: {os.path.basename(filepath)}")
    print("=" * 60)

    print(fmt_box("Mission Analysis", [
        ("Paint distance", f"{m['paint_dist_m']}m ({m['paint_dist_ft']:.0f}ft)"),
        ("Transit distance", f"{m['transit_dist_m']}m ({m['transit_dist_ft']:.0f}ft)"),
        ("Paint segments", str(m['paint_segments'])),
        ("Waypoints", str(m['waypoints'])),
        ("Paint time", f"{m['paint_time_min']}min @ {PAINT_SPEED}m/s"),
        ("Transit time", f"{m['transit_time_min']}min @ {TRANSIT_SPEED}m/s"),
        ("Total mission time", f"{m['total_time_min']}min"),
    ]))

    print(fmt_box("Paint Estimate (robot)", [
        ("Gallons needed", f"{p['gallons']} gal (incl {p['waste_pct']}% waste)"),
        ("Cost @ $25/gal", f"${p['cost_low']:.2f}"),
        ("Cost @ $30/gal", f"${p['cost_mid']:.2f}"),
        ("Cost @ $35/gal", f"${p['cost_high']:.2f}"),
    ]))

    print(fmt_box("Robot Operating Cost", [
        ("Electricity", f"${r['electricity']:.2f}"),
        ("Wear/maintenance", f"${r['wear']:.2f}"),
        ("Paint", f"${r['paint']:.2f}"),
        ("TOTAL per job", f"${r['total']:.2f}"),
    ]))

    print(fmt_box("Manual Striping Cost", [
        ("Time (manual)", f"{mc['time_hr']}hr ({mc['crew_size']}-person crew)"),
        ("Labor @ ${:.0f}/hr/person".format(mc['labor_rate']), f"${mc['labor_cost']:.2f}"),
        ("Paint ({:.1f} gal, more waste)".format(mc['paint_gallons']), f"${mc['paint_cost']:.2f}"),
        ("TOTAL manual", f"${mc['total']:.2f}"),
    ]))

    print(fmt_box("Savings & ROI", [
        ("Time saved per job", f"{s['time_saved_hr']}hr"),
        ("Cost saved per job", f"${s['cost_saved_per_job']:.2f}"),
        ("Robot hardware cost", f"${s['robot_cost']:.0f}"),
        ("Jobs to break even", f"{s['jobs_to_breakeven']:.1f} jobs"),
        ("Annual savings (20 jobs)", f"${s['annual_savings_20_jobs']:.2f}"),
    ]))

    print()


def print_json(costs):
    print(json.dumps(costs, indent=2))


def print_csv(costs):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Metric", "Value", "Unit"])

    for section_name, section_data in costs.items():
        for key, val in section_data.items():
            unit = ""
            if "dist" in key and "_m" in key:
                unit = "m"
            elif "dist" in key and "_ft" in key:
                unit = "ft"
            elif "time" in key and "hr" in key:
                unit = "hr"
            elif "time" in key and "min" in key:
                unit = "min"
            elif "gal" in key:
                unit = "gal"
            elif "cost" in key or "labor" in key or "electric" in key or "wear" in key or "paint" == key or "total" == key:
                unit = "$"
                if isinstance(val, (int, float)):
                    val = f"{val:.2f}"
            elif "saved" in key and "cost" in key:
                unit = "$"
            elif "pct" in key:
                unit = "%"
            elif "jobs" in key:
                unit = "jobs"
            writer.writerow([section_name, key, val, unit])

    print(output.getvalue())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Striper Robot Job Cost Estimator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python scripts/job_cost.py examples/output/sample_lot.waypoints --labor-rate 75",
    )
    parser.add_argument("waypoints", help="Path to .waypoints file (QGC WPL 110)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--labor-rate", type=float, default=DEFAULT_LABOR_RATE,
                        help=f"Manual labor rate $/hr/person (default: {DEFAULT_LABOR_RATE})")
    parser.add_argument("--paint-cost", type=float, default=DEFAULT_PAINT_COST,
                        help=f"Paint cost $/gallon (default: {DEFAULT_PAINT_COST})")
    args = parser.parse_args()

    if not os.path.isfile(args.waypoints):
        print(f"Error: file not found: {args.waypoints}", file=sys.stderr)
        sys.exit(1)

    commands = parse_waypoints(args.waypoints)
    metrics = analyze_mission(commands)
    costs = compute_costs(metrics, args.labor_rate, args.paint_cost)

    if args.json:
        print_json(costs)
    elif args.csv:
        print_csv(costs)
    else:
        print_pretty(costs, args.waypoints)


if __name__ == "__main__":
    main()
