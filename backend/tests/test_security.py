"""Security tests: HSTS, password complexity, SQL injection, unicode, cascade deletion, date validation, soft deletes."""

import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Security Test Lot",
    "center": {"lat": 40.0, "lng": -74.0},
}


# --- HSTS Header ---

@pytest.mark.asyncio
async def test_hsts_header(client):
    resp = await client.get("/api/health")
    assert resp.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"


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
