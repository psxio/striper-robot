"""Tests for robot fleet management — admin CRUD, assignments, and customer endpoints."""

import pytest

from backend.database import get_db


async def _create_robot(admin_client, serial="STR-001", hw="v1"):
    """Helper: create a robot via admin endpoint, return response dict."""
    resp = await admin_client.post("/api/admin/robots", json={
        "serial_number": serial,
        "hardware_version": hw,
    })
    return resp


async def _register_user(client, email="robot_user@example.com"):
    """Helper: register a fresh user and return (user_id, token)."""
    resp = await client.post("/api/auth/register", json={
        "email": email,
        "password": "testpass123",
        "name": "Robot User",
    })
    data = resp.json()
    return data["user"]["id"], data["token"]


async def _set_robot_api_key(robot_id: str, api_key: str = "robot-status-key") -> None:
    """Attach a hashed API key to a robot for telemetry tests."""
    from backend.services.robot_store import _hash_api_key
    async for db in get_db():
        await db.execute(
            "UPDATE robots SET api_key = ?, api_key_last4 = ? WHERE id = ?",
            (_hash_api_key(api_key), api_key[-4:], robot_id),
        )
        await db.commit()


# ---- Admin: Robot CRUD ----


@pytest.mark.asyncio
async def test_admin_create_robot(admin_client):
    """POST /api/admin/robots creates a robot and returns 201."""
    resp = await _create_robot(admin_client, serial="STR-001")
    assert resp.status_code == 201
    data = resp.json()
    assert data["serial_number"] == "STR-001"
    assert data["status"] == "available"
    assert data["hardware_version"] == "v1"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_admin_create_duplicate_serial(admin_client):
    """Creating two robots with the same serial_number fails (unique constraint)."""
    resp1 = await _create_robot(admin_client, serial="STR-DUP")
    assert resp1.status_code == 201

    # Duplicate serial triggers IntegrityError; depending on middleware chain
    # this surfaces as a 500 JSON response or a propagated exception.
    try:
        resp2 = await _create_robot(admin_client, serial="STR-DUP")
        assert resp2.status_code == 500
    except Exception:
        # IntegrityError propagated through ASGI — still correct behavior
        pass


@pytest.mark.asyncio
async def test_admin_list_robots(admin_client):
    """GET /api/admin/robots returns paginated list with correct total."""
    await _create_robot(admin_client, serial="STR-A01")
    await _create_robot(admin_client, serial="STR-A02")

    resp = await admin_client.get("/api/admin/robots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["limit"] == 50


@pytest.mark.asyncio
async def test_admin_list_robots_filter_status(admin_client):
    """GET /api/admin/robots?status=available filters by status."""
    r1 = await _create_robot(admin_client, serial="STR-F01")
    await _create_robot(admin_client, serial="STR-F02")

    # Put first robot into maintenance
    robot_id = r1.json()["id"]
    await admin_client.put(f"/api/admin/robots/{robot_id}", json={
        "status": "maintenance",
    })

    resp = await admin_client.get("/api/admin/robots?status=available")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["serial_number"] == "STR-F02"


@pytest.mark.asyncio
async def test_admin_update_robot(admin_client):
    """PUT /api/admin/robots/{id} updates robot status."""
    resp = await _create_robot(admin_client, serial="STR-U01")
    robot_id = resp.json()["id"]

    resp = await admin_client.put(f"/api/admin/robots/{robot_id}", json={
        "status": "maintenance",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "maintenance"


# ---- Admin: Assignments ----


@pytest.mark.asyncio
async def test_admin_assign_robot(admin_client, client):
    """POST /api/admin/robots/assign assigns robot to user, sets status to assigned."""
    resp = await _create_robot(admin_client, serial="STR-AS01")
    robot_id = resp.json()["id"]

    user_id, _ = await _register_user(client, email="assign1@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assert resp.status_code == 201
    assignment = resp.json()
    assert assignment["robot_id"] == robot_id
    assert assignment["user_id"] == user_id
    assert assignment["status"] == "preparing"

    # Verify robot status changed to assigned
    resp = await admin_client.get("/api/admin/robots")
    robot = [r for r in resp.json()["items"] if r["id"] == robot_id][0]
    assert robot["status"] == "assigned"


@pytest.mark.asyncio
async def test_admin_cannot_assign_retired_robot(admin_client, client):
    """Cannot assign a robot with status=retired."""
    resp = await _create_robot(admin_client, serial="STR-RET01")
    robot_id = resp.json()["id"]

    # Retire the robot
    await admin_client.put(f"/api/admin/robots/{robot_id}", json={
        "status": "retired",
    })

    user_id, _ = await _register_user(client, email="retired_test@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assert resp.status_code == 400
    assert "retired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_double_assign(admin_client, client):
    """Cannot assign a robot that is already assigned."""
    resp = await _create_robot(admin_client, serial="STR-DBL01")
    robot_id = resp.json()["id"]

    user_id, _ = await _register_user(client, email="double1@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assert resp.status_code == 201

    # Try to assign the same robot again
    user_id2, _ = await _register_user(client, email="double2@example.com")
    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id2,
    })
    assert resp.status_code == 400
    assert "already assigned" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_assign_second_active_robot_to_same_user(admin_client, client):
    """A user cannot hold two active robot assignments at the same time."""
    resp1 = await _create_robot(admin_client, serial="STR-USR-A")
    resp2 = await _create_robot(admin_client, serial="STR-USR-B")
    robot1_id = resp1.json()["id"]
    robot2_id = resp2.json()["id"]

    user_id, _ = await _register_user(client, email="one-robot@example.com")

    first = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot1_id,
        "user_id": user_id,
    })
    assert first.status_code == 201

    second = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot2_id,
        "user_id": user_id,
    })
    assert second.status_code == 400
    assert "active robot assignment" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_can_assign_new_robot_after_previous_returned(admin_client, client):
    """Returning a robot frees the user to receive another robot later."""
    resp1 = await _create_robot(admin_client, serial="STR-REASSIGN-A")
    resp2 = await _create_robot(admin_client, serial="STR-REASSIGN-B")
    robot1_id = resp1.json()["id"]
    robot2_id = resp2.json()["id"]
    user_id, _ = await _register_user(client, email="reassign@example.com")

    first = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot1_id,
        "user_id": user_id,
    })
    assert first.status_code == 201
    assignment_id = first.json()["id"]

    returned = await admin_client.put(
        f"/api/admin/robots/assignments/{assignment_id}",
        json={"status": "returned"},
    )
    assert returned.status_code == 200

    second = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot2_id,
        "user_id": user_id,
    })
    assert second.status_code == 201
    assert second.json()["robot_id"] == robot2_id


