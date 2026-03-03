#!/usr/bin/env bash
# ============================================================================
# build_workspace.sh — Build the Striper ROS 2 workspace with colcon
#
# Usage:
#   ./scripts/build_workspace.sh
#
# Sources the ROS 2 Humble setup, runs a colcon build with symlink-install
# in the striper_ws workspace, and reports the built packages.
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

if [ ! -d "$WORKSPACE/src" ]; then
    error "Workspace not found at $WORKSPACE/src"
    error "Make sure you are running this from the project root."
    exit 1
fi

# ── Source ROS 2 ───────────────────────────────────────────────────────────
ROS_SETUP="/opt/ros/humble/setup.bash"
if [ -f "$ROS_SETUP" ]; then
    info "Sourcing ROS 2 Humble..."
    # shellcheck disable=SC1091
    source "$ROS_SETUP"
else
    error "ROS 2 Humble not found at $ROS_SETUP."
    error "Run scripts/setup_wsl2_ros2.sh first."
    exit 1
fi

# ── Build ──────────────────────────────────────────────────────────────────
info "Building workspace at $WORKSPACE ..."
cd "$WORKSPACE"
colcon build --symlink-install

# ── Source the workspace ───────────────────────────────────────────────────
INSTALL_SETUP="$WORKSPACE/install/setup.bash"
if [ -f "$INSTALL_SETUP" ]; then
    info "Sourcing workspace install..."
    # shellcheck disable=SC1091
    source "$INSTALL_SETUP"
fi

# ── Report ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Build complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
info "Built packages:"
if [ -d "$WORKSPACE/install" ]; then
    for pkg_dir in "$WORKSPACE"/install/*/; do
        pkg_name="$(basename "$pkg_dir")"
        # Skip colcon marker directories
        if [[ "$pkg_name" == "." || "$pkg_name" == ".." ]]; then
            continue
        fi
        echo "  - $pkg_name"
    done
fi
echo ""
info "To use in your current shell, run:"
echo "  source $INSTALL_SETUP"
echo ""
