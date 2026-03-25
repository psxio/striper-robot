import pytest

from backend.database import get_db
from backend.services import robot_store
from backend.services.scheduler import process_due_schedules


LOT_WITH_LINES = {
    "name": "Cloud Ops Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [
        {
            "type": "Feature",
            "properties": {"kind": "stripe"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0060, 40.7128],
                    [-74.0058, 40.7128],
                ],
            },
        }
    ],
}


async def _setup_site(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}
    lot_resp = await auth_client.post("/api/lots", json=LOT_WITH_LINES)
    assert lot_resp.status_code == 201
    site_resp = await auth_client.get("/api/sites", headers=headers)
    site = site_resp.json()["items"][0]
    return me, headers, site


async def _claim_robot_for_org(robot_id: str, me: dict):
    claim, code = await robot_store.create_robot_claim(robot_id, me["id"])
    await robot_store.claim_robot_for_organization(code, me["active_organization_id"], me["id"])


@pytest.mark.asyncio
async def test_site_scan_and_simulation_flow(auth_client):
    me, headers, site = await _setup_site(auth_client)

    scan_resp = await auth_client.post(
        "/api/site-scans",
        headers=headers,
        json={"site_id": site["id"], "scan_type": "manual_trace", "notes": "Initial cloud scan"},
    )
    assert scan_resp.status_code == 201
    scan = scan_resp.json()
    assert scan["summary"]["feature_count"] == 1
    assert scan["summary"]["total_line_length_ft"] > 0

    robot = await robot_store.create_robot("SIM-001", firmware_version="2026.03")
    await _claim_robot_for_org(robot["id"], me)
    sim_resp = await auth_client.post(
        "/api/site-simulations",
        headers=headers,
        json={
            "site_id": site["id"],
            "scan_id": scan["id"],
            "robot_id": robot["id"],
            "mode": "mission_rehearsal",
            "speed_mph": 2.4,
        },
    )
    assert sim_resp.status_code == 201
    simulation = sim_resp.json()
    assert simulation["result"]["route_distance_ft"] >= scan["summary"]["total_line_length_ft"]
    assert simulation["result"]["estimated_runtime_min"] > 0


@pytest.mark.asyncio
async def test_scheduler_generates_org_scoped_work_order(auth_client):
    me, headers, site = await _setup_site(auth_client)

    create_resp = await auth_client.post(
        "/api/schedules/organization",
        headers=headers,
        json={"lot_id": site["lot_id"], "frequency": "weekly", "day_of_week": 0, "time_preference": "morning"},
    )
    assert create_resp.status_code == 201
    schedule = create_resp.json()

    async for db in get_db():
        await db.execute(
            "UPDATE recurring_schedules SET next_run = '2026-01-01' WHERE id = ?",
            (schedule["id"],),
        )
        await db.commit()
        break

    processed = await process_due_schedules()
    assert processed == 1

    work_orders = (await auth_client.get("/api/work-orders", headers=headers)).json()["items"]
    assert len(work_orders) == 1
    assert work_orders[0]["site_id"] == site["id"]
    async for db in get_db():
        cursor = await db.execute(
            "SELECT recurring_schedule_id, organization_id FROM jobs WHERE id = ?",
            (work_orders[0]["id"],),
        )
        row = await cursor.fetchone()
        assert row["recurring_schedule_id"] == schedule["id"]
        assert row["organization_id"] == me["active_organization_id"]
        break


@pytest.mark.asyncio
async def test_work_order_rejects_robot_not_ready(auth_client):
    me, headers, site = await _setup_site(auth_client)
    robot = await robot_store.create_robot("MAINT-001", firmware_version="2026.03")
    await _claim_robot_for_org(robot["id"], me)
    await robot_store.update_robot(robot["id"], maintenance_status="inspection_due")

    resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "Needs robot",
            "date": "2026-06-01",
            "status": "scheduled",
            "assigned_robot_id": robot["id"],
        },
    )
    assert resp.status_code == 400
    assert "dispatch-ready" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_work_order_rejects_robot_double_booking(auth_client):
    me, headers, site = await _setup_site(auth_client)
    robot = await robot_store.create_robot("BOOK-001", firmware_version="2026.03")
    await _claim_robot_for_org(robot["id"], me)

    first = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "Morning dispatch",
            "date": "2026-06-01",
            "status": "assigned",
            "assigned_robot_id": robot["id"],
        },
    )
    assert first.status_code == 201

    second = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "Second dispatch",
            "date": "2026-06-01",
            "status": "assigned",
            "assigned_robot_id": robot["id"],
        },
    )
    assert second.status_code == 409