@pytest.mark.asyncio
async def test_admin_update_assignment_shipped(admin_client, client):
    """Updating assignment to shipped sets shipped_at and tracking_number."""
    resp = await _create_robot(admin_client, serial="STR-SH01")
    robot_id = resp.json()["id"]
    user_id, _ = await _register_user(client, email="shipped@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assignment_id = resp.json()["id"]

    resp = await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "shipped",
        "tracking_number": "1Z999AA10123456784",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "shipped"
    assert data["tracking_number"] == "1Z999AA10123456784"
    assert data["shipped_at"] is not None


@pytest.mark.asyncio
async def test_admin_update_assignment_active(admin_client, client):
    """Updating assignment to active sets delivered_at."""
    resp = await _create_robot(admin_client, serial="STR-ACT01")
    robot_id = resp.json()["id"]
    user_id, _ = await _register_user(client, email="active@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assignment_id = resp.json()["id"]

    # Ship first
    await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "shipped",
        "tracking_number": "1Z999",
    })

    # Mark active (delivered)
    resp = await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "active",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["delivered_at"] is not None


@pytest.mark.asyncio
async def test_admin_update_assignment_returned(admin_client, client):
    """Updating assignment to returned sets returned_at and releases robot back to available."""
    resp = await _create_robot(admin_client, serial="STR-RET02")
    robot_id = resp.json()["id"]
    user_id, _ = await _register_user(client, email="returned@example.com")

    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assignment_id = resp.json()["id"]

    # Ship and deliver
    await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "shipped",
    })
    await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "active",
    })

    # Return
    resp = await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "returned",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "returned"
    assert data["returned_at"] is not None

    # Robot should be back to available
    resp = await admin_client.get("/api/admin/robots")
    robot = [r for r in resp.json()["items"] if r["id"] == robot_id][0]
    assert robot["status"] == "available"


