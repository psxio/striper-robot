"""Tests for fleet management: maintenance events, service checklists, consumables."""

import pytest


LOT_DATA = {
    "name": "Fleet Test Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [],
}


async def _setup_org_and_robot(auth_client):
    """Return (org_id_header, robot_id) for fleet tests."""
    me = (await auth_client.get("/api/auth/me")).json()
    org_id = me["active_organization_id"]
    headers = {"X-Organization-ID": org_id}
    from backend.services.robot_store import create_robot, create_robot_claim, claim_robot_for_organization
    robot = await create_robot("FLT-001", firmware_version="2026.1.0")
    claim, code = await create_robot_claim(robot["id"], me["id"])
    await claim_robot_for_organization(code, org_id, me["id"], friendly_name="Fleet test robot")
    return headers, robot["id"]


@pytest.mark.asyncio
async def test_list_robots_empty(auth_client):
    """GET /api/fleet/robots returns empty list when no robots assigned."""
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}
    resp = await auth_client.get("/api/fleet/robots", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_and_list_maintenance_events(auth_client):
    """POST /api/fleet/maintenance-events creates event; GET lists it."""
    headers, robot_id = await _setup_org_and_robot(auth_client)

    create_resp = await auth_client.post(
        "/api/fleet/maintenance-events",
        headers=headers,
        json={
            "robot_id": robot_id,
            "event_type": "inspection",
            "summary": "Routine 100-hour service",
            "details": "100 hours logged; all systems nominal",
        },
    )
    assert create_resp.status_code == 201
    event = create_resp.json()
    assert event["robot_id"] == robot_id
    assert event["event_type"] == "inspection"

    list_resp = await auth_client.get(
        "/api/fleet/maintenance-events",
        headers=headers,
        params={"robot_id": robot_id},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_and_list_service_checklists(auth_client):
    """POST /api/fleet/service-checklists creates checklist; GET lists it."""
    headers, robot_id = await _setup_org_and_robot(auth_client)

    create_resp = await auth_client.post(
        "/api/fleet/service-checklists",
        headers=headers,
        json={
            "robot_id": robot_id,
            "name": "Pre-mission safety check",
            "checklist_items": ["Battery > 80%", "Motor test"],
        },
    )
    assert create_resp.status_code == 201
    checklist = create_resp.json()
    assert checklist["name"] == "Pre-mission safety check"

    list_resp = await auth_client.get(
        "/api/fleet/service-checklists",
        headers=headers,
        params={"robot_id": robot_id},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_and_list_consumables(auth_client):
    """POST /api/fleet/consumables creates item; GET lists it."""
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    create_resp = await auth_client.post(
        "/api/fleet/consumables",
        headers=headers,
        json={
            "sku": "PAINT-WHT-1G",
            "name": "White Line Paint 1 Gallon",
            "unit": "gallon",
            "on_hand": 10,
            "reorder_level": 2,
        },
    )
    assert create_resp.status_code == 201
    item = create_resp.json()
    assert item["sku"] == "PAINT-WHT-1G"
    assert item["on_hand"] == 10

    list_resp = await auth_client.get("/api/fleet/consumables", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_update_consumable(auth_client):
    """PATCH /api/fleet/consumables/{id} updates on_hand quantity."""
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    item = (
        await auth_client.post(
            "/api/fleet/consumables",
            headers=headers,
            json={"sku": "PAINT-YLW", "name": "Yellow Paint", "unit": "gallon", "on_hand": 5, "reorder_level": 1},
        )
    ).json()

    patch_resp = await auth_client.patch(
        f"/api/fleet/consumables/{item['id']}",
        headers=headers,
        json={"on_hand": 8},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["on_hand"] == 8


@pytest.mark.asyncio
async def test_fleet_requires_auth(client):
    """Fleet endpoints require authentication."""
    resp = await client.get("/api/fleet/consumables")
    assert resp.status_code == 401
