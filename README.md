# Strype — Autonomous Parking Lot Striping Robot

Open-source autonomous robot that paints parking lot lines with 8mm RTK GPS precision.

## Architecture

```
striper_pathgen/     Python path generation library (DXF/SVG import, templates, waypoint export)
ardurover/           ArduRover firmware configs, Lua scripts, SITL setup
  lua/               paint_unified, motor_bridge, obstacle_avoid, fence_check, rangefinder_bridge
  params/            striper.param (Pixhawk 6C configuration)
  sitl/              sim_striper.sh (SITL launcher + param validation)
backend/             Strype Cloud API (FastAPI + aiosqlite)
  routers/           Auth, billing, lots, jobs, schedules, estimates, telemetry, admin
  services/          Data stores, scheduler, shipping, email
  tests/             235+ pytest tests
site/                Frontend (vanilla JS + Leaflet map designer)
  index.html         Landing page
  platform.html      Lot designer + job scheduler
  admin.html         Admin dashboard
scripts/             CLI tools (deploy validator, SITL test harness, RTK setup, DB backup)
docs/                BOM, deployment guide, quick start, research
tests/e2e/           Playwright E2E tests (22 tests)
```

## Hardware

| Component | Spec |
|-----------|------|
| Controller | Pixhawk 6C Mini, ArduRover 4.5+ |
| GPS | Holybro H-RTK UM982, dual-antenna RTK (8mm position, 0.1 deg heading) |
| Motors | Hoverboard hub motors (FOC firmware over UART) |
| Paint | Shurflo 8000 pump + solenoid + TeeJet TP8004EVS nozzle |
| Battery | 36V 18Ah lithium (648 Wh), 2-4 hr runtime |
| Safety | E-stop + DC contactor, geofence, obstacle avoidance |
| BOM | ~$1,011 components ([validated BOM](docs/validated_bom_v3.md)) |

## Quickstart

```bash
# Backend
pip install -r backend/requirements.txt
pip install -e striper_pathgen/
cp .env.example .env  # edit with your keys
python scripts/run_backend.py --reload

# Tests
python -m pytest backend/tests/ -v
python scripts/run_playwright.py

# Path generation
python scripts/pathgen_cli.py --template parking_row --spaces 20 --output mission.waypoints

# SITL (requires ArduPilot source)
bash ardurover/sitl/sim_striper.sh
python scripts/sitl_test.py --connection tcp:127.0.0.1:5760
```

## Deployment

See [docs/deployment.md](docs/deployment.md) for deployment guidance for Railway and AWS ECS.

## License

Private repository. Contact for licensing.
