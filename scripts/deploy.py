#!/usr/bin/env python3
"""Deployment validator and SD card preparation for striper robot.

Validates all config files, prepares the ArduRover SD card directory
structure, and generates a pre-flight checklist.

Usage:
    python scripts/deploy.py
    python scripts/deploy.py --sd-output ./sd_card
    python scripts/deploy.py --waypoints examples/output/sample_lot.waypoints
"""

import argparse
import os
import re
import shutil
import sys

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAM_FILE = os.path.join(PROJECT_ROOT, "ardurover", "params", "striper.param")
LUA_DIR = os.path.join(PROJECT_ROOT, "ardurover", "lua")

REQUIRED_LUA_SCRIPTS = [
    "motor_bridge.lua",
    "paint_control.lua",
    "paint_speed_sync.lua",
    "fence_check.lua",
    "obstacle_avoid.lua",
]

# Key params that must exist (param_name, expected_value or None for any)
REQUIRED_PARAMS = [
    ("FRAME_TYPE", "2"),          # skid steer
    ("GPS_TYPE", "24"),           # UnicoreNMEA (single UM980)
    ("SERVO1_FUNCTION", "73"),    # throttle left
    ("SERVO3_FUNCTION", "74"),    # throttle right
    ("SPRAY_ENABLE", "1"),        # AC_Sprayer
    ("SCR_ENABLE", "1"),          # Lua scripting
    ("RELAY1_PIN", None),         # paint solenoid (any value)
    ("RELAY2_PIN", None),         # pump (any value)
    ("FENCE_ENABLE", "1"),        # geofence on
    ("WP_SPEED", "0.50"),         # paint speed
    ("CRUISE_SPEED", "1.00"),     # transit speed
    ("AVOID_ENABLE", None),       # obstacle avoidance (any value)
]


def load_params(filepath):
    """Load param file into dict."""
    params = {}
    if not os.path.isfile(filepath):
        return params
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," in line:
                parts = line.split(",", 1)
                params[parts[0].strip()] = parts[1].strip()
    return params


def validate_params(params):
    """Check required params exist with correct values."""
    issues = []
    for name, expected in REQUIRED_PARAMS:
        if name not in params:
            issues.append(("MISSING", f"Parameter {name} not found in striper.param"))
        elif expected is not None and params[name] != expected:
            issues.append(("WRONG", f"{name} = {params[name]} (expected {expected})"))
    return issues


def validate_lua_scripts():
    """Check all Lua scripts exist and have basic validity."""
    issues = []
    for script in REQUIRED_LUA_SCRIPTS:
        path = os.path.join(LUA_DIR, script)
        if not os.path.isfile(path):
            issues.append(("MISSING", f"Lua script not found: {script}"))
            continue

        with open(path, "r") as f:
            content = f.read()

        # Basic checks
        if "function update()" not in content and "function update ()" not in content:
            issues.append(("WARN", f"{script}: no update() function found"))

        if "return update" not in content:
            issues.append(("WARN", f"{script}: no 'return update' scheduling found"))

        # Check for common Lua syntax issues
        opens = content.count("function ")
        ends = content.count("\nend")
        if opens > 0 and ends < opens:
            issues.append(("WARN", f"{script}: possible missing 'end' statement "
                          f"({opens} functions, {ends} ends)"))

    return issues


def validate_relay_consistency(params):
    """Check relay pin assignments are consistent between params and Lua."""
    issues = []
    relay1_pin = params.get("RELAY1_PIN")
    relay2_pin = params.get("RELAY2_PIN")

    if relay1_pin and relay2_pin and relay1_pin == relay2_pin:
        issues.append(("ERROR", f"RELAY1_PIN and RELAY2_PIN both set to {relay1_pin}!"))

    # Check paint_control.lua references correct relay indices
    paint_lua = os.path.join(LUA_DIR, "paint_control.lua")
    if os.path.isfile(paint_lua):
        with open(paint_lua, "r") as f:
            content = f.read()
        if "PAINT_RELAY" in content and "PUMP_RELAY" in content:
            # Check they use relay 0 and 1
            if "= 0" not in content.split("PAINT_RELAY")[1][:20]:
                issues.append(("WARN", "paint_control.lua PAINT_RELAY may not be 0"))
            if "= 1" not in content.split("PUMP_RELAY")[1][:20]:
                issues.append(("WARN", "paint_control.lua PUMP_RELAY may not be 1"))

    return issues


