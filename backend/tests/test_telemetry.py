"""Tests for robot telemetry endpoints: heartbeat ingestion and telemetry queries."""

import pytest

from backend.database import get_db
from backend.services.robot_store import (
    create_robot,
    assign_robot,
    create_robot_claim,
    claim_robot_for_organization,
    _hash_api_key,
)


HEARTBEAT_URL = "/api/telemetry/heartbeat"
VALID_HEARTBEAT = {
    "battery_pct": 85,
    "lat": 33.749,
    "lng": -84.388,
    "state": "idle",
    "paint_level_pct": 60,
    "error_code": None,
    "rssi": -55,
}
API_KEY = "test-robot-key-abc123"


async def _create_robot_with_key(serial="TEL-001", api_key=API_KEY):
    """Helper: create a robot via the store and set its api_key hash directly in DB."""
    robot = await create_robot(serial_number=serial)
    async for db in get_db():
        await db.execute(
            "UPDATE robots SET api_key = ?, api_key_last4 = ? WHERE id = ?",
            (_hash_api_key(api_key), api_key[-4:], robot["id"]),
        )
        await db.commit()
    return robot


async def _register_user(client, email="telemetry_user@example.com"):
    """Helper: register a user and return (user_id, token)."""
    resp = await client.post("/api/auth/register", json={
        "email": email,
        "password": "testpass123",
        "name": "Telemetry User",
    })
    data = resp.json()
    return data["user"]["id"], data["token"]


# ---- 1. Heartbeat with valid API key ----


@pytest.mark.asyncio
async def test_heartbeat_valid_key(client):
    """POST /api/telemetry/heartbeat with a valid X-Robot-Key returns ok."""
    await _create_robot_with_key()

    resp = await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": API_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---- 2. Heartbeat rejected without X-Robot-Key header ----


@pytest.mark.asyncio
async def test_heartbeat_missing_key(client):
    """POST /api/telemetry/heartbeat without X-Robot-Key returns 401."""
    resp = await client.post(HEARTBEAT_URL, json=VALID_HEARTBEAT)
    assert resp.status_code == 401
    assert "X-Robot-Key" in resp.json()["detail"]


# ---- 3. Heartbeat rejected with invalid API key ----


@pytest.mark.asyncio
async def test_heartbeat_invalid_key(client):
    """POST /api/telemetry/heartbeat with an invalid key returns 401."""
    resp = await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": "totally-bogus-key"},
    )
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


# ---- 4. Get latest telemetry for own robot (assigned user) ----


