"""Tests for Phase 4: DXF/SVG Import & Server-Side Export."""

import io
import pytest
import pytest_asyncio


LOT_DATA = {
    "name": "Import Test Lot",
    "center": {"lat": 40.7128, "lng": -74.0060},
    "zoom": 19,
    "features": [],
}


@pytest_asyncio.fixture
async def lot_id(auth_client):
    resp = await auth_client.post("/api/lots", json=LOT_DATA)
    return resp.json()["id"]


def _make_dxf_content() -> bytes:
    """Create a minimal DXF file with a single line."""
    import ezdxf
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (5, 5))
    msp.add_line((5, 5), (10, 0))
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def _make_svg_content() -> bytes:
    """Create a minimal SVG with a line path."""
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <line x1="0" y1="0" x2="10" y2="10" stroke="white" stroke-width="1"/>
  <polyline points="10,10 20,0 30,10" stroke="yellow" stroke-width="2" fill="none"/>
</svg>'''
    return svg.encode("utf-8")


# --- Import ---

@pytest.mark.asyncio
async def test_import_dxf(auth_client, lot_id):
    dxf_data = _make_dxf_content()
    resp = await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.dxf", dxf_data, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) >= 1
    # Check first feature has GeoJSON structure
    f = data["features"][0]
    assert f["type"] == "Feature"
    assert f["geometry"]["type"] == "LineString"
    assert len(f["geometry"]["coordinates"]) >= 2


@pytest.mark.asyncio
async def test_import_svg(auth_client, lot_id):
    svg_data = _make_svg_content()
    resp = await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.svg", svg_data, "image/svg+xml")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) >= 1


@pytest.mark.asyncio
async def test_import_bad_extension(auth_client, lot_id):
    resp = await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_oversize(auth_client, lot_id):
    big_data = b"x" * (6 * 1024 * 1024)  # 6 MB
    resp = await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("big.dxf", big_data, "application/octet-stream")},
    )
    assert resp.status_code == 413


# --- Export ---

@pytest.mark.asyncio
async def test_export_geojson(auth_client, lot_id):
    # First import a DXF to have features
    dxf_data = _make_dxf_content()
    await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.dxf", dxf_data, "application/octet-stream")},
    )

    resp = await auth_client.post(
        f"/api/lots/{lot_id}/export",
        json={"format": "geojson"},
    )
    assert resp.status_code == 200
    assert "application/geo+json" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_waypoints(auth_client, lot_id):
    dxf_data = _make_dxf_content()
    await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.dxf", dxf_data, "application/octet-stream")},
    )

    resp = await auth_client.post(
        f"/api/lots/{lot_id}/export",
        json={"format": "waypoints"},
    )
    assert resp.status_code == 200
    assert "QGC WPL" in resp.text


@pytest.mark.asyncio
async def test_export_kml(auth_client, lot_id):
    dxf_data = _make_dxf_content()
    await auth_client.post(
        f"/api/lots/{lot_id}/import",
        files={"file": ("test.dxf", dxf_data, "application/octet-stream")},
    )

    resp = await auth_client.post(
        f"/api/lots/{lot_id}/export",
        json={"format": "kml"},
    )
    assert resp.status_code == 200
    assert "<?xml" in resp.text


@pytest.mark.asyncio
async def test_export_empty_lot(auth_client, lot_id):
    resp = await auth_client.post(
        f"/api/lots/{lot_id}/export",
        json={"format": "geojson"},
    )
    assert resp.status_code == 400
