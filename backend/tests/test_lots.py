"""Tests for lot management endpoints."""

import pytest

from backend.services.billing_store import set_user_plan


LOT_DATA = {
    "name": "Test Parking Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [{"type": "line", "coords": [[0, 0], [1, 1]]}],
}


@pytest.mark.asyncio
async def test_create_lot(auth_client):
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Parking Lot"
    assert data["center"]["lat"] == 40.7128
    assert data["center"]["lng"] == -74.0060
    assert data["zoom"] == 19
    assert len(data["features"]) == 1
    assert "id" in data
    assert "created" in data
    assert "modified" in data


@pytest.mark.asyncio
async def test_list_lots(auth_client):
    # Upgrade to pro so we can create multiple lots
    me = await auth_client.get("/api/auth/me")
    await set_user_plan(me.json()["id"], "pro")

    await auth_client.post("/api/lots", json=LOT_DATA)
    await auth_client.post("/api/lots", json={
        "name": "Second Lot",
        "center": {"lat": 41.0, "lng": -75.0},
    })
    resp = await auth_client.get("/api/lots")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["limit"] == 50


@pytest.mark.asyncio
async def test_get_lot(auth_client):
    create_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/lots/{lot_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lot_id
    assert resp.json()["name"] == "Test Parking Lot"


@pytest.mark.asyncio
async def test_get_lot_not_found(auth_client):
    resp = await auth_client.get("/api/lots/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_lot(auth_client):
    create_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]
    resp = await auth_client.put(f"/api/lots/{lot_id}", json={
        "name": "Renamed Lot",
        "zoom": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed Lot"
    assert data["zoom"] == 20
    # Center should be unchanged
    assert data["center"]["lat"] == 40.7128


@pytest.mark.asyncio
async def test_update_lot_features(auth_client):
    """Verify features JSON round-trip through update."""
    create_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]
    new_features = [
        {"type": "polygon", "coords": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"type": "line", "coords": [[2, 2], [3, 3]]},
    ]
    resp = await auth_client.put(f"/api/lots/{lot_id}", json={
        "features": new_features,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) == 2
    assert data["features"][0]["type"] == "polygon"
    assert data["features"][1]["type"] == "line"


@pytest.mark.asyncio
async def test_delete_lot(auth_client):
    create_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/api/lots/{lot_id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Verify it's gone
    resp = await auth_client.get(f"/api/lots/{lot_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_lot(pro_client):
    create_resp = await pro_client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]
    resp = await pro_client.post(f"/api/lots/{lot_id}/duplicate")
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Parking Lot (Copy)"
    assert data["id"] != lot_id
    assert data["center"]["lat"] == 40.7128
    assert data["features"] == LOT_DATA["features"]


@pytest.mark.asyncio
async def test_lot_isolation(client):
    """Verify that one user cannot access another user's lots."""
    # Register user 1
    resp1 = await client.post("/api/auth/register", json={
        "email": "user1@example.com",
        "password": "password123",
    })
    token1 = resp1.json()["token"]

    # Register user 2
    resp2 = await client.post("/api/auth/register", json={
        "email": "user2@example.com",
        "password": "password123",
    })
    token2 = resp2.json()["token"]

    # User 1 creates a lot
    client.headers["Authorization"] = f"Bearer {token1}"
    create_resp = await client.post("/api/lots", json=LOT_DATA)
    lot_id = create_resp.json()["id"]

    # User 2 should NOT see it
    client.headers["Authorization"] = f"Bearer {token2}"
    resp = await client.get(f"/api/lots/{lot_id}")
    assert resp.status_code == 404

    # User 2's list should be empty
    resp = await client.get("/api/lots")
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_lot_search(auth_client):
    """Search lots by name."""
    me = await auth_client.get("/api/auth/me")
    await set_user_plan(me.json()["id"], "pro")

    await auth_client.post("/api/lots", json={
        "name": "Alpha Parking",
        "center": {"lat": 40.0, "lng": -74.0},
    })
    await auth_client.post("/api/lots", json={
        "name": "Beta Garage",
        "center": {"lat": 41.0, "lng": -75.0},
    })

    # Search for "Alpha" -> 1 result
    resp = await auth_client.get("/api/lots?search=Alpha")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Alpha Parking"

    # Search with no match -> 0
    resp = await auth_client.get("/api/lots?search=Gamma")
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_unauthorized(client):
    resp = await client.get("/api/lots")
    assert resp.status_code == 401