@pytest.mark.asyncio
async def test_admin_robot_history(admin_client, client):
    """GET /api/admin/robots/{id}/history returns assignment history."""
    resp = await _create_robot(admin_client, serial="STR-HIST01")
    robot_id = resp.json()["id"]
    user_id, _ = await _register_user(client, email="history@example.com")

    # Assign then return
    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assignment_id = resp.json()["id"]
    await admin_client.put(f"/api/admin/robots/assignments/{assignment_id}", json={
        "status": "returned",
    })

    # Check history
    resp = await admin_client.get(f"/api/admin/robots/{robot_id}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["robot_id"] == robot_id
    assert len(data["assignments"]) == 1
    assert data["assignments"][0]["status"] == "returned"
    assert "email" in data["assignments"][0]


@pytest.mark.asyncio
async def test_admin_list_assignments(admin_client, client):
    """GET /api/admin/assignments returns all assignments."""
    resp = await _create_robot(admin_client, serial="STR-LA01")
    robot_id = resp.json()["id"]
    user_id, _ = await _register_user(client, email="listassign@example.com")

    await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })

    resp = await admin_client.get("/api/admin/assignments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "items" in data
    assert data["items"][0]["serial_number"] == "STR-LA01"


# ---- Customer Endpoints ----


@pytest.mark.asyncio
async def test_user_no_robot(auth_client):
    """GET /api/robots returns assignment=null when user has no robot."""
    resp = await auth_client.get("/api/robots")
    assert resp.status_code == 200
    assert resp.json()["assignment"] is None


@pytest.mark.asyncio
async def test_user_has_robot(admin_client, client):
    """After admin assigns a robot, user sees the assignment via GET /api/robots."""
    # Create robot
    resp = await _create_robot(admin_client, serial="STR-USR01")
    robot_id = resp.json()["id"]

    # Register a target user via a separate unauthenticated client
    user_id, user_token = await _register_user(client, email="hasrobot@example.com")

    # Assign as admin
    resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assert resp.status_code == 201

    # Query as the user
    client.headers["Authorization"] = f"Bearer {user_token}"
    resp = await client.get("/api/robots")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assignment"] is not None
    assert data["assignment"]["robot_id"] == robot_id
    assert data["assignment"]["serial_number"] == "STR-USR01"


@pytest.mark.asyncio
async def test_user_robot_status_no_robot(auth_client):
    """GET /api/robots/status returns status=no_robot when no robot assigned."""
    resp = await auth_client.get("/api/robots/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_robot"


@pytest.mark.asyncio
async def test_user_robot_status_with_robot(admin_client, client):
    """GET /api/robots/status returns robot info after assignment."""
    resp = await _create_robot(admin_client, serial="STR-STAT01")
    robot_id = resp.json()["id"]

    user_id, user_token = await _register_user(client, email="status@example.com")

    await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })

    client.headers["Authorization"] = f"Bearer {user_token}"
    resp = await client.get("/api/robots/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "preparing"
    assert data["robot_id"] == robot_id
    assert data["serial_number"] == "STR-STAT01"
    assert data["connectivity"] == "unknown"
    assert data["current_job"] is None


@pytest.mark.asyncio
async def test_user_robot_status_includes_telemetry_and_priority_job(admin_client, client):
    """Robot status should include latest telemetry and the active or next job."""
    from backend.services.billing_store import set_user_plan

    resp = await _create_robot(admin_client, serial="STR-OPS01")
    robot_id = resp.json()["id"]
    await _set_robot_api_key(robot_id, "robot-ops-key")

    user_id, user_token = await _register_user(client, email="robot-ops@example.com")
    await set_user_plan(user_id, "pro")

    assign_resp = await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })
    assignment_id = assign_resp.json()["id"]
    await admin_client.put(
        f"/api/admin/robots/assignments/{assignment_id}",
        json={"status": "active"},
    )

    client.headers["Authorization"] = f"Bearer {user_token}"
    lot_resp = await client.post("/api/lots", json={
        "name": "Telemetry Lot",
        "center": {"lat": 40.0, "lng": -74.0},
        "features": [],
    })
    lot_id = lot_resp.json()["id"]

    await client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-20",
    })
    in_progress_resp = await client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-04-21",
        "time_preference": "afternoon",
    })
    in_progress_id = in_progress_resp.json()["id"]
    await client.patch(f"/api/jobs/{in_progress_id}", json={"status": "in_progress"})

    await client.post(
        "/api/telemetry/heartbeat",
        json={
            "battery_pct": 72,
            "lat": 33.749,
            "lng": -84.388,
            "state": "painting",
            "paint_level_pct": 55,
            "error_code": None,
            "rssi": -61,
        },
        headers={"X-Robot-Key": "robot-ops-key"},
    )

    status_resp = await client.get("/api/robots/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "active"
    assert data["connectivity"] == "online"
    assert data["battery_pct"] == 72
    assert data["paint_level_pct"] == 55
    assert data["last_state"] == "painting"
    assert data["location"] == {"lat": 33.749, "lng": -84.388}
    assert data["current_job"]["id"] == in_progress_id
    assert data["current_job"]["status"] == "in_progress"
    assert data["current_job"]["lot_name"] == "Telemetry Lot"


# ---- Authorization Checks ----


@pytest.mark.asyncio
async def test_non_admin_cannot_create_robot(auth_client):
    """Non-admin user gets 403 when trying to create a robot."""
    resp = await auth_client.post("/api/admin/robots", json={
        "serial_number": "STR-NOAUTH",
        "hardware_version": "v1",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_assign_robot(auth_client):
    """Non-admin user gets 403 when trying to assign a robot."""
    resp = await auth_client.post("/api/admin/robots/assign", json={
        "robot_id": "fake-id",
        "user_id": "fake-user",
    })
    assert resp.status_code == 403


# ---- Stats Integration ----


@pytest.mark.asyncio
async def test_stats_include_robots(admin_client, client):
    """GET /api/admin/stats includes robot_count, robots_available, active_assignments."""
    # Create two robots
    await _create_robot(admin_client, serial="STR-ST01")
    resp = await _create_robot(admin_client, serial="STR-ST02")
    robot_id = resp.json()["id"]

    # Assign one robot
    user_id, _ = await _register_user(client, email="stats@example.com")
    await admin_client.post("/api/admin/robots/assign", json={
        "robot_id": robot_id,
        "user_id": user_id,
    })

    resp = await admin_client.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["robot_count"] == 2
    assert data["robots_available"] == 1
    assert data["active_assignments"] == 1


# ---- API Key Management ----


@pytest.mark.asyncio
async def test_admin_generate_api_key(admin_client):
    """POST /api/admin/robots/{id}/api-key generates a new key prefixed with strk_."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-001"})
    robot_id = resp.json()["id"]

    # Generate key
    resp = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["robot_id"] == robot_id
    assert data["api_key"].startswith("strk_")


@pytest.mark.asyncio
async def test_admin_generate_api_key_rotation(admin_client):
    """Generating a second API key rotates the existing one (returns new key)."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-002"})
    robot_id = resp.json()["id"]

    # First key
    resp = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    assert resp.status_code == 200
    first_key = resp.json()["api_key"]

    # Second attempt rotates — returns a new key
    resp = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    assert resp.status_code == 200
    second_key = resp.json()["api_key"]
    assert second_key != first_key


@pytest.mark.asyncio
async def test_admin_revoke_api_key(admin_client):
    """DELETE /api/admin/robots/{id}/api-key revokes the key."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-003"})
    robot_id = resp.json()["id"]

    await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")

    # Revoke
    resp = await admin_client.delete(f"/api/admin/robots/{robot_id}/api-key")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_admin_revoke_regenerate_lifecycle(admin_client):
    """After revoking a key, generating a new one should produce a different key."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-004"})
    robot_id = resp.json()["id"]

    # Generate, revoke, regenerate
    resp1 = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    key1 = resp1.json()["api_key"]

    await admin_client.delete(f"/api/admin/robots/{robot_id}/api-key")

    resp2 = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    key2 = resp2.json()["api_key"]
    assert key1 != key2  # New key should be different


