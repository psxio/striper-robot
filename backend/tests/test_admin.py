"""Tests for Phase 5: Admin Dashboard."""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_non_admin_forbidden(auth_client):
    """Non-admin user gets 403 on admin endpoints."""
    resp = await auth_client.get("/api/admin/stats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stats(admin_client):
    """Admin can get platform stats."""
    resp = await admin_client.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "lots" in data
    assert "jobs" in data
    assert "waitlist" in data
    assert "users_by_plan" in data
    assert data["users"] >= 1  # At least the admin user


@pytest.mark.asyncio
async def test_list_users(admin_client):
    """Admin can list users."""
    resp = await admin_client.get("/api/admin/users")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    user = data["items"][0]
    assert "email" in user
    assert "lot_count" in user
    assert "job_count" in user


@pytest.mark.asyncio
async def test_list_waitlist(admin_client, client):
    """Admin can list waitlist entries."""
    # Add a waitlist entry (use a separate unauthenticated request)
    transport = client._transport
    from httpx import AsyncClient
    async with AsyncClient(transport=transport, base_url="http://test") as unauth:
        await unauth.post("/api/waitlist", json={
            "email": "interested@example.com",
        })

    resp = await admin_client.get("/api/admin/waitlist")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_change_user_plan(admin_client, client):
    """Admin can change a user's plan."""
    # Create a regular user
    del admin_client.headers["Authorization"]
    resp = await admin_client.post("/api/auth/register", json={
        "email": "regular@example.com",
        "password": "password123",
    })
    user_id = resp.json()["user"]["id"]
    user_token = resp.json()["token"]

    # Re-auth as admin
    resp = await admin_client.post("/api/auth/login", json={
        "email": "admin@example.com",
        "password": "adminpass123",
    })
    admin_client.headers["Authorization"] = f"Bearer {resp.json()['token']}"

    # Change plan
    resp = await admin_client.put(f"/api/admin/users/{user_id}/plan", json={
        "plan": "pro",
    })
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"

    # Verify user sees the change
    admin_client.headers["Authorization"] = f"Bearer {user_token}"
    resp = await admin_client.get("/api/auth/me")
    assert resp.json()["plan"] == "pro"


@pytest.mark.asyncio
async def test_waitlist_csv_export(admin_client, client):
    """Admin can export waitlist as CSV."""
    # Add a waitlist entry
    transport = client._transport
    from httpx import AsyncClient
    async with AsyncClient(transport=transport, base_url="http://test") as unauth:
        await unauth.post("/api/waitlist", json={
            "email": "csv@example.com",
        })

    resp = await admin_client.get("/api/admin/waitlist?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "email" in resp.text