def validate_waypoints(filepath):
    """Basic sanity checks on a waypoints file."""
    issues = []
    if not os.path.isfile(filepath):
        issues.append(("ERROR", f"Waypoints file not found: {filepath}"))
        return issues

    with open(filepath, "r") as f:
        header = f.readline().strip()
        if not header.startswith("QGC WPL"):
            issues.append(("ERROR", f"Not a QGC WPL file: {header}"))
            return issues

        lines = f.readlines()

    relay_on = 0
    relay_off = 0
    wp_count = 0
    lats = []
    lons = []

    for line in lines:
        parts = line.strip().split("\t")
        if len(parts) < 12:
            continue
        cmd_id = int(parts[3])

        if cmd_id == 16:  # NAV_WAYPOINT
            lat, lon = float(parts[8]), float(parts[9])
            if lat != 0 and lon != 0:
                wp_count += 1
                lats.append(lat)
                lons.append(lon)

        elif cmd_id == 181:  # DO_SET_RELAY
            relay_idx = int(float(parts[4]))
            relay_state = int(float(parts[5]))
            if relay_idx == 0:
                if relay_state == 1:
                    relay_on += 1
                else:
                    relay_off += 1

    # Checks
    if wp_count == 0:
        issues.append(("ERROR", "No NAV_WAYPOINT commands found"))

    if relay_on != relay_off:
        issues.append(("ERROR", f"Unbalanced relays: {relay_on} ON vs {relay_off} OFF"))

    if relay_on == 0:
        issues.append(("WARN", "No paint relay commands found (no painting?)"))

    if lats:
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        if lat_range > 0.01 or lon_range > 0.01:
            issues.append(("WARN", f"Large GPS spread: {lat_range:.6f} lat, "
                          f"{lon_range:.6f} lon — verify lot boundary"))

    print(f"  Waypoints: {wp_count}")
    print(f"  Paint segments: {relay_on}")
    print(f"  GPS bounds: ({min(lats):.5f},{min(lons):.5f}) to ({max(lats):.5f},{max(lons):.5f})")

    return issues


