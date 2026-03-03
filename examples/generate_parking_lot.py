#!/usr/bin/env python3
"""Example: Generate a 10-space parking lot mission for Mission Planner.

This script demonstrates the full workflow:
1. Define a parking lot layout using templates
2. Optimize paint path ordering (minimize transit distance)
3. Export to ArduPilot .waypoints file for Mission Planner

Usage:
    python examples/generate_parking_lot.py

Output:
    examples/output/parking_10spaces.waypoints
    examples/output/parking_10spaces.geojson
"""

import os
import sys

# Add project root and pathgen package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "striper_pathgen"))

from striper_pathgen.models import Point2D, GeoPoint, PaintJob, PaintSegment
from striper_pathgen.template_generator import generate_parking_row
from striper_pathgen.path_optimizer import optimize_path_order
from striper_pathgen.coordinate_transform import CoordinateTransformer
from striper_pathgen.mission_planner import export_waypoints, save_waypoints
from striper_pathgen.job_exporter import export_geojson

import json


def main():
    # ── 1. Job site GPS coordinates (datum) ────────────────────────────
    # This is a real parking lot in Austin, TX (example coordinates)
    datum_lat = 30.2672
    datum_lon = -97.7431
    datum_heading = 45.0  # Lot is oriented 45 degrees from north

    print(f"Job site: ({datum_lat}, {datum_lon}), heading {datum_heading} deg")
    print()

    # ── 2. Generate parking spaces ─────────────────────────────────────
    # 10 standard spaces in a row, starting at the local origin
    origin = Point2D(0.0, 0.0)
    row_angle = 0.0  # Perpendicular to the lot heading

    paint_paths = generate_parking_row(
        origin=origin,
        count=10,
        spacing=2.7432,   # 9 feet in meters (standard space width)
        length=5.4864,    # 18 feet in meters (standard space depth)
        angle=row_angle,
        handicap_indices=[0],  # First space is handicap
    )

    print(f"Generated {len(paint_paths)} paint paths for 10 spaces (1 handicap)")
    total_paint_m = sum(p.length for p in paint_paths)
    print(f"Total paint distance: {total_paint_m:.1f} m ({total_paint_m * 3.281:.0f} ft)")
    print()

    # ── 3. Optimize path ordering ──────────────────────────────────────
    optimized_paths = optimize_path_order(paint_paths)

    # ── 4. Create paint segments from optimized paths ──────────────────
    segments = [
        PaintSegment(path=p, index=i)
        for i, p in enumerate(optimized_paths)
    ]
    datum = GeoPoint(lat=datum_lat, lon=datum_lon)
    job = PaintJob(job_id="parking-10-spaces", segments=segments, datum=datum)

    print(f"Optimized {len(job.segments)} segments")
    print()

    # ── 5. Export to Mission Planner .waypoints ─────────────────────────
    os.makedirs("examples/output", exist_ok=True)

    waypoints_content = export_waypoints(
        job=job,
        datum_lat=datum_lat,
        datum_lon=datum_lon,
        datum_heading=datum_heading,
        paint_speed=0.5,      # 0.5 m/s while painting (for clean lines)
        transit_speed=1.0,    # 1.0 m/s while transiting between lines
        waypoint_spacing=0.5, # Waypoint every 0.5m along paint paths
        accept_radius=0.05,   # 5cm waypoint acceptance radius
    )

    waypoints_file = "examples/output/parking_10spaces.waypoints"
    save_waypoints(
        job=job,
        filepath=waypoints_file,
        datum_lat=datum_lat,
        datum_lon=datum_lon,
        datum_heading=datum_heading,
        paint_speed=0.5,
        transit_speed=1.0,
    )

    # Count waypoints
    wp_lines = [l for l in waypoints_content.strip().split("\n") if l]
    nav_wps = sum(1 for l in wp_lines if "\t16\t" in l)
    relay_cmds = sum(1 for l in wp_lines if "\t181\t" in l)
    speed_cmds = sum(1 for l in wp_lines if "\t178\t" in l)

    print(f"Mission file: {waypoints_file}")
    print(f"  Total lines: {len(wp_lines)}")
    print(f"  NAV_WAYPOINT commands: {nav_wps}")
    print(f"  DO_SET_RELAY commands: {relay_cmds} ({relay_cmds // 2} paint segments)")
    print(f"  DO_CHANGE_SPEED commands: {speed_cmds}")
    print()

    # ── 6. Export GeoJSON for visualization ─────────────────────────────
    geojson = export_geojson(job)

    geojson_file = "examples/output/parking_10spaces.geojson"
    with open(geojson_file, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"GeoJSON file: {geojson_file}")
    print(f"  Features: {len(geojson['features'])}")
    print()

    # ── 7. Print first few waypoints as preview ────────────────────────
    print("First 15 waypoint lines:")
    print("-" * 100)
    for line in wp_lines[:15]:
        print(line)
    print("...")
    print()

    # ── 8. Job summary ─────────────────────────────────────────────────
    paint_ft = total_paint_m * 3.281
    gallons = paint_ft / 350  # ~350 linear ft per gallon
    job_time_min = (total_paint_m / 0.5) / 60  # At 0.5 m/s paint speed

    print("=" * 60)
    print("JOB SUMMARY")
    print("=" * 60)
    print(f"  Spaces:           10 (1 handicap)")
    print(f"  Paint distance:   {total_paint_m:.0f} m ({paint_ft:.0f} ft)")
    print(f"  Est. paint used:  {gallons:.1f} gallons (${gallons * 20:.0f} at $20/gal)")
    print(f"  Est. paint time:  {job_time_min:.0f} minutes (+ transit)")
    print(f"  Waypoints:        {nav_wps}")
    print(f"  Mission file:     {waypoints_file}")
    print()
    print("To use: Open Mission Planner -> Flight Plan -> Load WP File")
    print(f"        Select {waypoints_file}")


if __name__ == "__main__":
    main()
