"""Tests for auth refresh tokens and email verification."""

import pytest


# --- Helper ---

async def _register_and_login(client, email="refresh@example.com", password="testpass123"):
    """Register a user and log in, returning (login_response, access_token, refresh_cookie)."""
    await client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "name": "Refresh User",
    })
    resp = await client.post("/api/auth/login", json={
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200
    data = resp.json()
    access_token = data["token"]
    refresh_cookie = resp.cookies.get("refresh_token")
    return resp, access_token, refresh_cookie


def _csrf_headers(client) -> dict:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


# --- Refresh Token Tests ---

@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client):
    """Login should set a refresh_token httpOnly cookie."""
    _resp, _access, refresh_cookie = await _register_and_login(client)
    assert refresh_cookie is not None
    assert len(refresh_cookie) > 0


@pytest.mark.asyncio
async def test_refresh_issues_new_access_token(client):
    """POST /api/auth/refresh should return a new access token that works with /me."""
    _resp, _access, refresh_cookie = await _register_and_login(client)

    # Call refresh with the cookie
    client.cookies.set("refresh_token", refresh_cookie)
    refresh_resp = await client.post("/api/auth/refresh", headers=_csrf_headers(client))
    assert refresh_resp.status_code == 200

    new_token = refresh_resp.json()["token"]
    assert new_token is not None
    assert len(new_token) > 0

    # Verify the new token works
    client.headers["Authorization"] = f"Bearer {new_token}"
    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "refresh@example.com"


@pytest.mark.asyncio
async def test_refresh_rotates_token(client):
    """After refresh, the old refresh token should be invalid (rotation)."""
    _resp, _access, old_refresh = await _register_and_login(client)

    # Use the refresh token
    client.cookies.set("refresh_token", old_refresh)
    refresh_resp = await client.post("/api/auth/refresh", headers=_csrf_headers(client))
    assert refresh_resp.status_code == 200

    # Extract the rotated (new) refresh cookie
    new_refresh = refresh_resp.cookies.get("refresh_token")
    assert new_refresh is not None
    assert new_refresh != old_refresh

    # Old token should now be invalid
    client.cookies.set("refresh_token", old_refresh)
    resp2 = await client.post("/api/auth/refresh", headers=_csrf_headers(client))
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client):
    """An invalid/expired refresh token should return 401."""
    client.cookies.set("refresh_token", "totally-bogus-token-value")
    client.cookies.set("csrf_token", "refresh-csrf")
    resp = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": "refresh-csrf"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    """POST /api/auth/refresh with no refresh_token cookie should return 401."""
    client.cookies.set("csrf_token", "refresh-csrf")
    resp = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": "refresh-csrf"})
    assert resp.status_code == 401
    assert "no refresh token" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(client):
    """After logout, the refresh token should no longer work."""
    _resp, access_token, refresh_cookie = await _register_and_login(client)

    # Logout with the access token
    client.headers["Authorization"] = f"Bearer {access_token}"
    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # Try to refresh with the old cookie — should fail
    client.headers.pop("Authorization", None)
    client.cookies.set("refresh_token", refresh_cookie)
    resp = await client.post("/api/auth/refresh", headers=_csrf_headers(client))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_requires_csrf_header_when_cookie_present(client):
    """Cookie-authenticated refresh requests must include the matching CSRF header."""
    _resp, _access, refresh_cookie = await _register_and_login(client)
    client.cookies.set("refresh_token", refresh_cookie)

    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 403
    assert "csrf" in resp.json()["detail"].lower()


# --- Email Verification Tests ---

@pytest.mark.asyncio
async def test_verify_email_with_valid_token(client):
    """Email verification with a valid token should succeed and mark user as verified."""
    resp = await client.post("/api/auth/register", json={
        "email": "verify@example.com",
        "password": "testpass123",
        "name": "Verify User",
    })
    user_id = resp.json()["user"]["id"]
    token = resp.json()["token"]

    # Create a verification token via the store directly
    from backend.services.user_store import create_verification_token, get_user_by_id
    v_token = await create_verification_token(user_id)

    # Verify the email
    resp = await client.post("/api/auth/verify-email", json={"token": v_token})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Confirm the user is now verified in the database
    user = await get_user_by_id(user_id)
    assert user["email_verified"] == 1


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(client):
    """Email verification with an invalid token should return 400."""
    resp = await client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resend_verification_returns_token_in_dev(client):
    """Resend verification should return a new token in dev mode."""
    resp = await client.post("/api/auth/register", json={
        "email": "resend@example.com",
        "password": "testpass123",
        "name": "Resend User",
    })
    access_token = resp.json()["token"]

    # Request resend (user is not yet verified)
    client.headers["Authorization"] = f"Bearer {access_token}"
    resp = await client.post("/api/auth/resend-verification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    # In dev mode the token is returned in the response
    assert "token" in data
    assert len(data["token"]) > 0


@pytest.mark.asyncio
async def test_resend_verification_fails_if_already_verified(client):
    """Resend verification should return 400 if email is already verified."""
    resp = await client.post("/api/auth/register", json={
        "email": "already@example.com",
        "password": "testpass123",
        "name": "Already Verified",
    })
    access_token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]

    # Manually verify the user
    from backend.services.user_store import create_verification_token, verify_email_token
    v_token = await create_verification_token(user_id)
    await verify_email_token(v_token)

    # Try to resend — should fail
    client.headers["Authorization"] = f"Bearer {access_token}"
    resp = await client.post("/api/auth/resend-verification")
    assert resp.status_code == 400
    assert "already verified" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_me_returns_email_verified_field(client):
    """GET /api/auth/me should include email_verified field, toggling after verification."""
    # Register
    resp = await client.post("/api/auth/register", json={
        "email": "verify@example.com", "password": "testpass123", "name": "Test",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    # Check email_verified is false
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email_verified"] is False

    # Verify email directly
    from backend.services.user_store import create_verification_token, verify_email_token
    user_id = resp.json()["id"]
    vtoken = await create_verification_token(user_id)
    await verify_email_token(vtoken)

    # Check email_verified is now true
    resp = await client.get("/api/auth/me")
    assert resp.json()["email_verified"] is True