def prepare_sd_card(output_dir):
    """Create SD card directory structure."""
    scripts_dir = os.path.join(output_dir, "APM", "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    # Copy Lua scripts
    copied = 0
    for script in REQUIRED_LUA_SCRIPTS:
        src = os.path.join(LUA_DIR, script)
        dst = os.path.join(scripts_dir, script)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            copied += 1
            print(f"  Copied: {script}")
        else:
            print(f"  SKIP (not found): {script}")

    # Copy param file
    params_dir = os.path.join(output_dir, "APM", "params")
    os.makedirs(params_dir, exist_ok=True)
    if os.path.isfile(PARAM_FILE):
        shutil.copy2(PARAM_FILE, os.path.join(params_dir, "striper.param"))
        print(f"  Copied: striper.param")

    print(f"\n  SD card staging ready at: {output_dir}")
    print(f"  Copied {copied} Lua scripts + param file")
    print(f"\n  To deploy: copy contents of {output_dir}/APM/ to your SD card's APM/ folder")
    return output_dir


def print_preflight_checklist():
    """Print pre-flight checklist."""
    print()
    print("=" * 60)
    print("  PRE-FLIGHT CHECKLIST")
    print("=" * 60)
    print()
    print("  HARDWARE:")
    print("  [ ] Battery fully charged (36V nominal, >37V measured)")
    print("  [ ] E-stop button tested (press = motors stop)")
    print("  [ ] GPS antenna mounted high, clear sky view")
    print("  [ ] Wheels tight, no wobble, tires inflated")
    print("  [ ] All wiring secure, no loose connectors")
    print("  [ ] Paint tank filled, cap secure")
    print("  [ ] Nozzle clear (test spray with water)")
    print("  [ ] RC transmitter powered on, bound")
    print()
    print("  SOFTWARE:")
    print("  [ ] Param file loaded in Mission Planner")
    print("  [ ] Lua scripts on SD card (/APM/scripts/)")
    print("  [ ] Mission waypoints uploaded")
    print("  [ ] Geofence polygon uploaded (matches lot boundary)")
    print("  [ ] Telemetry link connected")
    print("  [ ] GPS shows 'RTK Fixed' (>= 15 sats)")
    print()
    print("  FIELD CHECKS:")
    print("  [ ] Lot surface dry")
    print("  [ ] No vehicles/pedestrians in paint zone")
    print("  [ ] Cones or barriers placed at lot entrances")
    print("  [ ] Weather: no rain forecast for 2+ hours")
    print("  [ ] Wind < 10 mph (paint overspray)")
    print("  [ ] Temperature 50-90F (paint curing)")
    print()
    print("  FIRST-RUN EXTRAS:")
    print("  [ ] Compass calibrated")
    print("  [ ] Motor direction verified (both forward)")
    print("  [ ] RC channel mapping verified")
    print("  [ ] Test drive in MANUAL mode (10ft forward/back)")
    print("  [ ] Test paint with water before real paint")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Striper Robot Deployment Validator",
    )
    parser.add_argument("--sd-output", type=str,
                        help="Directory to stage SD card files")
    parser.add_argument("--waypoints", type=str,
                        help="Waypoints file to validate")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  STRIPER ROBOT - DEPLOYMENT VALIDATOR")
    print("=" * 60)
    print()

    all_issues = []

    # 1. Validate params
    print("[1/4] Checking striper.param...")
    if not os.path.isfile(PARAM_FILE):
        print(f"  ERROR: param file not found at {PARAM_FILE}")
        all_issues.append(("ERROR", "Param file not found"))
    else:
        params = load_params(PARAM_FILE)
        print(f"  Loaded {len(params)} parameters")
        issues = validate_params(params)
        issues += validate_relay_consistency(params)
        all_issues += issues
        if not issues:
            print("  All required params: OK")
        for level, msg in issues:
            print(f"  {level}: {msg}")
    print()

    # 2. Validate Lua scripts
    print("[2/4] Checking Lua scripts...")
    issues = validate_lua_scripts()
    all_issues += issues
    found = [s for s in REQUIRED_LUA_SCRIPTS if os.path.isfile(os.path.join(LUA_DIR, s))]
    print(f"  Found {len(found)}/{len(REQUIRED_LUA_SCRIPTS)} scripts")
    if not issues:
        print("  All scripts: OK")
    for level, msg in issues:
        print(f"  {level}: {msg}")
    print()

    # 3. Validate waypoints (if provided)
    if args.waypoints:
        print("[3/4] Checking waypoints file...")
        issues = validate_waypoints(args.waypoints)
        all_issues += issues
        if not issues:
            print("  Waypoints: OK")
        for level, msg in issues:
            print(f"  {level}: {msg}")
    else:
        print("[3/4] Waypoints: skipped (use --waypoints to validate)")
    print()

    # 4. Prepare SD card (if requested)
    if args.sd_output:
        print("[4/4] Preparing SD card staging directory...")
        prepare_sd_card(args.sd_output)
    else:
        print("[4/4] SD card: skipped (use --sd-output DIR to stage)")
    print()

    # Summary
    errors = [i for i in all_issues if i[0] == "ERROR"]
    warnings = [i for i in all_issues if i[0] in ("WARN", "WRONG", "MISSING")]

    print("=" * 60)
    if not errors and not warnings:
        print("  ALL CHECKS PASSED - ready to deploy!")
    elif not errors:
        print(f"  PASSED with {len(warnings)} warning(s)")
    else:
        print(f"  FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    print("=" * 60)

    # Always show checklist
    print_preflight_checklist()

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
