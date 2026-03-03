#!/usr/bin/env bash
# ============================================================================
# run_simulation.sh — Launch the full Striper simulation stack
#
# Usage:
#   ./scripts/run_simulation.sh
#   ./scripts/run_simulation.sh --no-gui          # headless (no Gazebo GUI)
#   ./scripts/run_simulation.sh --world custom     # custom world file
#
# Launches Gazebo with a parking lot world, spawns the robot model, and
# starts all localization, navigation, safety, and application nodes.
# ============================================================================
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Resolve paths ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE="$PROJECT_ROOT/striper_ws"

# ── Parse arguments ────────────────────────────────────────────────────────
GUI="true"
WORLD="parking_lot"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-gui)
            GUI="false"
            shift
            ;;
        --world)
            WORLD="$2"
            shift 2
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# ── Source ROS 2 and workspace ─────────────────────────────────────────────
ROS_SETUP="/opt/ros/humble/setup.bash"
if [ -f "$ROS_SETUP" ]; then
    # shellcheck disable=SC1091
    source "$ROS_SETUP"
else
    error "ROS 2 Humble not found. Run scripts/setup_wsl2_ros2.sh first."
    exit 1
fi

INSTALL_SETUP="$WORKSPACE/install/setup.bash"
if [ -f "$INSTALL_SETUP" ]; then
    # shellcheck disable=SC1091
    source "$INSTALL_SETUP"
else
    error "Workspace not built. Run scripts/build_workspace.sh first."
    exit 1
fi

# ── Launch ─────────────────────────────────────────────────────────────────
info "Launching Striper simulation (world=$WORLD, gui=$GUI)..."
echo ""

ros2 launch striper_bringup simulation.launch.py \
    gui:="$GUI" \
    world:="$WORLD" \
    "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
