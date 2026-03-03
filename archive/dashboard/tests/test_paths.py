"""Tests for the /api/paths endpoints."""

import io

import pytest


# ---------------------------------------------------------------------------
# GET /api/paths/templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_templates(client):
    resp = await client.get("/api/paths/templates")
    assert resp.status_code == 200
    body = resp.json()
    # Should contain all seven template types
    expected_keys = {"standard", "angled_60", "angled_45", "handicap", "compact", "arrow", "crosswalk"}
    assert expected_keys == set(body.keys())


@pytest.mark.asyncio
async def test_template_metadata(client):
    resp = await client.get("/api/paths/templates")
    body = resp.json()

    standard = body["standard"]
    assert "name" in standard
    assert "description" in standard
    assert standard["default_spacing_ft"] == 9.0


# ---------------------------------------------------------------------------
# POST /api/paths/template — standard parking stall
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_standard_template(client):
    payload = {
        "template_type": "standard",
        "origin": {"lat": 30.2672, "lng": -97.7431},
        "angle": 0.0,
        "count": 5,
        "spacing_ft": 9.0,
        "length_ft": 18.0,
        "include_end_lines": True,
    }
    resp = await client.post("/api/paths/template", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_type"] == "standard"
    assert body["line_count"] > 0
    geojson = body["geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == body["line_count"]
    # 5 stalls -> 6 divider lines + 2 end lines = 8
    assert body["line_count"] == 8


@pytest.mark.asyncio
async def test_generate_standard_template_no_end_lines(client):
    payload = {
        "template_type": "standard",
        "origin": {"lat": 30.0, "lng": -97.0},
        "count": 3,
        "include_end_lines": False,
    }
    resp = await client.post("/api/paths/template", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # 3 stalls -> 4 divider lines, no end lines
    assert body["line_count"] == 4


@pytest.mark.asyncio
async def test_generate_angled_template(client):
    payload = {
        "template_type": "angled_60",
        "origin": {"lat": 30.0, "lng": -97.0},
        "count": 4,
        "include_end_lines": True,
    }
    resp = await client.post("/api/paths/template", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_type"] == "angled_60"
    # 4 stalls -> 5 dividers + 2 end lines = 7
    assert body["line_count"] == 7


# ---------------------------------------------------------------------------
# POST /api/paths/template — arrow (uses striper_pathgen)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_arrow_template(client):
    """Arrow template should return paint path features via striper_pathgen."""
    payload = {
        "template_type": "arrow",
        "origin": {"lat": 30.0, "lng": -97.0},
        "arrow_type": "straight",
    }
    resp = await client.post("/api/paths/template", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_type"] == "arrow"
    assert body["line_count"] >= 2
    assert len(body["geojson"]["features"]) >= 2


# ---------------------------------------------------------------------------
# POST /api/paths/template — crosswalk (uses striper_pathgen)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_crosswalk_template(client):
    """Crosswalk template should return stripe features via striper_pathgen."""
    payload = {
        "template_type": "crosswalk",
        "origin": {"lat": 30.0, "lng": -97.0},
    }
    resp = await client.post("/api/paths/template", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_type"] == "crosswalk"
    assert body["line_count"] >= 2
    assert len(body["geojson"]["features"]) >= 2


# ---------------------------------------------------------------------------
# POST /api/paths/upload — validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_reject_non_dxf_svg(client):
    """Only .dxf and .svg files should be accepted."""
    file_content = b"not a real file"
    resp = await client.post(
        "/api/paths/upload",
        files={"file": ("drawing.png", io.BytesIO(file_content), "image/png")},
    )
    assert resp.status_code == 400
    assert "Only DXF and SVG" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_reject_txt(client):
    resp = await client.post(
        "/api/paths/upload",
        files={"file": ("plan.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_missing_file(client):
    """Posting without a file should return a 422 validation error."""
    resp = await client.post("/api/paths/upload")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/paths/preview/{job_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_nonexistent_job(client):
    resp = await client.get("/api/paths/preview/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_with_path_data(client):
    """Create a job with path data and verify preview returns it."""
    features = [
        {
            "type": "Feature",
            "properties": {"line_type": "stall_divider"},
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        }
    ]
    create_resp = await client.post(
        "/api/jobs",
        json={"name": "Preview Test", "path_data": {"features": features}},
    )
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/paths/preview/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["line_type"] == "stall_divider"


@pytest.mark.asyncio
async def test_preview_without_path_data(client):
    """Job exists but has no path_data — should return empty features."""
    create_resp = await client.post("/api/jobs", json={"name": "Empty Path"})
    job_id = create_resp.json()["id"]

    resp = await client.get(f"/api/paths/preview/{job_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"] == []