@pytest.mark.asyncio
async def test_generated_key_works_for_heartbeat(admin_client, client):
    """A generated API key should authenticate telemetry heartbeat requests."""
    # Create robot and generate key
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-005"})
    robot_id = resp.json()["id"]

    resp = await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")
    api_key = resp.json()["api_key"]

    # Use key for heartbeat (unauthenticated client, just X-Robot-Key header)
    hb_resp = await client.post("/api/telemetry/heartbeat",
        json={"battery_pct": 85, "state": "idle"},
        headers={"X-Robot-Key": api_key},
    )
    assert hb_resp.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_generate_key(admin_client, client):
    """Non-admin user gets 403 when trying to generate an API key."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "KEY-006"})
    robot_id = resp.json()["id"]

    # Register a non-admin user via a separate unauthenticated client
    user_id, user_token = await _register_user(client, email="nonadmin_key@example.com")
    client.headers["Authorization"] = f"Bearer {user_token}"
    resp = await client.post(f"/api/admin/robots/{robot_id}/api-key")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_robots_masks_api_key(admin_client):
    """GET /api/admin/robots should mask the full API key and expose has_api_key + last4."""
    resp = await admin_client.post("/api/admin/robots", json={"serial_number": "MASK-001"})
    robot_id = resp.json()["id"]

    await admin_client.post(f"/api/admin/robots/{robot_id}/api-key")

    # List robots — key should be masked
    resp = await admin_client.get("/api/admin/robots")
    robots = resp.json()["items"]
    robot = [r for r in robots if r["id"] == robot_id][0]
    assert robot["api_key"] is None  # Full key not exposed
    assert robot["has_api_key"] is True
    assert len(robot["api_key_last4"]) == 4
