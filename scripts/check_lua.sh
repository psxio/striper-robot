#!/usr/bin/env bash
# =============================================================================
# check_lua.sh — Local Lua syntax checker for ArduRover scripts
# =============================================================================
# Usage: bash scripts/check_lua.sh
# Requires: lua5.3 (luac) installed locally

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUA_DIR="$SCRIPT_DIR/../ardurover/lua"

# Find luac binary (try common names)
LUAC=""
for cmd in luac5.3 luac53 luac; do
    if command -v "$cmd" &>/dev/null; then
        LUAC="$cmd"
        break
    fi
done

if [ -z "$LUAC" ]; then
    echo "ERROR: luac not found. Install Lua 5.3:"
    echo "  Ubuntu/Debian: sudo apt install lua5.3"
    echo "  macOS:         brew install lua@5.3"
    echo "  Windows:       choco install lua53"
    exit 1
fi

echo "Using: $LUAC ($($LUAC -v 2>&1 || true))"
echo "Checking: $LUA_DIR/*.lua"
echo ""

errors=0
checked=0

for f in "$LUA_DIR"/*.lua; do
    [ -f "$f" ] || continue
    checked=$((checked + 1))
    basename="$(basename "$f")"
    if $LUAC -p "$f" 2>&1; then
        echo "  OK  $basename"
    else
        echo "  FAIL $basename"
        errors=$((errors + 1))
    fi
done

echo ""
if [ "$checked" -eq 0 ]; then
    echo "WARNING: No .lua files found in $LUA_DIR"
    exit 1
elif [ "$errors" -gt 0 ]; then
    echo "FAIL: $errors/$checked file(s) with syntax errors"
    exit 1
else
    echo "PASS: $checked file(s) checked, all OK"
fi
