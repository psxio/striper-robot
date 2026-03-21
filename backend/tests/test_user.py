"""Tests for user profile, preferences, account deletion, and data export."""

import pytest


@pytest.mark.asyncio
async def test_update_profile_name(auth_client):
    """PUT /api/user/profile updates display name."""
    resp = await auth_client.put("/api/user/profile", json={"name": "Updated Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_profile_company_and_phone(auth_client):
    """PUT /api/user/profile with company_name and phone returns 200."""
    resp = await auth_client.put(
        "/api/user/profile",
        json={"company_name": "Acme Corp", "phone": "+15555550100"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_duplicate_email(auth_client, client):
    """PUT /api/user/profile rejects email already taken by another user."""
    await client.post("/api/auth/register", json={
        "email": "other@example.com",
        "password": "otherpass123",
        "name": "Other",
    })
    resp = await auth_client.put("/api/user/profile", json={"email": "other@example.com"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_preferences_map_state(auth_client):
    """PUT /api/user/preferences stores map_state."""
    resp = await auth_client.put(
        "/api/user/preferences",
        json={"map_state": {"zoom": 17, "lat": 40.7, "lng": -74.0}},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_preferences_invalid_lot(auth_client):
    """PUT /api/user/preferences rejects nonexistent active_lot_id."""
    resp = await auth_client.put(
        "/api/user/preferences",
        json={"active_lot_id": "nonexistent-lot-id"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_data_contains_user(auth_client):
    """GET /api/user/export returns JSON with user object."""
    resp = await auth_client.get("/api/user/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert "lots" in data
    assert "jobs" in data
    assert "subscriptions" in data
    assert "schedules" in data


@pytest.mark.asyncio
async def test_export_data_unauthenticated(client):
    """GET /api/user/export requires authentication."""
    resp = await client.get("/api/user/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_password(auth_client):
    """DELETE /api/user/account rejects wrong password."""
    resp = await auth_client.request(
        "DELETE", "/api/user/account", json={"password": "wrongpass"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_account_success(auth_client, client):
    """DELETE /api/user/account with correct password removes the account."""
    resp = await auth_client.request(
        "DELETE", "/api/user/account", json={"password": "testpass123"}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Subsequent login should fail
    login = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123",
    })
    assert login.status_code == 401
