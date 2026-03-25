"""Persisted site scans and cloud simulation runs for site operations."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db
from . import estimate_store, robot_store, site_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_lot(site_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            """SELECT l.*
               FROM sites s
               LEFT JOIN lots l ON l.id = s.lot_id
               WHERE s.id = ?""",
            (site_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


def _feature_summary(features: list[dict], center: Optional[dict], zoom: Optional[int]) -> dict:
    estimate = estimate_store.calculate_estimate(features)
    feature_count = len(features)
    line_count = 0
    point_count = 0
    min_lat = min_lng = max_lat = max_lng = None
    for feature in features:
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if geometry.get("type") == "LineString":
            line_count += 1
            for point in coords:
                if len(point) < 2:
                    continue
                lng, lat = point[0], point[1]
                min_lat = lat if min_lat is None else min(min_lat, lat)
                max_lat = lat if max_lat is None else max(max_lat, lat)
                min_lng = lng if min_lng is None else min(min_lng, lng)
                max_lng = lng if max_lng is None else max(max_lng, lng)
                point_count += 1
    return {
        **estimate,
        "feature_count": feature_count,
        "line_count": line_count,
        "point_count": point_count,
        "bounds": (
            None
            if min_lat is None
            else {
                "south": min_lat,
                "west": min_lng,
                "north": max_lat,
                "east": max_lng,
            }
        ),
        "center": center,
        "zoom": zoom,
    }


def _parse_scan_row(row) -> dict:
    data = dict(row)
    data["summary"] = json.loads(data.get("summary_json") or "{}")
    data["geometry_snapshot"] = json.loads(data.get("geometry_snapshot_json") or "[]")
    data.pop("summary_json", None)
    data.pop("geometry_snapshot_json", None)
    return data


def _parse_simulation_row(row) -> dict:
    data = dict(row)
    data["config"] = json.loads(data.get("config_json") or "{}")
    data["result"] = json.loads(data.get("result_json") or "{}")
    data.pop("config_json", None)
    data.pop("result_json", None)
    return data


async def get_site_scan(organization_id: str, scan_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM site_scans WHERE organization_id = ? AND id = ?",
            (organization_id, scan_id),
        )
        row = await cursor.fetchone()
        return _parse_scan_row(row) if row else None


async def list_site_scans(organization_id: str, site_id: Optional[str] = None) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND site_id = ?"
            params.append(site_id)
        cursor = await db.execute(
            f"SELECT * FROM site_scans {where} ORDER BY captured_at DESC, created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [_parse_scan_row(row) for row in rows]


async def create_site_scan(
    organization_id: str,
    created_by_user_id: str,
    site_id: str,
    *,
    scan_type: str,
    notes: str = "",
    source_media_asset_id: Optional[str] = None,
) -> dict:
    site = await site_store.get_site(organization_id, site_id)
    if not site:
        raise ValueError("Site not found")
    lot = await _get_lot(site_id)
    features: list[dict] = []
    if lot and lot.get("features"):
        try:
            features = json.loads(lot["features"])
        except json.JSONDecodeError:
            features = []
    summary = _feature_summary(features, site.get("center"), site.get("zoom"))
    scan_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO site_scans
               (id, organization_id, site_id, lot_id, source_media_asset_id, scan_type, notes,
                summary_json, geometry_snapshot_json, captured_at, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scan_id,
                organization_id,
                site_id,
                site.get("lot_id"),
                source_media_asset_id,
                scan_type,
                notes,
                json.dumps(summary),
                json.dumps(features),
                now,
                created_by_user_id,
                now,
                now,
            ),
        )
        await db.commit()
    return await get_site_scan(organization_id, scan_id) or {}


async def get_simulation_run(organization_id: str, simulation_id: str) -> Optional[dict]:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM simulation_runs WHERE organization_id = ? AND id = ?",
            (organization_id, simulation_id),
        )
        row = await cursor.fetchone()
        return _parse_simulation_row(row) if row else None


async def list_simulation_runs(
    organization_id: str,
    *,
    site_id: Optional[str] = None,
    scan_id: Optional[str] = None,
) -> list[dict]:
    async for db in get_db():
        where = "WHERE organization_id = ?"
        params: list[object] = [organization_id]
        if site_id:
            where += " AND site_id = ?"
            params.append(site_id)
        if scan_id:
            where += " AND scan_id = ?"
            params.append(scan_id)
        cursor = await db.execute(
            f"SELECT * FROM simulation_runs {where} ORDER BY created_at DESC",
            tuple(params),
        )
        rows = await cursor.fetchall()
        return [_parse_simulation_row(row) for row in rows]


async def create_simulation_run(
    organization_id: str,
    created_by_user_id: str,
    *,
    site_id: str,
    scan_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    robot_id: Optional[str] = None,
    mode: str = "preview",
    speed_mph: float = 2.0,
    notes: str = "",
) -> dict:
    site = await site_store.get_site(organization_id, site_id)
    if not site:
        raise ValueError("Site not found")
    scan = await get_site_scan(organization_id, scan_id) if scan_id else None
    if scan_id and not scan:
        raise ValueError("Site scan not found")
    if not scan:
        scan = await create_site_scan(
            organization_id,
            created_by_user_id,
            site_id,
            scan_type="manual_trace",
            notes="Auto-generated scan for cloud simulation",
        )

    summary = scan.get("summary") or {}
    line_length_ft = float(summary.get("total_line_length_ft") or 0)
    route_distance_ft = round(line_length_ft * 1.12, 1)
    transit_distance_ft = round(max(route_distance_ft - line_length_ft, 0), 1)
    speed_fpm = max(speed_mph * 88.0, 1.0)
    runtime_min = round(route_distance_ft / speed_fpm, 1)
    utilization_pct = round(min((line_length_ft / max(route_distance_ft, 1)) * 100, 100), 1)
    risk_flags: list[str] = []
    robot = await robot_store.get_robot(robot_id) if robot_id else None
    if robot:
        if robot.get("maintenance_status") not in (None, "", "ready"):
            risk_flags.append(f"maintenance_{robot['maintenance_status']}")
        if robot.get("issue_state"):
            risk_flags.append(f"issue_{robot['issue_state']}")
        if robot.get("battery_health_pct") is not None and robot["battery_health_pct"] < 60:
            risk_flags.append("battery_health_low")
    if summary.get("line_count", 0) > 80:
        risk_flags.append("dense_layout")
    if summary.get("bounds") is None:
        risk_flags.append("no_geometry_bounds")
    readiness = "ready" if not risk_flags else "review"

    config = {
        "mode": mode,
        "speed_mph": speed_mph,
        "site_id": site_id,
        "scan_id": scan["id"],
        "work_order_id": work_order_id,
        "robot_id": robot_id,
    }
    result = {
        "site_name": site["name"],
        "route_distance_ft": route_distance_ft,
        "stripe_distance_ft": line_length_ft,
        "transit_distance_ft": transit_distance_ft,
        "estimated_runtime_min": runtime_min,
        "paint_gallons": summary.get("paint_gallons"),
        "estimated_cost": summary.get("estimated_cost"),
        "utilization_pct": utilization_pct,
        "risk_flags": risk_flags,
        "readiness": readiness,
    }

    simulation_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO simulation_runs
               (id, organization_id, site_id, scan_id, work_order_id, robot_id, status, mode, notes,
                config_json, result_json, created_by_user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                simulation_id,
                organization_id,
                site_id,
                scan["id"],
                work_order_id,
                robot_id,
                readiness,
                mode,
                notes,
                json.dumps(config),
                json.dumps(result),
                created_by_user_id,
                now,
                now,
            ),
        )
        await db.commit()
    return await get_simulation_run(organization_id, simulation_id) or {}
