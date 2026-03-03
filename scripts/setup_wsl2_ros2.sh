#!/usr/bin/env bash
# ============================================================================
# setup_wsl2_ros2.sh — Automated ROS 2 Humble installation for WSL2 Ubuntu
#
# Usage:
#   chmod +x scripts/setup_wsl2_ros2.sh
#   ./scripts/setup_wsl2_ros2.sh
#
# This script installs ROS 2 Humble Desktop, navigation and simulation
# packages, colcon build tools, and Python dependencies required by the
# Striper parking-lot line-painting robot project.
# ============================================================================
set -euo pipefail

# ── Colours for output ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Check WSL2 ─────────────────────────────────────────────────────────────
if [ ! -f /proc/version ]; then
    error "Cannot read /proc/version. Are you running on Linux / WSL2?"
    exit 1
fi

if grep -qi microsoft /proc/version; then
    info "WSL2 environment detected."
else
    warn "This does not appear to be a WSL2 environment."
    warn "The script is designed for WSL2 Ubuntu but will continue anyway."
    read -rp "Press Enter to continue or Ctrl-C to abort..."
fi

# ── Check Ubuntu version ───────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "OS: ${PRETTY_NAME:-unknown}"
    if [[ "${VERSION_ID:-}" != "22.04" ]]; then
        warn "ROS 2 Humble targets Ubuntu 22.04 (Jammy). You have ${VERSION_ID:-unknown}."
        warn "Installation may not work correctly on other releases."
    fi
fi

# ── Locale setup ───────────────────────────────────────────────────────────
info "Ensuring UTF-8 locale..."
sudo apt-get update -qq && sudo apt-get install -y -qq locales > /dev/null
sudo locale-gen en_US en_US.UTF-8 > /dev/null
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# ── Add ROS 2 apt repository ──────────────────────────────────────────────
info "Adding the ROS 2 apt repository..."
sudo apt-get install -y -qq software-properties-common curl gnupg lsb-release > /dev/null

# Add the ROS 2 GPG key
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg

# Add the repository to sources list
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
    | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt-get update -qq

# ── Install ROS 2 Humble packages ─────────────────────────────────────────
info "Installing ROS 2 Humble packages (this may take several minutes)..."
sudo apt-get install -y \
    ros-humble-desktop \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-robot-localization \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-xacro \
    ros-humble-joint-state-publisher \
    ros-humble-robot-state-publisher

# ── Install colcon build tools ─────────────────────────────────────────────
info "Installing colcon build tools..."
sudo apt-get install -y \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool

# Initialise rosdep if not already done
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    info "Initialising rosdep..."
    sudo rosdep init || true
fi
rosdep update --rosdistro=humble || true

# ── Install Python dependencies ────────────────────────────────────────────
info "Installing Python dependencies..."
sudo apt-get install -y python3-pip > /dev/null
pip3 install --user ezdxf svgpathtools

# ── Add ROS 2 source to .bashrc ───────────────────────────────────────────
BASHRC="$HOME/.bashrc"
ROS_SOURCE_LINE="source /opt/ros/humble/setup.bash"
if ! grep -qF "$ROS_SOURCE_LINE" "$BASHRC" 2>/dev/null; then
    info "Adding ROS 2 source to $BASHRC..."
    echo "" >> "$BASHRC"
    echo "# ROS 2 Humble (added by striper setup script)" >> "$BASHRC"
    echo "$ROS_SOURCE_LINE" >> "$BASHRC"
else
    info "ROS 2 source already present in $BASHRC."
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  ROS 2 Humble installation complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Open a new terminal (or run: source ~/.bashrc)"
echo "  2. Build the workspace:"
echo "       cd $(dirname "$(realpath "$0")")/.. && ./scripts/build_workspace.sh"
echo "  3. Launch the simulation:"
echo "       ./scripts/run_simulation.sh"
echo ""
echo "Verify your installation:"
echo "  ros2 --version"
echo "  ros2 pkg list | grep striper"
echo ""
