"""Tests for P1 features: login lockout, waitlist dedup, admin delete, GDPR export, audit log."""

import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Test Lot",
    "center": {"lat": 40.0, "lng": -74.0},
}


# --- Login Lockout ---

@pytest.mark.asyncio
async def test_login_lockout_after_failures(client):
    """Account should be locked after 5 failed login attempts."""
    # Register a user first
    await client.post("/api/auth/register", json={
        "email": "lockout@example.com",
        "password": "testpass123",
    })

    # 5 failed attempts
    for _ in range(5):
        resp = await client.post("/api/auth/login", json={
            "email": "lockout@example.com",
            "password": "wrongpassword1",
        })
        assert resp.status_code == 401

    # 6th attempt should be locked out (429)
    resp = await client.post("/api/auth/login", json={
        "email": "lockout@example.com",
        "password": "testpass123",  # even correct password
    })
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_login_lockout_clears_on_success(client):
    """Successful login should reset failed attempt counter."""
    await client.post("/api/auth/register", json={
        "email": "clear@example.com",
        "password": "testpass123",
    })

    # 3 failed attempts (not enough to lock)
    for _ in range(3):
        await client.post("/api/auth/login", json={
            "email": "clear@example.com",
            "password": "wrongpassword1",
        })

    # Successful login resets counter
    resp = await client.post("/api/auth/login", json={
        "email": "clear@example.com",
        "password": "testpass123",
    })
    assert resp.status_code == 200

    # 3 more failures (total 3 again, not 6) — should not lock
    for _ in range(3):
        await client.post("/api/auth/login", json={
            "email": "clear@example.com",
            "password": "wrongpassword1",
        })
    resp = await client.post("/api/auth/login", json={
        "email": "clear@example.com",
        "password": "testpass123",
    })
    assert resp.status_code == 200


# --- Waitlist Dedup ---

@pytest.mark.asyncio
async def test_waitlist_dedup(client):
    """Same email should not create duplicate waitlist entries."""
    resp1 = await client.post("/api/waitlist", json={"email": "dup@example.com"})
    assert resp1.status_code == 201

    resp2 = await client.post("/api/waitlist", json={"email": "dup@example.com"})
    assert resp2.status_code == 201  # Idempotent, no error

    # Verify only one entry via admin
    from backend.services.admin_store import list_waitlist
    items, total = await list_waitlist()
    emails = [i["email"] for i in items]
    assert emails.count("dup@example.com") == 1


# --- Admin Delete Waitlist ---

@pytest.mark.asyncio
async def test_admin_delete_waitlist_entry(admin_client, client):
    """Admin should be able to delete a waitlist entry."""
    # Add a waitlist entry
    await client.post("/api/waitlist", json={"email": "removeme@example.com"})

    # List waitlist to get the ID
    resp = await admin_client.get("/api/admin/waitlist")
    items = resp.json()["items"]
    entry = next(i for i in items if i["email"] == "removeme@example.com")

    # Delete it
    resp = await admin_client.delete(f"/api/admin/waitlist/{entry['id']}")
    assert resp.status_code == 200

    # Verify it's gone
    resp = await admin_client.get("/api/admin/waitlist")
    emails = [i["email"] for i in resp.json()["items"]]
    assert "removeme@example.com" not in emails


@pytest.mark.asyncio
async def test_admin_delete_waitlist_not_found(admin_client):
    """Deleting a nonexistent waitlist entry should return 404."""
    resp = await admin_client.delete("/api/admin/waitlist/99999")
    assert resp.status_code == 404


# --- Admin Delete User ---

@pytest.mark.asyncio
async def test_admin_delete_user(admin_client, client):
    """Admin should be able to delete a regular user."""
    # Register a user to delete
    resp = await client.post("/api/auth/register", json={
        "email": "victim@example.com",
        "password": "testpass123",
    })
    user_id = resp.json()["user"]["id"]

    # Admin deletes the user
    resp = await admin_client.delete(f"/api/admin/users/{user_id}")
    assert resp.status_code == 200

    # Verify user is gone
    resp = await admin_client.get("/api/admin/users")
    emails = [u["email"] for u in resp.json()["items"]]
    assert "victim@example.com" not in emails


# --- GDPR Data Export ---

@pytest.mark.asyncio
async def test_gdpr_export(auth_client):
    """Users should be able to export all their data."""
    # Create some data
    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]
    await auth_client.post("/api/jobs", json={"lotId": lot_id, "date": "2026-04-01"})

    # Export
    resp = await auth_client.get("/api/user/export")
    assert resp.status_code == 200
    data = resp.json()

    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert len(data["lots"]) == 1
    assert len(data["jobs"]) == 1
    assert "subscriptions" in data


