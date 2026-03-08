"""Tests for recurring schedule management endpoints."""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def pro_lot_id(pro_client):
    """Create a lot under the pro user and return its ID."""
    resp = await pro_client.post("/api/lots", json={
        "name": "Schedule Test Lot",
        "center": {"lat": 40.0, "lng": -74.0},
        "features": [],
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# -- 1. Create schedule (pro) --

@pytest.mark.asyncio
async def test_create_schedule_pro(pro_client, pro_lot_id):
    """Pro user can create a recurring schedule (201) with frequency and next_run."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["frequency"] == "weekly"
    assert data["day_of_week"] == 1
    assert data["time_preference"] == "morning"
    assert data["active"] is True
    assert "next_run" in data
    assert "id" in data


# -- 2. Free plan rejected --

@pytest.mark.asyncio
async def test_create_schedule_free_rejected(auth_client):
    """Free-plan user cannot create a schedule (403)."""
    # auth_client is free plan; create a lot first (free users can create lots)
    lot_resp = await auth_client.post("/api/lots", json={
        "name": "Free Lot",
        "center": {"lat": 40.0, "lng": -74.0},
        "features": [],
    })
    lot_id = lot_resp.json()["id"]

    resp = await auth_client.post("/api/schedules", json={
        "lot_id": lot_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    assert resp.status_code == 403
    assert "Pro" in resp.json()["detail"]


# -- 3. List schedules --

@pytest.mark.asyncio
async def test_list_schedules(pro_client, pro_lot_id):
    """Creating two schedules then listing returns items with total=2."""
    await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "monthly",
        "day_of_month": 15,
        "time_preference": "afternoon",
    })

    resp = await pro_client.get("/api/schedules")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


# -- 4. Weekly schedule --

@pytest.mark.asyncio
async def test_create_schedule_weekly(pro_client, pro_lot_id):
    """Weekly schedule with day_of_week=1 is valid."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    assert resp.status_code == 201
    assert resp.json()["frequency"] == "weekly"
    assert resp.json()["day_of_week"] == 1


# -- 5. Monthly schedule --

@pytest.mark.asyncio
async def test_create_schedule_monthly(pro_client, pro_lot_id):
    """Monthly schedule with day_of_month=15 is valid."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "monthly",
        "day_of_month": 15,
        "time_preference": "evening",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["frequency"] == "monthly"
    assert data["day_of_month"] == 15
    assert data["time_preference"] == "evening"


# -- 6. Biweekly schedule --

@pytest.mark.asyncio
async def test_create_schedule_biweekly(pro_client, pro_lot_id):
    """Biweekly schedule with day_of_week=3 is valid."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "biweekly",
        "day_of_week": 3,
        "time_preference": "afternoon",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["frequency"] == "biweekly"
    assert data["day_of_week"] == 3


# -- 7. Update schedule --

@pytest.mark.asyncio
async def test_update_schedule(pro_client, pro_lot_id):
    """Updating frequency via PUT changes the schedule."""
    create_resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    schedule_id = create_resp.json()["id"]

    resp = await pro_client.put(f"/api/schedules/{schedule_id}", json={
        "frequency": "monthly",
        "day_of_month": 20,
        "time_preference": "evening",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["frequency"] == "monthly"
    assert data["day_of_month"] == 20
    assert data["time_preference"] == "evening"


# -- 8. Delete schedule --

@pytest.mark.asyncio
async def test_delete_schedule(pro_client, pro_lot_id):
    """Deleting a schedule returns 200 and the schedule disappears from listing."""
    create_resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 4,
        "time_preference": "morning",
    })
    schedule_id = create_resp.json()["id"]

    resp = await pro_client.delete(f"/api/schedules/{schedule_id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Verify it is no longer listed (soft-deleted, active=0)
    list_resp = await pro_client.get("/api/schedules")
    assert list_resp.json()["total"] == 0
    assert list_resp.json()["items"] == []


# -- 9. Invalid frequency --

@pytest.mark.asyncio
async def test_schedule_invalid_frequency(pro_client, pro_lot_id):
    """An unsupported frequency like 'daily' returns 422."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "daily",
        "day_of_week": 1,
        "time_preference": "morning",
    })
    assert resp.status_code == 422


# -- 10. Invalid lot --

@pytest.mark.asyncio
async def test_schedule_invalid_lot(pro_client):
    """Using a non-existent lot_id returns 404."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": "00000000-0000-0000-0000-000000000000",
        "frequency": "weekly",
        "day_of_week": 2,
        "time_preference": "morning",
    })
    assert resp.status_code == 404
    assert "Lot not found" in resp.json()["detail"]


# -- 11. Ownership isolation --

@pytest.mark.asyncio
async def test_schedule_ownership(client):
    """Another user cannot update or delete a schedule they do not own."""
    from backend.services.billing_store import set_user_plan

    # Register user 1 (pro) and create a lot + schedule
    resp1 = await client.post("/api/auth/register", json={
        "email": "owner@example.com",
        "password": "password123",
    })
    token1 = resp1.json()["token"]
    user1_id = resp1.json()["user"]["id"]
    await set_user_plan(user1_id, "pro")
    client.headers["Authorization"] = f"Bearer {token1}"

    lot_resp = await client.post("/api/lots", json={
        "name": "Owner Lot",
        "center": {"lat": 40.0, "lng": -74.0},
        "features": [],
    })
    lot_id = lot_resp.json()["id"]

    create_resp = await client.post("/api/schedules", json={
        "lot_id": lot_id,
        "frequency": "weekly",
        "day_of_week": 0,
        "time_preference": "morning",
    })
    assert create_resp.status_code == 201
    schedule_id = create_resp.json()["id"]

    # Register user 2 (different user)
    del client.headers["Authorization"]
    resp2 = await client.post("/api/auth/register", json={
        "email": "other@example.com",
        "password": "password123",
    })
    token2 = resp2.json()["token"]
    client.headers["Authorization"] = f"Bearer {token2}"

    # User 2 tries to update user 1's schedule
    resp = await client.put(f"/api/schedules/{schedule_id}", json={
        "frequency": "monthly",
        "day_of_month": 10,
    })
    assert resp.status_code == 404

    # User 2 tries to delete user 1's schedule
    resp = await client.delete(f"/api/schedules/{schedule_id}")
    assert resp.status_code == 404

    # User 2 should see no schedules when listing
    resp = await client.get("/api/schedules")
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


# -- 12. Update nonexistent schedule --

@pytest.mark.asyncio
async def test_update_nonexistent_schedule(pro_client):
    """PUT on a fake schedule ID returns 404."""
    resp = await pro_client.put(
        "/api/schedules/00000000-0000-0000-0000-000000000000",
        json={"frequency": "monthly", "day_of_month": 5},
    )
    assert resp.status_code == 404
    assert "Schedule not found" in resp.json()["detail"]


# -- 13. Delete nonexistent schedule --

@pytest.mark.asyncio
async def test_delete_nonexistent_schedule(pro_client):
    """DELETE on a fake schedule ID returns 404."""
    resp = await pro_client.delete(
        "/api/schedules/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
    assert "Schedule not found" in resp.json()["detail"]


# -- 14. Response shape --

@pytest.mark.asyncio
async def test_schedule_response_shape(pro_client, pro_lot_id):
    """Verify every expected field is present in the schedule response."""
    resp = await pro_client.post("/api/schedules", json={
        "lot_id": pro_lot_id,
        "frequency": "weekly",
        "day_of_week": 5,
        "time_preference": "afternoon",
    })
    assert resp.status_code == 201
    data = resp.json()

    expected_keys = {
        "id", "lot_id", "frequency", "day_of_week", "day_of_month",
        "time_preference", "active", "next_run", "created_at", "updated_at",
    }
    assert expected_keys == set(data.keys()), (
        f"Missing: {expected_keys - set(data.keys())}, "
        f"Extra: {set(data.keys()) - expected_keys}"
    )

    # Sanity-check types
    assert isinstance(data["id"], str)
    assert isinstance(data["lot_id"], str)
    assert isinstance(data["active"], bool)
    assert isinstance(data["next_run"], str)
    assert isinstance(data["created_at"], str)
    assert isinstance(data["updated_at"], str)


# -- 15. Pagination --

@pytest.mark.asyncio
async def test_schedule_pagination(pro_client, pro_lot_id):
    """Create several schedules and verify page/limit params work."""
    # Create 5 schedules (all weekly, different days)
    for day in range(5):
        resp = await pro_client.post("/api/schedules", json={
            "lot_id": pro_lot_id,
            "frequency": "weekly",
            "day_of_week": day,
            "time_preference": "morning",
        })
        assert resp.status_code == 201

    # Page 1, limit 2
    resp = await pro_client.get("/api/schedules?page=1&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["limit"] == 2

    # Page 2, limit 2
    resp = await pro_client.get("/api/schedules?page=2&limit=2")
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 2

    # Page 3, limit 2 (only 1 remaining)
    resp = await pro_client.get("/api/schedules?page=3&limit=2")
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 5
    assert data["page"] == 3
