"""Tests for Phase 2: Account Management — password reset, change password, profile, delete account."""

import pytest


# --- Password Reset Flow ---

@pytest.mark.asyncio
async def test_forgot_reset_login(client):
    """Full password reset flow: forgot → reset → login with new password."""
    # Register
    await client.post("/api/auth/register", json={
        "email": "reset@example.com",
        "password": "oldpassword1",
    })

    # Forgot password (dev mode returns token)
    resp = await client.post("/api/auth/forgot-password", json={
        "email": "reset@example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "token" in data  # dev mode

    # Reset password
    resp = await client.post("/api/auth/reset-password", json={
        "token": data["token"],
        "new_password": "newpassword1",
    })
    assert resp.status_code == 200

    # Login with new password succeeds
    resp = await client.post("/api/auth/login", json={
        "email": "reset@example.com",
        "password": "newpassword1",
    })
    assert resp.status_code == 200

    # Login with old password fails
    resp = await client.post("/api/auth/login", json={
        "email": "reset@example.com",
        "password": "oldpassword1",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_forgot_nonexistent_email(client):
    """Forgot password for non-existent email still returns ok (no email leak)."""
    resp = await client.post("/api/auth/forgot-password", json={
        "email": "nobody@example.com",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # No token returned for non-existent email
    assert "token" not in resp.json()


@pytest.mark.asyncio
async def test_reset_invalid_token(client):
    resp = await client.post("/api/auth/reset-password", json={
        "token": "invalid-token",
        "new_password": "newpassword1",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_token_single_use(client):
    """Reset token can only be used once."""
    await client.post("/api/auth/register", json={
        "email": "single@example.com",
        "password": "password123",
    })
    resp = await client.post("/api/auth/forgot-password", json={
        "email": "single@example.com",
    })
    token = resp.json()["token"]

    # First use succeeds
    resp = await client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "newpassword1",
    })
    assert resp.status_code == 200

    # Second use fails
    resp = await client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "anotherpass1",
    })
    assert resp.status_code == 400


# --- Change Password ---

@pytest.mark.asyncio
async def test_change_password_success(auth_client):
    resp = await auth_client.put("/api/auth/password", json={
        "current_password": "testpass123",
        "new_password": "newpass1234",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_change_password_wrong_current(auth_client):
    resp = await auth_client.put("/api/auth/password", json={
        "current_password": "wrongpassword",
        "new_password": "newpass1234",
    })
    assert resp.status_code == 400


# --- Profile Update ---

@pytest.mark.asyncio
async def test_update_profile_name(auth_client):
    resp = await auth_client.put("/api/user/profile", json={
        "name": "New Name",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_profile_email(auth_client):
    resp = await auth_client.put("/api/user/profile", json={
        "email": "newemail@example.com",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "newemail@example.com"


@pytest.mark.asyncio
async def test_update_profile_duplicate_email(client):
    """Changing email to one that's already taken should fail."""
    await client.post("/api/auth/register", json={
        "email": "taken@example.com",
        "password": "password123",
    })
    resp = await client.post("/api/auth/register", json={
        "email": "me@example.com",
        "password": "password123",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    resp = await client.put("/api/user/profile", json={
        "email": "taken@example.com",
    })
    assert resp.status_code == 409


# --- Delete Account ---

@pytest.mark.asyncio
async def test_delete_account(auth_client):
    resp = await auth_client.request("DELETE", "/api/user/account", json={
        "password": "testpass123",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Subsequent requests should fail
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_password(auth_client):
    resp = await auth_client.request("DELETE", "/api/user/account", json={
        "password": "wrongpassword",
    })
    assert resp.status_code == 400
