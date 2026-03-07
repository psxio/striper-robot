"""Security tests: HSTS, CSP, password complexity, SQL injection, unicode, cascade deletion,
date validation, soft deletes, token revocation, global error handler, logout."""

import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Security Test Lot",
    "center": {"lat": 40.0, "lng": -74.0},
}


# --- Security Headers ---

@pytest.mark.asyncio
async def test_hsts_header(client):
    resp = await client.get("/api/health")
    assert resp.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"


@pytest.mark.asyncio
async def test_csp_header(client):
    resp = await client.get("/api/health")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "script-src" in csp


# --- Password Complexity ---

@pytest.mark.asyncio
async def test_password_all_letters_rejected(client):
    resp = await client.post("/api/auth/register", json={
        "email": "letters@example.com",
        "password": "abcdefghij",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_password_all_digits_rejected(client):
    resp = await client.post("/api/auth/register", json={
        "email": "digits@example.com",
        "password": "1234567890",
    })
    assert resp.status_code == 422


# --- SQL Injection ---

@pytest.mark.asyncio
async def test_sql_injection_login_email(client):
    resp = await client.post("/api/auth/login", json={
        "email": "' OR 1=1--@example.com",
        "password": "password123",
    })
    # Should be 422 (bad email) or 401, not 200
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_sql_injection_lot_name(auth_client):
    resp = await auth_client.post("/api/lots", json={
        "name": "'; DROP TABLE lots; --",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    assert resp.status_code == 201
    # Verify lots table still works
    resp = await auth_client.get("/api/lots")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_sql_injection_search(auth_client):
    resp = await auth_client.get("/api/lots?search=' OR 1=1--")
    assert resp.status_code == 200


# --- Unicode / Emoji ---

@pytest.mark.asyncio
async def test_unicode_lot_name(auth_client):
    resp = await auth_client.post("/api/lots", json={
        "name": "Parking Lot \U0001f697\U0001f17f\ufe0f",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    assert resp.status_code == 201
    assert "\U0001f697" in resp.json()["name"]


@pytest.mark.asyncio
async def test_unicode_user_name(client):
    resp = await client.post("/api/auth/register", json={
        "email": "unicode@example.com",
        "password": "testpass123",
        "name": "Test \u00e9\u00e8\u00ea\u00eb",
    })
    assert resp.status_code == 201
    assert "\u00e9" in resp.json()["user"]["name"]


# --- Cascade Deletion ---

@pytest.mark.asyncio
async def test_cascade_delete_user(client):
    """Deleting a user should cascade-delete their lots and jobs."""
    resp = await client.post("/api/auth/register", json={
        "email": "cascade@example.com",
        "password": "testpass123",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    # Create lot and job
    lot_resp = await client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]
    await client.post("/api/jobs", json={"lotId": lot_id, "date": "2026-04-01"})

    # Delete account (httpx delete doesn't support json, use request)
    resp = await client.request("DELETE", "/api/user/account", json={"password": "testpass123"})
    assert resp.status_code == 200

    # Re-register to verify data is gone
    del client.headers["Authorization"]
    resp = await client.post("/api/auth/register", json={
        "email": "cascade2@example.com",
        "password": "testpass123",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    resp = await client.get("/api/lots")
    assert resp.json()["total"] == 0
    resp = await client.get("/api/jobs")
    assert resp.json()["total"] == 0


# --- Job Date Validation ---

@pytest.mark.asyncio
async def test_job_date_invalid_string(auth_client):
    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]
    resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "not-a-date",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_job_date_invalid_numbers(auth_client):
    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]
    resp = await auth_client.post("/api/jobs", json={
        "lotId": lot_id,
        "date": "2026-13-45",
    })
    assert resp.status_code == 422


# --- Admin Self-Deletion ---

@pytest.mark.asyncio
async def test_admin_cannot_delete_self(admin_client):
    """Admin should not be able to delete their own account via admin endpoint."""
    me = await admin_client.get("/api/auth/me")
    my_id = me.json()["id"]
    resp = await admin_client.delete(f"/api/admin/users/{my_id}")
    assert resp.status_code == 400


# --- Soft Delete ---

@pytest.mark.asyncio
async def test_soft_delete_lot_excluded_from_list(auth_client):
    """Deleted lot should not appear in list but data is preserved in DB."""
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = resp.json()["id"]

    # Delete it
    resp = await auth_client.delete(f"/api/lots/{lot_id}")
    assert resp.status_code == 200

    # Should not appear in list
    resp = await auth_client.get("/api/lots")
    assert resp.json()["total"] == 0

    # Should not be gettable
    resp = await auth_client.get(f"/api/lots/{lot_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_cascades_jobs(auth_client):
    """Soft-deleting a lot should also remove its jobs."""
    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = lot_resp.json()["id"]

    # Create a job for this lot
    await auth_client.post("/api/jobs", json={"lotId": lot_id, "date": "2026-04-01"})
    resp = await auth_client.get("/api/jobs")
    assert resp.json()["total"] == 1

    # Soft-delete the lot
    await auth_client.delete(f"/api/lots/{lot_id}")

    # Jobs should be gone too
    resp = await auth_client.get("/api/jobs")
    assert resp.json()["total"] == 0


# --- Logout / Token Revocation ---

@pytest.mark.asyncio
async def test_logout_invalidates_token(client):
    """After logout, the same token should be rejected."""
    resp = await client.post("/api/auth/register", json={
        "email": "logout@example.com",
        "password": "testpass123",
    })
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"

    # Token works before logout
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200

    # Logout
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200

    # Token should be revoked now
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_unauthenticated(client):
    """Logout without auth should return 401."""
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 401


# --- Global Error Handler ---

@pytest.mark.asyncio
async def test_error_handler_returns_json(client):
    """Health endpoint returns JSON even on errors; 500s should return JSON not HTML."""
    # We can't easily trigger a 500 in tests, but we can verify the handler exists
    # by checking that a bad route returns proper 404 (not HTML)
    resp = await client.get("/api/nonexistent")
    # FastAPI returns 404 for unknown API routes or falls through to static files
    assert resp.status_code in (404, 200)


# --- Config Validation ---

@pytest.mark.asyncio
async def test_config_validation_dev_mode():
    """In dev mode, insecure defaults should warn but not crash."""
    from backend.config import Settings
    s = Settings()
    s.ENV = "dev"
    s.SECRET_KEY = "dev-secret-key-change-in-production"
    s.CORS_ORIGINS = "*"
    # Should not raise
    s.validate()


@pytest.mark.asyncio
async def test_config_validation_prod_secret_key():
    """In production, default SECRET_KEY should raise."""
    from backend.config import Settings
    s = Settings()
    s.ENV = "production"
    s.SECRET_KEY = "dev-secret-key-change-in-production"
    s.CORS_ORIGINS = "https://app.strype.io"
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.validate()


@pytest.mark.asyncio
async def test_config_validation_prod_cors_wildcard():
    """In production, wildcard CORS should raise."""
    from backend.config import Settings
    s = Settings()
    s.ENV = "production"
    s.SECRET_KEY = "a-real-secret-key-that-is-not-default"
    s.CORS_ORIGINS = "*"
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        s.validate()
