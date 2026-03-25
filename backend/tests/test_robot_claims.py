import pytest

from backend.services.billing_store import set_user_plan


async def _register(client, email: str, name: str = "User"):
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "testpass123", "name": name},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_robot_claim_lifecycle(admin_client, client):
    admin_robot = await admin_client.post("/api/admin/robots", json={"serial_number": "CLAIM-001"})
    assert admin_robot.status_code == 201
    robot_id = admin_robot.json()["id"]

    create_claim = await admin_client.post("/api/robot-claims", json={"robot_id": robot_id})
    assert create_claim.status_code == 201
    claim = create_claim.json()
    assert claim["status"] == "pending"
    code = claim["claim_code"]

    user = await _register(client, "claim-user@example.com")
    client.headers["Authorization"] = f"Bearer {user['token']}"
    await set_user_plan(user["user"]["id"], "robot")  # Need robot tier to claim
    me = (await client.get("/api/auth/me")).json()
    headers = {"X-Organization-ID": me["active_organization_id"]}

    validate = await client.get(f"/api/robot-claims/{code}", headers=headers)
    assert validate.status_code == 200
    assert validate.json()["robot_id"] == robot_id

    claimed = await client.post(
        f"/api/robot-claims/{code}/claim",
        headers=headers,
        json={"friendly_name": "North lot unit", "deployment_notes": "Commissioned in staging"},
    )
    assert claimed.status_code == 200
    data = claimed.json()
    assert data["organization_id"] == me["active_organization_id"]
    assert data["commissioning_status"] == "commissioned"
    assert data["robot"]["claim_status"] == "claimed"
    assert data["robot"]["organization_id"] == me["active_organization_id"]
    assert data["api_key"].startswith("strk_")

    second_claim = await client.post(
        f"/api/robot-claims/{code}/claim",
        headers=headers,
        json={},
    )
    # 403 = tier limit (robot plan allows 1, already claimed 1)
    # 400 = claim code already used (if tier check was bypassed)
    assert second_claim.status_code in (400, 403)

    fleet = await client.get("/api/fleet/claimed-robots", headers=headers)
    assert fleet.status_code == 200
    assert fleet.json()["total"] == 1
    assert fleet.json()["items"][0]["id"] == robot_id


@pytest.mark.asyncio
async def test_robot_claim_isolation_between_orgs(admin_client, client):
    robot_resp = await admin_client.post("/api/admin/robots", json={"serial_number": "CLAIM-ISO-001"})
    robot_id = robot_resp.json()["id"]
    claim_resp = await admin_client.post("/api/robot-claims", json={"robot_id": robot_id})
    code = claim_resp.json()["claim_code"]

    first = await _register(client, "first-org@example.com", name="First Org")
    client.headers["Authorization"] = f"Bearer {first['token']}"
    await set_user_plan(first["user"]["id"], "robot")  # Need robot tier to claim
    first_me = (await client.get("/api/auth/me")).json()
    first_headers = {"X-Organization-ID": first_me["active_organization_id"]}
    claim_first = await client.post(
        f"/api/robot-claims/{code}/claim",
        headers=first_headers,
        json={"friendly_name": "Ops robot"},
    )
    assert claim_first.status_code == 200

    second = await _register(client, "second-org@example.com", name="Second Org")
    client.headers["Authorization"] = f"Bearer {second['token']}"
    second_me = (await client.get("/api/auth/me")).json()
    second_headers = {"X-Organization-ID": second_me["active_organization_id"]}

    validate = await client.get(f"/api/robot-claims/{code}", headers=second_headers)
    assert validate.status_code == 403

    fleet = await client.get("/api/fleet/claimed-robots", headers=second_headers)
    assert fleet.status_code == 200
    assert fleet.json()["total"] == 0
