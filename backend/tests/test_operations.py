"""Tests for work orders, job runs, and operations scheduling."""

import pytest


LOT_DATA = {
    "name": "Operations Test Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [],
}


async def _setup_site_and_org(auth_client):
    """Create a lot/site and return (org_headers, site, me)."""
    me = (await auth_client.get("/api/auth/me")).json()
    org_id = me["active_organization_id"]
    headers = {"X-Organization-ID": org_id}

    lot_resp = await auth_client.post("/api/lots", json=LOT_DATA)
    assert lot_resp.status_code == 201

    sites_resp = await auth_client.get("/api/sites", headers=headers)
    site = sites_resp.json()["items"][0]
    return headers, site, me


@pytest.mark.asyncio
async def test_list_work_orders_empty(auth_client):
    """GET /api/work-orders returns empty list initially."""
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}
    resp = await auth_client.get("/api/work-orders", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_work_order(auth_client):
    """POST /api/work-orders creates a work order for an existing site."""
    headers, site, me = await _setup_site_and_org(auth_client)

    resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": site["id"],
            "title": "WO-BASIC-001",
            "date": "2026-06-01",
            "status": "scheduled",
        },
    )
    assert resp.status_code == 201
    wo = resp.json()
    assert wo["site_id"] == site["id"]
    assert wo["status"] == "scheduled"


@pytest.mark.asyncio
async def test_get_work_order(auth_client):
    """GET /api/work-orders/{id} returns the specific work order."""
    headers, site, me = await _setup_site_and_org(auth_client)

    wo = (
        await auth_client.post(
            "/api/work-orders",
            headers=headers,
            json={"site_id": site["id"], "title": "WO-GET-001", "date": "2026-06-02", "status": "scheduled"},
        )
    ).json()

    resp = await auth_client.get(f"/api/work-orders/{wo['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == wo["id"]


@pytest.mark.asyncio
async def test_update_work_order_status(auth_client):
    """PATCH /api/work-orders/{id} updates status."""
    headers, site, me = await _setup_site_and_org(auth_client)

    wo = (
        await auth_client.post(
            "/api/work-orders",
            headers=headers,
            json={"site_id": site["id"], "title": "WO-UPD-001", "date": "2026-06-03", "status": "scheduled"},
        )
    ).json()

    resp = await auth_client.patch(
        f"/api/work-orders/{wo['id']}",
        headers=headers,
        json={"status": "assigned", "assigned_user_id": me["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "assigned"


@pytest.mark.asyncio
async def test_create_work_order_nonexistent_site(auth_client):
    """POST /api/work-orders returns 404 for unknown site_id."""
    me = (await auth_client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    resp = await auth_client.post(
        "/api/work-orders",
        headers=headers,
        json={
            "site_id": "nonexistent-site-id",
            "title": "WO-BAD",
            "date": "2026-06-10",
            "status": "scheduled",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_job_run(auth_client):
    """POST /api/work-orders/{id}/runs creates a job run."""
    headers, site, me = await _setup_site_and_org(auth_client)

    wo = (
        await auth_client.post(
            "/api/work-orders",
            headers=headers,
            json={"site_id": site["id"], "title": "WO-RUN-001", "date": "2026-06-04", "status": "scheduled"},
        )
    ).json()

    run_resp = await auth_client.post(
        f"/api/work-orders/{wo['id']}/runs",
        headers=headers,
        json={"job_id": wo["id"], "technician_user_id": me["id"], "notes": "Started from north entrance"},
    )
    assert run_resp.status_code == 201
    run = run_resp.json()
    assert run["job_id"] == wo["id"]


@pytest.mark.asyncio
async def test_list_job_runs(auth_client):
    """GET /api/work-orders/{id}/runs lists runs for a work order."""
    headers, site, me = await _setup_site_and_org(auth_client)

    wo = (
        await auth_client.post(
            "/api/work-orders",
            headers=headers,
            json={"site_id": site["id"], "title": "WO-RUNS-001", "date": "2026-06-05", "status": "scheduled"},
        )
    ).json()

    await auth_client.post(
        f"/api/work-orders/{wo['id']}/runs",
        headers=headers,
        json={"job_id": wo["id"], "technician_user_id": me["id"]},
    )

    list_resp = await auth_client.get(f"/api/work-orders/{wo['id']}/runs", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_work_orders_require_auth(client):
    """Work order endpoints require authentication."""
    resp = await client.get("/api/work-orders")
    assert resp.status_code == 401
