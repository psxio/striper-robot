"""Cost estimation persistence layer using aiosqlite."""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..database import get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _haversine_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the distance between two lat/lon points in feet using the Haversine formula."""
    earth_radius_miles = 3958.8
    feet_per_mile = 5280

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_miles * feet_per_mile * c


def calculate_estimate(features: list[dict]) -> dict:
    """Calculate cost estimate from a list of GeoJSON features.

    Sums line lengths from LineString geometries using Haversine distances.
    Returns dict with total_line_length_ft, paint_gallons, estimated_runtime_min,
    and estimated_cost.
    """
    total_ft = 0.0

    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "LineString":
            continue
        coords = geometry.get("coordinates", [])
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i][0], coords[i][1]
            lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
            total_ft += _haversine_ft(lat1, lon1, lat2, lon2)

    return {
        "total_line_length_ft": round(total_ft, 1),
        "paint_gallons": round(total_ft / 300, 2),
        "estimated_runtime_min": round(total_ft / 200),
        "estimated_cost": round(total_ft * 0.15, 2),
    }


async def save_estimate(job_id: str, estimate_data: dict) -> dict:
    """Insert a cost estimate into job_estimates and return the saved dict."""
    estimate_id = str(uuid.uuid4())
    now = _now()
    async for db in get_db():
        await db.execute(
            """INSERT INTO job_estimates (id, job_id, total_line_length_ft, paint_gallons,
               estimated_runtime_min, estimated_cost, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                estimate_id,
                job_id,
                estimate_data["total_line_length_ft"],
                estimate_data["paint_gallons"],
                estimate_data["estimated_runtime_min"],
                estimate_data["estimated_cost"],
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM job_estimates WHERE id = ?", (estimate_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_estimate(job_id: str) -> Optional[dict]:
    """Get an estimate by job_id, return dict or None."""
    async for db in get_db():
        cursor = await db.execute(
            "SELECT * FROM job_estimates WHERE job_id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
