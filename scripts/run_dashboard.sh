#!/usr/bin/env bash
# ============================================================================
# run_dashboard.sh — Start the Striper dashboard web server
#
# Usage:
#   ./scripts/run_dashboard.sh                    # default port 8000
#   DASHBOARD_PORT=9000 ./scripts/run_dashboard.sh  # custom port
#
# Installs Python dependencies (if needed) and launches the FastAPI
# dashboard with uvicorn.
# ============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Resolve paths ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/dashboard"

if [ ! -d "$DASHBOARD_DIR" ]; then
    error "Dashboard directory not found at $DASHBOARD_DIR"
    exit 1
fi

cd "$DASHBOARD_DIR"

# ── Install dependencies ───────────────────────────────────────────────────
REQUIREMENTS="$DASHBOARD_DIR/requirements.txt"
if [ -f "$REQUIREMENTS" ]; then
    info "Checking Python dependencies..."
    # Only install if any package is missing (quick pip check)
    if ! pip show fastapi uvicorn > /dev/null 2>&1; then
        info "Installing dependencies from requirements.txt..."
        pip install -r "$REQUIREMENTS"
    else
        info "Dependencies already installed."
    fi
else
    warn "requirements.txt not found at $REQUIREMENTS — skipping dependency install."
fi

# ── Determine port ─────────────────────────────────────────────────────────
PORT="${DASHBOARD_PORT:-8000}"

# ── Print instructions ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Striper Dashboard${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  URL:      http://localhost:${PORT}"
echo "  API docs: http://localhost:${PORT}/docs"
echo "  WebSocket: ws://localhost:${PORT}/ws"
echo ""
echo "  Set DASHBOARD_PORT env var to change the port (default: 8000)."
echo "  Press Ctrl-C to stop the server."
echo ""

# ── Launch ─────────────────────────────────────────────────────────────────
cd "$PROJECT_ROOT"
uvicorn dashboard.backend.main:app --host 0.0.0.0 --port "${PORT}"
