"""Tests for organization-scoped commercial workflows."""

import pytest


LOT_DATA = {
    "name": "Portfolio Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [
        {
            "type": "Feature",
            "properties": {"width": 4, "color": "#ffffff"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-74.0060, 40.7128],
                    [-74.0058, 40.7129],
                ],
            },
        }
    ],
}


@pytest.mark.asyncio
async def test_site_quote_work_order_report_flow(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()
    org_id = me["active_organization_id"]
    headers = {"X-Organization-ID": org_id}

    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert lot_resp.status_code == 201

    sites_resp = await auth_client.get("/api/sites", headers=headers)
    assert sites_resp.status_code == 200
    assert sites_resp.json()["total"] == 1
    site = sites_resp.json()["items"][0]
    assert site["lot_id"] == lot_resp.json()["id"]

    quote_resp = await auth_client.post(
        "/api/quotes",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "Spring Refresh",
            "cadence": "monthly",
            "scope": "Restripe the front parking lot",
            "notes": "Customer needs photo proof",
        },
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    assert quote["estimated_cost"] > 0
    assert quote["site_id"] == site["id"]

    work_order_resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "quote_id": quote["id"],
            "title": "WO-1001",
            "date": "2026-04-15",
            "status": "scheduled",
            "assigned_user_id": me["id"],
            "time_preference": "morning",
            "notes": "Bring touch-up kit",
        },
    )
    assert work_order_resp.status_code == 201
    work_order = work_order_resp.json()
    assert work_order["site_id"] == site["id"]
    assert work_order["quote_id"] == quote["id"]

    assign_resp = await auth_client.patch(
        f"/api/work-orders/{work_order['id']}",
        headers=headers,
        json={"status": "assigned", "assigned_user_id": me["id"]},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "assigned"

    run_resp = await auth_client.post(
        f"/api/work-orders/{work_order['id']}/runs",
        headers=headers,
        json={
            "job_id": work_order["id"],
            "technician_user_id": me["id"],
            "notes": "Robot launched from north edge",
        },
    )
    assert run_resp.status_code == 201
    run = run_resp.json()
    assert run["job_id"] == work_order["id"]

    await auth_client.patch(
        f"/api/work-orders/{work_order['id']}",
        headers=headers,
        json={"status": "in_progress"},
    )
    complete_resp = await auth_client.patch(
        f"/api/work-orders/{work_order['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    assert complete_resp.status_code == 200

    run_complete_resp = await auth_client.patch(
        f"/api/job-runs/{run['id']}",
        headers=headers,
        json={
            "status": "completed",
            "actual_paint_gallons": 1.25,
            "telemetry_summary": {"battery_pct": 74, "distance_ft": 1180},
        },
    )
    assert run_complete_resp.status_code == 200
    assert run_complete_resp.json()["status"] == "completed"

    report_resp = await auth_client.post(
        "/api/job-reports",
        headers=headers,
        data={"job_id": work_order["id"], "job_run_id": run["id"]},
    )
    assert report_resp.status_code == 201
    report = report_resp.json()
    assert report["job_id"] == work_order["id"]
    assert report["report_json"]["design"]["line_length_ft"] > 0

    download_json = await auth_client.get(
        f"/api/job-reports/{report['id']}/download?format=json",
        headers=headers,
    )
    assert download_json.status_code == 200
    assert download_json.headers["content-type"].startswith("application/json")

    download_pdf = await auth_client.get(
        f"/api/job-reports/{report['id']}/download?format=pdf",
        headers=headers,
    )
    assert download_pdf.status_code == 200
    assert download_pdf.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_media_and_fleet_operations_flow(auth_client):
    me = (await auth_client.get("/api/auth/me")).json()
    org_id = me["active_organization_id"]
    headers = {"X-Organization-ID": org_id}

    robot_create = await auth_client.post(
        "/api/admin/robots",
        json={"serial_number": "STR-001"},
    )
    assert robot_create.status_code == 403

    from backend.services.robot_store import create_robot, create_robot_claim, claim_robot_for_organization

    robot = await create_robot("STR-001", firmware_version="2026.3.1")
    claim, code = await create_robot_claim(robot["id"], me["id"])
    await claim_robot_for_organization(code, org_id, me["id"], friendly_name="Commercial core robot")

    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert lot_resp.status_code == 201
    site = (await auth_client.get("/api/sites", headers=headers)).json()["items"][0]

    work_order_resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "WO-2001",
            "date": "2026-04-20",
            "status": "scheduled",
            "assigned_user_id": me["id"],
            "assigned_robot_id": robot["id"],
        },
    )
    assert work_order_resp.status_code == 201
    work_order = work_order_resp.json()
    run_resp = await auth_client.post(
        f"/api/work-orders/{work_order['id']}/runs",
        headers=headers,
        json={"job_id": work_order["id"], "robot_id": robot["id"], "technician_user_id": me["id"]},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()

    upload_resp = await auth_client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "before_photo", "job_id": work_order["id"], "job_run_id": run["id"], "site_id": site["id"]},
        files={"file": ("before.jpg", b"jpeg-bytes", "image/jpeg")},
    )
    assert upload_resp.status_code == 201
    asset = upload_resp.json()

    media_list = await auth_client.get(f"/api/media-assets?job_id={work_order['id']}", headers=headers)
    assert media_list.status_code == 200
    assert media_list.json()["total"] == 1

    media_download = await auth_client.get(f"/api/media-assets/{asset['id']}/download", headers=headers)
    assert media_download.status_code == 200
    assert media_download.content == b"jpeg-bytes"

    robot_update = await auth_client.patch(
        f"/api/fleet/robots/{robot['id']}",
        headers=headers,
        json={
            "maintenance_status": "inspection_due",
            "battery_health_pct": 88,
            "issue_state": "paint_pump_watch",
        },
    )
    assert robot_update.status_code == 200
    assert robot_update.json()["maintenance_status"] == "inspection_due"

    maint_resp = await auth_client.post(
        "/api/fleet/maintenance-events",
        headers=headers,
        json={
            "robot_id": robot["id"],
            "event_type": "inspection",
            "summary": "Pre-route inspection",
            "details": "Checked tire pressure and pump lines",
        },
    )
    assert maint_resp.status_code == 201

    checklist_resp = await auth_client.post(
        "/api/fleet/service-checklists",
        headers=headers,
        json={
            "robot_id": robot["id"],
            "name": "Weekly service",
            "checklist_items": ["Clean nozzles", "Check battery terminals"],
        },
    )
    assert checklist_resp.status_code == 201
    assert checklist_resp.json()["checklist_items"][0] == "Clean nozzles"

    consumable_resp = await auth_client.post(
        "/api/fleet/consumables",
        headers=headers,
        json={
            "sku": "PAINT-WHT-5G",
            "name": "White Striping Paint",
            "unit": "gallon",
            "on_hand": 12,
            "reorder_level": 4,
        },
    )
    assert consumable_resp.status_code == 201
    consumable = consumable_resp.json()

    usage_resp = await auth_client.post(
        "/api/fleet/consumable-usage",
        headers=headers,
        json={
            "consumable_item_id": consumable["id"],
            "quantity": 1.5,
            "job_run_id": run["id"],
            "notes": "Used on south lanes",
        },
    )
    assert usage_resp.status_code == 201
    assert usage_resp.json()["quantity"] == 1.5

    items_resp = await auth_client.get("/api/fleet/consumables", headers=headers)
    assert items_resp.status_code == 200
    assert items_resp.json()["items"][0]["on_hand"] == pytest.approx(10.5)
