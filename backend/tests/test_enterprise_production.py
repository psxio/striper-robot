"""Enterprise production hardening tests."""

import pytest

from backend.config import settings


LOT_DATA = {
    "name": "Enterprise Lot",
    "center": {"lat": 41.8781, "lng": -87.6298},
    "zoom": 19,
    "features": [
        {
            "type": "Feature",
            "properties": {"width": 4, "color": "#ffffff"},
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-87.6298, 41.8781],
                    [-87.6296, 41.8782],
                ],
            },
        }
    ],
}


async def _register(client, email: str, name: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "testpass123", "name": name},
    )
    assert resp.status_code == 201
    payload = resp.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.mark.asyncio
async def test_org_invite_membership_and_audit_flow(client):
    owner = await _register(client, "owner@example.com", "Owner")
    client.headers["Authorization"] = f"Bearer {owner['token']}"
    me = (await client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    invite_resp = await client.post(
        "/api/organizations/invites",
        headers=headers,
        json={"email": "tech@example.com", "role": "technician"},
    )
    assert invite_resp.status_code == 201
    invite = invite_resp.json()
    assert invite["accept_token"]

    second = await _register(client, "tech@example.com", "Technician")
    client.headers["Authorization"] = f"Bearer {second['token']}"
    accept_resp = await client.post(f"/api/organizations/invites/{invite['accept_token']}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["membership"]["role"] == "technician"

    client.headers["Authorization"] = f"Bearer {owner['token']}"
    memberships_resp = await client.get("/api/organizations/memberships", headers=headers)
    assert memberships_resp.status_code == 200
    assert len(memberships_resp.json()["items"]) == 2

    update_role_resp = await client.patch(
        f"/api/organizations/memberships/{second['user']['id']}",
        headers=headers,
        json={"role": "dispatcher"},
    )
    assert update_role_resp.status_code == 200
    assert update_role_resp.json()["role"] == "dispatcher"

    audit_resp = await client.get("/api/organizations/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    actions = [item["action"] for item in audit_resp.json()["items"]]
    assert "membership.invited" in actions
    assert "membership.accepted" in actions
    assert "membership.role_changed" in actions


@pytest.mark.asyncio
async def test_verification_requires_complete_report_package(client):
    owner = await _register(client, "ops@example.com", "Ops Owner")
    client.headers["Authorization"] = f"Bearer {owner['token']}"
    me = (await client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    lot_resp = await client.post("/api/lots", json=LOT_DATA)
    assert lot_resp.status_code == 201
    site = (await client.get("/api/sites", headers=headers)).json()["items"][0]

    quote_resp = await client.post(
        "/api/quotes",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "Enterprise Quote",
            "cadence": "monthly",
            "scope": "Restripe and document",
            "notes": "Need customer-ready proof",
        },
    )
    quote = quote_resp.json()

    work_order_resp = await client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "quote_id": quote["id"],
            "title": "Enterprise WO",
            "date": "2026-04-18",
            "status": "scheduled",
            "assigned_user_id": me["id"],
        },
    )
    work_order = work_order_resp.json()

    run_resp = await client.post(
        f"/api/work-orders/{work_order['id']}/runs",
        headers=headers,
        json={"job_id": work_order["id"], "technician_user_id": me["id"], "notes": "Launched"},
    )
    run = run_resp.json()

    await client.patch(f"/api/work-orders/{work_order['id']}", headers=headers, json={"status": "assigned", "assigned_user_id": me["id"]})
    await client.patch(f"/api/work-orders/{work_order['id']}", headers=headers, json={"status": "in_progress"})
    await client.patch(f"/api/work-orders/{work_order['id']}", headers=headers, json={"status": "completed"})
    await client.patch(
        f"/api/job-runs/{run['id']}",
        headers=headers,
        json={"status": "completed", "actual_paint_gallons": 1.1, "telemetry_summary": {"battery_pct": 84}},
    )

    blocked = await client.patch(f"/api/work-orders/{work_order['id']}", headers=headers, json={"status": "verified"})
    assert blocked.status_code == 400
    assert "Customer-ready verification blocked" in blocked.json()["detail"]

    upload_resp = await client.post(
        "/api/media-assets",
        headers=headers,
        data={"asset_type": "before_photo", "job_id": work_order["id"], "job_run_id": run["id"], "site_id": site["id"]},
        files={"file": ("before.jpg", b"proof-bytes", "image/jpeg")},
    )
    assert upload_resp.status_code == 201

    report_resp = await client.post(
        "/api/job-reports",
        headers=headers,
        data={"job_id": work_order["id"], "job_run_id": run["id"]},
    )
    assert report_resp.status_code == 201

    verified = await client.patch(f"/api/work-orders/{work_order['id']}", headers=headers, json={"status": "verified"})
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"

    audit_resp = await client.get("/api/organizations/audit-logs", headers=headers)
    actions = [item["action"] for item in audit_resp.json()["items"]]
    assert "report.generated" in actions
    assert "work_order.updated" in actions


@pytest.mark.asyncio
async def test_readiness_and_request_size_limit(auth_client):
    original_limit = settings.MAX_UPLOAD_BYTES
    try:
        ready = await auth_client.get("/api/ready")
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"

        settings.MAX_UPLOAD_BYTES = 32
        oversized = await auth_client.post("/api/lots", json={**LOT_DATA, "name": "X" * 200})
        assert oversized.status_code == 413
    finally:
        settings.MAX_UPLOAD_BYTES = original_limit
