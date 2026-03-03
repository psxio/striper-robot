"""Tests for the /api/robot endpoints."""

import pytest


# ---------------------------------------------------------------------------
# GET /api/robot/status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/api/robot/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "state" in body
    assert "position" in body
    assert "speed" in body
    assert "heading" in body
    assert "battery" in body
    assert "paint_level" in body
    assert "gps_accuracy" in body
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_get_status_default_idle(client):
    resp = await client.get("/api/robot/status")
    body = resp.json()
    assert body["state"] == "idle"
    assert body["speed"] == 0.0


# ---------------------------------------------------------------------------
# POST /api/robot/estop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estop(client):
    resp = await client.post("/api/robot/estop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "E-Stop activated" in body["message"]

    # Robot state should now be estopped
    status = await client.get("/api/robot/status")
    assert status.json()["state"] == "estopped"


# ---------------------------------------------------------------------------
# POST /api/robot/release-estop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_release_estop(client):
    # First activate e-stop
    await client.post("/api/robot/estop")

    resp = await client.post("/api/robot/release-estop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "E-Stop released" in body["message"]

    # Robot state should be idle again
    status = await client.get("/api/robot/status")
    assert status.json()["state"] == "idle"


# ---------------------------------------------------------------------------
# GET /api/robot/position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_position(client):
    resp = await client.get("/api/robot/position")
    assert resp.status_code == 200
    body = resp.json()
    assert "lat" in body
    assert "lng" in body
    assert isinstance(body["lat"], float)
    assert isinstance(body["lng"], float)


@pytest.mark.asyncio
async def test_get_position_has_default(client):
    """The mock bridge initialises with a known default position."""
    resp = await client.get("/api/robot/position")
    body = resp.json()
    # Default position from RosBridge.__init__
    assert body["lat"] == pytest.approx(30.2672, abs=0.01)
    assert body["lng"] == pytest.approx(-97.7431, abs=0.01)