@pytest.mark.asyncio
async def test_gdpr_export_unauthenticated(client):
    """Unauthenticated users should not be able to export data."""
    resp = await client.get("/api/user/export")
    assert resp.status_code == 401


# --- Audit Log ---

@pytest.mark.asyncio
async def test_audit_log_records_plan_change(admin_client, client):
    """Changing a user's plan should create an audit log entry."""
    # Create a user
    resp = await client.post("/api/auth/register", json={
        "email": "audit@example.com",
        "password": "testpass123",
    })
    user_id = resp.json()["user"]["id"]

    # Change their plan
    await admin_client.put(f"/api/admin/users/{user_id}/plan", json={"plan": "pro"})

    # Check audit log
    resp = await admin_client.get("/api/admin/audit-log")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["action"] == "set_plan"
    assert items[0]["target"] == user_id
    assert items[0]["detail"] == "pro"


@pytest.mark.asyncio
async def test_audit_log_records_user_deletion(admin_client, client):
    """Deleting a user should create an audit log entry."""
    resp = await client.post("/api/auth/register", json={
        "email": "todelete@example.com",
        "password": "testpass123",
    })
    user_id = resp.json()["user"]["id"]

    await admin_client.delete(f"/api/admin/users/{user_id}")

    resp = await admin_client.get("/api/admin/audit-log")
    items = resp.json()["items"]
    delete_entries = [i for i in items if i["action"] == "delete_user"]
    assert len(delete_entries) >= 1
    assert delete_entries[0]["target"] == user_id


@pytest.mark.asyncio
async def test_audit_log_unauthenticated(client):
    """Non-admins should not access the audit log."""
    resp = await client.get("/api/admin/audit-log")
    assert resp.status_code in (401, 403)


# --- Settings Profile Update with Email ---

@pytest.mark.asyncio
async def test_update_profile_email(auth_client):
    """User should be able to change their email."""
    resp = await auth_client.put("/api/user/profile", json={
        "email": "newemail@example.com",
        "name": "New Name",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "newemail@example.com"


@pytest.mark.asyncio
async def test_update_profile_email_conflict(auth_client, client):
    """Changing to an email already in use should fail."""
    # Register another user
    await client.post("/api/auth/register", json={
        "email": "taken@example.com",
        "password": "testpass123",
    })

    # Try to change to that email
    resp = await auth_client.put("/api/user/profile", json={
        "email": "taken@example.com",
    })
    assert resp.status_code == 409


# --- Active Lot Ownership Validation ---

@pytest.mark.asyncio
async def test_set_active_lot_must_be_owned(client):
    """Setting active_lot_id to a non-owned lot should fail."""
    # Register user A
    resp = await client.post("/api/auth/register", json={
        "email": "usera@example.com",
        "password": "testpass123",
    })
    token_a = resp.json()["token"]

    # Register user B and create a lot
    resp = await client.post("/api/auth/register", json={
        "email": "userb@example.com",
        "password": "testpass123",
    })
    token_b = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token_b}"
    lot_resp = await client.post("/api/lots", json=LOT_DATA)
    other_lot_id = lot_resp.json()["id"]

    # User A tries to set user B's lot as active
    client.headers["Authorization"] = f"Bearer {token_a}"
    resp = await client.put("/api/user/preferences", json={
        "active_lot_id": other_lot_id,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_active_lot_deleted_lot_rejected(auth_client):
    """Setting active_lot_id to a soft-deleted lot should fail."""
    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]

    # Delete the lot
    await auth_client.delete(f"/api/lots/{lot_id}")

    # Try to set deleted lot as active
    resp = await auth_client.put("/api/user/preferences", json={
        "active_lot_id": lot_id,
    })
    assert resp.status_code == 404


# --- Admin Plan Whitelist ---

@pytest.mark.asyncio
async def test_admin_set_invalid_plan_rejected(admin_client, client):
    """Admin should not be able to set an invalid plan."""
    resp = await client.post("/api/auth/register", json={
        "email": "plantest@example.com",
        "password": "testpass123",
    })
    user_id = resp.json()["user"]["id"]

    resp = await admin_client.put(f"/api/admin/users/{user_id}/plan", json={
        "plan": "superduper",
    })
    assert resp.status_code == 422


# --- Map State Validation ---

@pytest.mark.asyncio
async def test_map_state_invalid_zoom_rejected(auth_client):
    """Map state with invalid zoom should be rejected."""
    resp = await auth_client.put("/api/user/preferences", json={
        "map_state": {"lat": 40.0, "lng": -74.0, "zoom": 100},
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_map_state_invalid_lat_rejected(auth_client):
    """Map state with out-of-bounds lat should be rejected."""
    resp = await auth_client.put("/api/user/preferences", json={
        "map_state": {"lat": 100.0, "lng": -74.0, "zoom": 18},
    })
    assert resp.status_code == 422
