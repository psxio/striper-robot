#!/usr/bin/env bash
# =============================================================================
# sim_striper.sh - ArduRover SITL Launcher for Parking Lot Line Striper
# =============================================================================
# Launches ArduRover in Software-In-The-Loop (SITL) mode with our parameter
# file and Lua scripts, simulating the striper robot at a parking lot.
#
# Prerequisites:
#   - ArduPilot source code cloned and built (with sim_vehicle.py available)
#   - Python 3 with MAVProxy installed: pip install MAVProxy
#   - waf build completed: ./waf configure --board sitl && ./waf rover
#
# Usage:
#   chmod +x sim_striper.sh
#   ./sim_striper.sh
#
# Connecting Mission Planner to SITL:
#   1. Run this script - it starts MAVProxy on TCP port 5760 and UDP 14550/14551
#   2. In Mission Planner: top-right dropdown -> TCP -> Connect -> 127.0.0.1:5760
#   3. Or use UDP: top-right dropdown -> UDP -> Connect -> port 14550
#   4. If running Mission Planner on another machine on the LAN, use:
#      --out udp:<LAN_IP>:14550 in the sim_vehicle.py command below
#
# Connecting QGroundControl:
#   QGC automatically listens on UDP 14550 - it should connect automatically.
# =============================================================================

set -euo pipefail

# ---- Configuration ----------------------------------------------------------

# Path to ArduPilot source tree (adjust to your local clone)
ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot}"

# Path to our parameter file (absolute or relative to this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAM_FILE="${SCRIPT_DIR}/../params/striper.param"
LUA_SCRIPT_DIR="${SCRIPT_DIR}/../lua"

# Simulated location: a parking lot (lat, lon, alt, heading)
# Default: a generic open parking lot area (adjust to your test site)
# Format: lat,lon,alt,heading
SIM_LOCATION="33.4484,-112.0740,331,0"   # Phoenix, AZ area (flat, open)

# Vehicle type
VEHICLE="Rover"

# ---- Pre-flight checks ------------------------------------------------------

if [ ! -d "$ARDUPILOT_DIR" ]; then
    echo "ERROR: ArduPilot directory not found at: $ARDUPILOT_DIR"
    echo "Set ARDUPILOT_DIR environment variable to your ardupilot clone path."
    echo ""
    echo "To clone ArduPilot:"
    echo "  git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git"
    echo "  cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y"
    echo "  ./waf configure --board sitl && ./waf rover"
    exit 1
fi

if [ ! -f "$PARAM_FILE" ]; then
    echo "ERROR: Parameter file not found at: $PARAM_FILE"
    exit 1
fi

# ---- Prepare Lua scripts for SITL -------------------------------------------

# SITL looks for Lua scripts in the scripts/ directory relative to where it runs
# Create a symlink or copy scripts to the SITL working directory
SITL_SCRIPTS_DIR="$ARDUPILOT_DIR/Tools/autotest/scripts"
mkdir -p "$SITL_SCRIPTS_DIR"

echo "Copying Lua scripts to SITL scripts directory..."
if [ -d "$LUA_SCRIPT_DIR" ]; then
    cp -v "$LUA_SCRIPT_DIR"/*.lua "$SITL_SCRIPTS_DIR/" 2>/dev/null || true
fi

# ---- Launch SITL -------------------------------------------------------------

echo "============================================================"
echo " ArduRover SITL - Parking Lot Line Striper"
echo "============================================================"
echo " Parameter file : $PARAM_FILE"
echo " Lua scripts    : $LUA_SCRIPT_DIR"
echo " Sim location   : $SIM_LOCATION"
echo " Vehicle        : $VEHICLE"
echo "============================================================"
echo ""
echo " After launch, MAVProxy console commands:"
echo "   mode manual        - switch to manual mode"
echo "   mode auto          - switch to auto mode (run mission)"
echo "   arm throttle       - arm the vehicle"
echo "   wp load <file>     - load a waypoint mission file"
echo "   relay set 0 1      - turn paint solenoid ON"
echo "   relay set 0 0      - turn paint solenoid OFF"
echo "   module load map    - open the map window"
echo "   module load console - open the console window"
echo ""
echo " Connect Mission Planner via TCP 127.0.0.1:5760"
echo " Connect QGroundControl via UDP 14550 (auto-detected)"
echo "============================================================"
echo ""

cd "$ARDUPILOT_DIR"

# Launch sim_vehicle.py with our parameters
# --add-param-file loads our custom parameters on top of defaults
# -l sets the simulated GPS location
# --map opens the MAVProxy map module
# --console opens the MAVProxy console
# -w wipes the virtual EEPROM (clean start with our params)
python3 Tools/autotest/sim_vehicle.py \
    -v "$VEHICLE" \
    -l "$SIM_LOCATION" \
    --add-param-file "$PARAM_FILE" \
    --map \
    --console \
    -w \
    --out "udp:127.0.0.1:14550" \
    --out "udp:127.0.0.1:14551"

# =============================================================================
# SITL Testing Workflow:
# =============================================================================
# 1. Start SITL with this script
# 2. Open Mission Planner, connect via TCP 5760 or UDP 14550
# 3. In Mission Planner Flight Plan tab:
#    a. Draw waypoints for a parking lot stripe pattern
#    b. Insert DO_SET_RELAY(0,1) before paint-start waypoints
#    c. Insert DO_SET_RELAY(0,0) after paint-end waypoints
#    d. Write waypoints to vehicle
# 4. In MAVProxy or Mission Planner:
#    a. Arm the vehicle: arm throttle
#    b. Switch to AUTO mode: mode auto
#    c. Watch the simulated robot follow the stripe pattern
#    d. Check messages for paint ON/OFF events from Lua scripts
# 5. Test geofence:
#    a. Draw a polygon fence in Mission Planner
#    b. Upload fence
#    c. Manually steer robot outside fence to verify fence_check.lua triggers
# =============================================================================
