"""Tests for the cost estimation endpoint."""

import pytest


ENDPOINT = "/api/estimates/calculate"


def _line_feature(coords):
    """Helper to build a GeoJSON LineString feature from coordinate pairs."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
    }


def _point_feature(coord):
    """Helper to build a GeoJSON Point feature."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": coord,
        },
    }


# ---- 1. Empty features → all zeros ----

@pytest.mark.asyncio
async def test_estimate_empty_features(auth_client):
    resp = await auth_client.post(ENDPOINT, json={"features": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_line_length_ft"] == 0.0
    assert data["paint_gallons"] == 0.0
    assert data["estimated_runtime_min"] == 0
    assert data["estimated_cost"] == 0.0


# ---- 2. Single LineString → non-zero values ----

@pytest.mark.asyncio
async def test_estimate_single_line(auth_client):
    # Use points far enough apart (~440 ft) so runtime rounds to >= 1 min.
    feature = _line_feature([[-74.006, 40.7128], [-74.006, 40.7140]])
    resp = await auth_client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_line_length_ft"] > 0
    assert data["paint_gallons"] > 0
    assert data["estimated_runtime_min"] > 0
    assert data["estimated_cost"] > 0


# ---- 3. Multiple LineStrings → larger values than single ----

@pytest.mark.asyncio
async def test_estimate_multiple_lines(auth_client):
    line1 = _line_feature([[-74.006, 40.7128], [-74.006, 40.7130]])
    line2 = _line_feature([[-74.005, 40.7128], [-74.005, 40.7130]])

    single_resp = await auth_client.post(ENDPOINT, json={"features": [line1]})
    multi_resp = await auth_client.post(ENDPOINT, json={"features": [line1, line2]})

    single = single_resp.json()
    multi = multi_resp.json()

    assert multi["total_line_length_ft"] > single["total_line_length_ft"]
    assert multi["paint_gallons"] > single["paint_gallons"]
    assert multi["estimated_cost"] > single["estimated_cost"]


# ---- 4. Non-LineString (Point) is ignored → zeros ----

@pytest.mark.asyncio
async def test_estimate_non_linestring_ignored(auth_client):
    point = _point_feature([-74.006, 40.7128])
    resp = await auth_client.post(ENDPOINT, json={"features": [point]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_line_length_ft"] == 0.0
    assert data["paint_gallons"] == 0.0
    assert data["estimated_runtime_min"] == 0
    assert data["estimated_cost"] == 0.0


# ---- 5. Mixed features → only LineStrings counted ----

@pytest.mark.asyncio
async def test_estimate_mixed_features(auth_client):
    line = _line_feature([[-74.006, 40.7128], [-74.006, 40.7130]])
    point = _point_feature([-74.005, 40.7128])

    line_only_resp = await auth_client.post(ENDPOINT, json={"features": [line]})
    mixed_resp = await auth_client.post(ENDPOINT, json={"features": [line, point]})

    assert line_only_resp.json() == mixed_resp.json()


# ---- 6. Response shape — all 4 fields present ----

@pytest.mark.asyncio
async def test_estimate_response_shape(auth_client):
    feature = _line_feature([[-74.006, 40.7128], [-74.006, 40.7130]])
    resp = await auth_client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_line_length_ft" in data
    assert "paint_gallons" in data
    assert "estimated_runtime_min" in data
    assert "estimated_cost" in data
    assert isinstance(data["total_line_length_ft"], float)
    assert isinstance(data["paint_gallons"], float)
    assert isinstance(data["estimated_runtime_min"], int)
    assert isinstance(data["estimated_cost"], float)


# ---- 7. Unauthenticated request → 401 ----

@pytest.mark.asyncio
async def test_estimate_requires_auth(client):
    feature = _line_feature([[-74.006, 40.7128], [-74.006, 40.7130]])
    resp = await client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 401


# ---- 8. Known-distance line → reasonable values ----

@pytest.mark.asyncio
async def test_estimate_values_reasonable(auth_client):
    # Two points ~100m apart (same longitude, ~0.0009 degrees latitude difference).
    # Expected distance: roughly 100m ≈ 330 feet.
    feature = _line_feature([[-74.006, 40.7128], [-74.006, 40.7137]])
    resp = await auth_client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 200
    data = resp.json()

    length = data["total_line_length_ft"]
    assert 250 < length < 450, f"Expected ~330 ft, got {length}"

    # Paint: ~330 ft / 300 ft per gallon ≈ 1.1 gallons
    assert 0.5 < data["paint_gallons"] < 2.0

    # Runtime: ~330 ft / 200 ft per min ≈ 1.65 min → rounded to 2
    assert 1 <= data["estimated_runtime_min"] <= 3

    # Cost: ~330 ft * $0.15 = ~$49.50
    assert 30 < data["estimated_cost"] < 70


# ---- 9. LineString with a single coordinate → 0 length ----

@pytest.mark.asyncio
async def test_estimate_single_point_line(auth_client):
    # A degenerate LineString with only one coordinate has no segments.
    feature = _line_feature([[-74.006, 40.7128]])
    resp = await auth_client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_line_length_ft"] == 0.0
    assert data["paint_gallons"] == 0.0
    assert data["estimated_runtime_min"] == 0
    assert data["estimated_cost"] == 0.0


# ---- 10. Cost formula: cost = length_ft * 0.15 ----

@pytest.mark.asyncio
async def test_estimate_cost_formula(auth_client):
    feature = _line_feature([[-74.006, 40.7128], [-74.006, 40.7140]])
    resp = await auth_client.post(ENDPOINT, json={"features": [feature]})
    assert resp.status_code == 200
    data = resp.json()

    expected_cost = round(data["total_line_length_ft"] * 0.15, 2)
    assert data["estimated_cost"] == expected_cost
