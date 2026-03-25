"""Post-deploy smoke checks for staging and production."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected: int = 200,
    **kwargs: Any,
) -> Any:
    resp = session.request(method, url, timeout=30, **kwargs)
    if resp.status_code != expected:
        fail(f"{method} {url} returned {resp.status_code}: {resp.text[:500]}")
    if not resp.content:
        return None
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        return resp.json()
    return resp.text


def main() -> None:
    base_url = os.environ.get("SMOKE_BASE_URL", "").rstrip("/")
    email = os.environ.get("SMOKE_EMAIL", "")
    password = os.environ.get("SMOKE_PASSWORD", "")
    if not base_url:
        fail("SMOKE_BASE_URL is required")
    if not email or not password:
        fail("SMOKE_EMAIL and SMOKE_PASSWORD are required")

    session = requests.Session()

    ready = request_json(session, "GET", f"{base_url}/api/ready")
    print(json.dumps({"ready": ready}, indent=2))

    auth = request_json(
        session,
        "POST",
        f"{base_url}/api/auth/login",
        json={"email": email, "password": password},
    )
    token = auth["token"]
    session.headers["Authorization"] = f"Bearer {token}"

    me = request_json(session, "GET", f"{base_url}/api/auth/me")
    orgs = request_json(session, "GET", f"{base_url}/api/organizations")
    org_id = os.environ.get("SMOKE_ORG_ID") or orgs.get("active_organization_id") or me.get("active_organization_id")
    if not org_id:
        fail("No organization available for smoke checks")
    session.headers["X-Organization-ID"] = org_id

    lots = request_json(session, "GET", f"{base_url}/api/lots")
    lot_name = f"Smoke Lot {org_id[:8]}"
    lot_payload = {
        "name": lot_name,
        "center": {"lat": 41.8781, "lng": -87.6298},
        "zoom": 18,
        "features": [],
    }
    lot = request_json(session, "POST", f"{base_url}/api/lots", json=lot_payload, expected=201)

    sites = request_json(session, "GET", f"{base_url}/api/sites")
    site = next((item for item in sites["items"] if item.get("lot_id") == lot["id"]), None)
    if not site:
        fail("Expected auto-linked site for smoke lot")

    scan = request_json(
        session,
        "POST",
        f"{base_url}/api/site-scans",
        json={"site_id": site["id"], "scan_type": "manual_trace", "notes": "Smoke scan"},
        expected=201,
    )
    simulation = request_json(
        session,
        "POST",
        f"{base_url}/api/site-simulations",
        json={"site_id": site["id"], "scan_id": scan["id"], "mode": "preview", "speed_mph": 2.0},
        expected=201,
    )
    work_order = request_json(
        session,
        "POST",
        f"{base_url}/api/work-orders",
        json={
            "site_id": site["id"],
            "title": "Smoke Work Order",
            "date": "2026-12-01",
            "status": "scheduled",
        },
        expected=201,
    )

    reports = request_json(session, "GET", f"{base_url}/api/job-reports")
    print(
        json.dumps(
            {
                "me": {"id": me["id"], "active_organization_id": org_id},
                "lots_total": lots["total"],
                "site_id": site["id"],
                "scan_id": scan["id"],
                "simulation_id": simulation["id"],
                "work_order_id": work_order["id"],
                "reports_total": reports.get("total", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