@pytest.mark.asyncio
async def test_get_latest_telemetry_own_robot(client):
    """Assigned user can GET /api/telemetry/robot/{id}/latest for their own robot."""
    robot = await _create_robot_with_key(serial="TEL-OWN")
    user_id, token = await _register_user(client, email="own_robot@example.com")
    await assign_robot(robot["id"], user_id)

    # Send a heartbeat so there is telemetry data
    await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": API_KEY},
    )

    resp = await client.get(
        f"/api/telemetry/robot/{robot['id']}/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["battery_pct"] == 85
    assert data["state"] == "idle"
    assert data["lat"] == 33.749
    assert "created_at" in data


# ---- 5. Cannot see another user's robot telemetry ----


@pytest.mark.asyncio
async def test_cannot_see_other_users_robot(client):
    """A user cannot GET telemetry for a robot assigned to someone else (403)."""
    robot = await _create_robot_with_key(serial="TEL-OTHER")
    owner_id, _ = await _register_user(client, email="owner@example.com")
    await assign_robot(robot["id"], owner_id)

    # Send a heartbeat
    await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": API_KEY},
    )

    # Register a different user who does NOT own this robot
    _, intruder_token = await _register_user(client, email="intruder@example.com")

    resp = await client.get(
        f"/api/telemetry/robot/{robot['id']}/latest",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 403
    assert "Not authorized" in resp.json()["detail"]


# ---- 6. Admin can see any robot's telemetry ----


@pytest.mark.asyncio
async def test_admin_can_see_any_robot_telemetry(admin_client, client):
    """Admin can GET telemetry for any robot regardless of assignment."""
    robot = await _create_robot_with_key(serial="TEL-ADMIN")
    user_id, _ = await _register_user(client, email="someuser@example.com")
    await assign_robot(robot["id"], user_id)

    # Send a heartbeat
    await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": API_KEY},
    )

    resp = await admin_client.get(
        f"/api/telemetry/robot/{robot['id']}/latest",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["battery_pct"] == 85


@pytest.mark.asyncio
async def test_org_member_can_see_claimed_robot_telemetry(client):
    """A user can access telemetry for a robot claimed into their active organization."""
    robot = await _create_robot_with_key(serial="TEL-ORG")
    owner_id, owner_token = await _register_user(client, email="owner-org@example.com")

    client.headers["Authorization"] = f"Bearer {owner_token}"
    me = (await client.get("/api/auth/me")).json()
    claim, code = await create_robot_claim(robot["id"], owner_id)
    await claim_robot_for_organization(code, me["active_organization_id"], owner_id)

    await client.post(
        HEARTBEAT_URL,
        json=VALID_HEARTBEAT,
        headers={"X-Robot-Key": API_KEY},
    )

    resp = await client.get(
        f"/api/telemetry/robot/{robot['id']}/latest",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["battery_pct"] == 85


# ---- 7. Get latest returns 404 when no telemetry exists ----


@pytest.mark.asyncio
async def test_latest_returns_404_when_empty(client):
    """GET /api/telemetry/robot/{id}/latest returns 404 when no telemetry exists."""
    robot = await _create_robot_with_key(serial="TEL-EMPTY")
    user_id, token = await _register_user(client, email="empty_telem@example.com")
    await assign_robot(robot["id"], user_id)

    resp = await client.get(
        f"/api/telemetry/robot/{robot['id']}/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert "No telemetry" in resp.json()["detail"]


# ---- 8. Telemetry history with hours filter ----


@pytest.mark.asyncio
async def test_telemetry_history(client):
    """GET /api/telemetry/robot/{id}/history returns heartbeat records within the window."""
    robot = await _create_robot_with_key(serial="TEL-HIST")
    user_id, token = await _register_user(client, email="history@example.com")
    await assign_robot(robot["id"], user_id)

    # Send multiple heartbeats
    for i in range(3):
        await client.post(
            HEARTBEAT_URL,
            json={**VALID_HEARTBEAT, "battery_pct": 80 - i * 10},
            headers={"X-Robot-Key": API_KEY},
        )

    resp = await client.get(
        f"/api/telemetry/robot/{robot['id']}/history?hours=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["robot_id"] == robot["id"]
    assert len(data["items"]) == 3
    # Most recent first (DESC order)
    assert data["items"][0]["battery_pct"] == 60
    assert data["items"][2]["battery_pct"] == 80


# ---- 9. Heartbeat updates robot's last_seen_at and last_battery_pct ----


@pytest.mark.asyncio
async def test_heartbeat_updates_robot_summary(client):
    """Heartbeat POST updates the robots table last_seen_at and last_battery_pct fields."""
    robot = await _create_robot_with_key(serial="TEL-UPD")

    # Before heartbeat, last_seen_at should be None
    async for db in get_db():
        cursor = await db.execute(
            "SELECT last_seen_at, last_battery_pct, last_state FROM robots WHERE id = ?",
            (robot["id"],),
        )
        row = await cursor.fetchone()
        assert row["last_seen_at"] is None
        assert row["last_battery_pct"] is None

    # Send heartbeat
    await client.post(
        HEARTBEAT_URL,
        json={**VALID_HEARTBEAT, "battery_pct": 72, "state": "mowing"},
        headers={"X-Robot-Key": API_KEY},
    )

    # After heartbeat, fields should be updated
    async for db in get_db():
        cursor = await db.execute(
            "SELECT last_seen_at, last_battery_pct, last_state FROM robots WHERE id = ?",
            (robot["id"],),
        )
        row = await cursor.fetchone()
        assert row["last_seen_at"] is not None
        assert row["last_battery_pct"] == 72
        assert row["last_state"] == "mowing"


# ---- 10. Unauthenticated user cannot access telemetry endpoints ----


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_telemetry(client):
    """GET telemetry endpoints without Bearer token returns 401."""
    robot = await _create_robot_with_key(serial="TEL-NOAUTH")

    # No Authorization header at all
    resp = await client.get(f"/api/telemetry/robot/{robot['id']}/latest")
    assert resp.status_code == 401

    resp = await client.get(f"/api/telemetry/robot/{robot['id']}/history")
    assert resp.status_code == 401
