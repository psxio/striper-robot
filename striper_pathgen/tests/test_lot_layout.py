"""Tests for parking lot layout generation."""

import json
import pytest

from striper_pathgen.lot_layout import LotLayout, generate_from_layout
from striper_pathgen.models import GeoPoint


def _simple_layout() -> dict:
    """Return a minimal valid layout dict."""
    return {
        "name": "Test Lot",
        "datum": {"lat": 30.0, "lon": -97.0},
        "heading": 0.0,
        "elements": [
            {
                "type": "parking_row",
                "origin": [0.0, 0.0],
                "angle": 0.0,
                "count": 5,
            }
        ],
    }


class TestLotLayout:
    def test_from_dict(self):
        layout = LotLayout.from_dict(_simple_layout())
        assert layout.name == "Test Lot"
        assert layout.datum.lat == 30.0
        assert layout.datum.lon == -97.0
        assert layout.heading == 0.0
        assert len(layout.elements) == 1

    def test_to_dict_roundtrip(self):
        d = _simple_layout()
        layout = LotLayout.from_dict(d)
        result = layout.to_dict()
        assert result["name"] == d["name"]
        assert result["datum"] == d["datum"]
        assert result["heading"] == d["heading"]
        assert len(result["elements"]) == len(d["elements"])

    def test_from_json(self, tmp_path):
        path = tmp_path / "test.json"
        path.write_text(json.dumps(_simple_layout()))
        layout = LotLayout.from_json(str(path))
        assert layout.name == "Test Lot"

    def test_to_json(self, tmp_path):
        layout = LotLayout.from_dict(_simple_layout())
        path = str(tmp_path / "out.json")
        layout.to_json(path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["name"] == "Test Lot"

    def test_default_heading(self):
        d = _simple_layout()
        del d["heading"]
        layout = LotLayout.from_dict(d)
        assert layout.heading == 0.0

    def test_default_name(self):
        d = _simple_layout()
        del d["name"]
        layout = LotLayout.from_dict(d)
        assert layout.name == "Untitled"


class TestGenerateFromLayout:
    def test_single_row(self):
        layout = LotLayout.from_dict(_simple_layout())
        job = generate_from_layout(layout)
        assert len(job.segments) > 0
        assert job.datum.lat == 30.0

    def test_job_id_from_name(self):
        layout = LotLayout.from_dict(_simple_layout())
        job = generate_from_layout(layout)
        assert job.job_id == "test-lot"

    def test_multi_row_layout(self):
        d = {
            "name": "Two Row Lot",
            "datum": {"lat": 30.0, "lon": -97.0},
            "heading": 45.0,
            "elements": [
                {"type": "parking_row", "origin": [0.0, 0.0], "angle": 0.0, "count": 5},
                {"type": "parking_row", "origin": [0.0, 12.0], "angle": 0.0, "count": 5},
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)
        # Two rows of 5 spaces should produce more segments than one row
        single = generate_from_layout(LotLayout.from_dict(_simple_layout()))
        assert len(job.segments) > len(single.segments)

    def test_with_handicap(self):
        d = {
            "name": "Handicap Row",
            "datum": {"lat": 30.0, "lon": -97.0},
            "heading": 0.0,
            "elements": [
                {
                    "type": "parking_row",
                    "origin": [0.0, 0.0],
                    "angle": 0.0,
                    "count": 5,
                    "handicap": [0, 4],
                },
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)
        assert len(job.segments) > 0

    def test_with_arrows(self):
        d = {
            "name": "Arrows",
            "datum": {"lat": 30.0, "lon": -97.0},
            "heading": 0.0,
            "elements": [
                {"type": "arrow", "origin": [0.0, 0.0], "angle": 90.0},
                {"type": "arrow", "origin": [3.0, 0.0], "angle": 90.0},
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)
        assert len(job.segments) >= 2

    def test_with_crosswalk(self):
        d = {
            "name": "Crosswalk",
            "datum": {"lat": 30.0, "lon": -97.0},
            "heading": 0.0,
            "elements": [
                {"type": "crosswalk", "origin": [0.0, 0.0], "angle": 0.0},
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)
        assert len(job.segments) > 0

    def test_mixed_elements(self):
        d = {
            "name": "Full Lot",
            "datum": {"lat": 30.0, "lon": -97.0},
            "heading": 45.0,
            "elements": [
                {"type": "parking_row", "origin": [0.0, 0.0], "angle": 0.0, "count": 10, "handicap": [0]},
                {"type": "parking_row", "origin": [0.0, 12.0], "angle": 0.0, "count": 10, "handicap": [0, 9]},
                {"type": "arrow", "origin": [13.0, 6.0], "angle": 90.0},
                {"type": "crosswalk", "origin": [-2.0, 6.0], "angle": 0.0},
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)
        assert len(job.segments) > 0
        assert job.metadata["element_count"] == 4
        assert job.metadata["layout_name"] == "Full Lot"

    def test_no_optimize(self):
        layout = LotLayout.from_dict(_simple_layout())
        job_opt = generate_from_layout(layout, optimize=True)
        job_noopt = generate_from_layout(layout, optimize=False)
        # Both should have the same number of segments
        assert len(job_opt.segments) == len(job_noopt.segments)

    def test_empty_layout_raises(self):
        d = {
            "name": "Empty",
            "datum": {"lat": 30.0, "lon": -97.0},
            "elements": [],
        }
        layout = LotLayout.from_dict(d)
        with pytest.raises(ValueError, match="no paint paths"):
            generate_from_layout(layout)

    def test_unknown_element_type_raises(self):
        d = {
            "name": "Bad",
            "datum": {"lat": 30.0, "lon": -97.0},
            "elements": [{"type": "unicorn", "origin": [0, 0]}],
        }
        layout = LotLayout.from_dict(d)
        with pytest.raises(ValueError, match="Unknown element type"):
            generate_from_layout(layout)


class TestWaypointIntegration:
    """End-to-end: layout -> job -> waypoints -> validate."""

    def test_full_pipeline(self):
        from striper_pathgen.mission_planner import export_waypoints
        from striper_pathgen.waypoint_validator import validate_waypoints

        d = {
            "name": "Integration Test",
            "datum": {"lat": 30.2672, "lon": -97.7431},
            "heading": 45.0,
            "elements": [
                {"type": "parking_row", "origin": [0.0, 0.0], "angle": 0.0, "count": 5, "handicap": [0]},
                {"type": "arrow", "origin": [8.0, 3.0], "angle": 90.0},
            ],
        }
        layout = LotLayout.from_dict(d)
        job = generate_from_layout(layout)

        content = export_waypoints(
            job=job,
            datum_lat=layout.datum.lat,
            datum_lon=layout.datum.lon,
            datum_heading=layout.heading,
        )

        result = validate_waypoints(content)
        assert result.ok, f"Validation failed: {result.errors}"
        assert result.stats["paint_segments"] > 0
