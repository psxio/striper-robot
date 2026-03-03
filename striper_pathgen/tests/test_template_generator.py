"""Tests for striper_pathgen.template_generator — template geometry generation."""

from __future__ import annotations

import math

import pytest

from striper_pathgen.models import PaintPath, Point2D
from striper_pathgen.template_generator import (
    generate_arrow,
    generate_crosswalk,
    generate_handicap_space,
    generate_parking_row,
    generate_standard_space,
)


# ── helpers ────────────────────────────────────────────────────────────── #

def _path_bounds(paths: list[PaintPath]):
    """Return (min_x, min_y, max_x, max_y) over all waypoints."""
    xs = [p.x for path in paths for p in path.waypoints]
    ys = [p.y for path in paths for p in path.waypoints]
    return min(xs), min(ys), max(xs), max(ys)


def _approx(a: float, b: float, tol: float = 0.05) -> bool:
    return abs(a - b) < tol


# ══════════════════════════════════════════════════════════════════════════ #
#  generate_standard_space
# ══════════════════════════════════════════════════════════════════════════ #

class TestGenerateStandardSpace:

    def test_returns_two_paths(self):
        paths = generate_standard_space(Point2D(0, 0), angle=0)
        assert len(paths) == 2

    def test_default_dimensions(self):
        paths = generate_standard_space(Point2D(0, 0), angle=0)
        min_x, min_y, max_x, max_y = _path_bounds(paths)
        # Width ~2.7 m, length ~5.5 m (with small floating-point tolerance)
        assert _approx(max_x - min_x, 2.7)
        assert _approx(max_y - min_y, 5.5)

    def test_custom_dimensions(self):
        paths = generate_standard_space(
            Point2D(0, 0), angle=0, width=3.0, length=6.0
        )
        min_x, _, max_x, max_y = _path_bounds(paths)
        assert _approx(max_x - min_x, 3.0)
        assert _approx(max_y, 6.0, tol=0.1)

    def test_rotation_90(self):
        paths = generate_standard_space(Point2D(0, 0), angle=90)
        # After 90-degree CCW rotation, the space should be sideways.
        min_x, min_y, max_x, max_y = _path_bounds(paths)
        # Height and width swap (approximately).
        assert _approx(max_x - min_x, 5.5, tol=0.2)
        assert _approx(max_y - min_y, 2.7, tol=0.2)

    def test_origin_offset(self):
        ox, oy = 10.0, 20.0
        paths = generate_standard_space(Point2D(ox, oy), angle=0)
        min_x, min_y, _, _ = _path_bounds(paths)
        # Origin should shift the bounding box.
        assert min_x >= ox - 0.1
        assert min_y >= oy - 0.1

    def test_color_parameter(self):
        paths = generate_standard_space(Point2D(0, 0), angle=0, color="yellow")
        for p in paths:
            assert p.color == "yellow"

    def test_line_width_parameter(self):
        paths = generate_standard_space(
            Point2D(0, 0), angle=0, line_width=0.2
        )
        for p in paths:
            assert p.line_width == 0.2

    def test_each_path_has_two_waypoints(self):
        paths = generate_standard_space(Point2D(0, 0), angle=0)
        for p in paths:
            assert len(p.waypoints) == 2

    def test_lines_are_parallel_vertical(self):
        """At angle=0 the two lines should both be vertical (constant x)."""
        paths = generate_standard_space(Point2D(0, 0), angle=0)
        for p in paths:
            assert _approx(p.waypoints[0].x, p.waypoints[1].x, tol=1e-9)


# ══════════════════════════════════════════════════════════════════════════ #
#  generate_handicap_space
# ══════════════════════════════════════════════════════════════════════════ #

class TestGenerateHandicapSpace:

    def test_returns_more_paths_than_standard(self):
        handicap = generate_handicap_space(Point2D(0, 0), angle=0)
        standard = generate_standard_space(Point2D(0, 0), angle=0)
        # Handicap has boundary + aisle + cross-hatching + symbol.
        assert len(handicap) > len(standard)

    def test_has_cross_hatching(self):
        paths = generate_handicap_space(Point2D(0, 0), angle=0)
        # At least 3 boundary lines + some hatch lines + 1 circle = > 4
        assert len(paths) >= 5

    def test_default_color_is_blue(self):
        paths = generate_handicap_space(Point2D(0, 0), angle=0)
        for p in paths:
            assert p.color == "blue"

    def test_custom_color(self):
        paths = generate_handicap_space(Point2D(0, 0), angle=0, color="white")
        for p in paths:
            assert p.color == "white"

    def test_default_width_is_wider(self):
        paths = generate_handicap_space(Point2D(0, 0), angle=0)
        min_x, _, max_x, _ = _path_bounds(paths)
        # Default handicap width is 3.6 m, standard is 2.7 m.
        assert (max_x - min_x) > 3.0

    def test_wheelchair_symbol_path_is_circular(self):
        """The last path should be the wheelchair symbol (25 waypoints)."""
        paths = generate_handicap_space(Point2D(0, 0), angle=0)
        symbol = paths[-1]
        # The circle has num_pts+1 = 25 waypoints.
        assert len(symbol.waypoints) == 25

    def test_rotation_preserves_path_count(self):
        paths_0 = generate_handicap_space(Point2D(0, 0), angle=0)
        paths_45 = generate_handicap_space(Point2D(0, 0), angle=45)
        assert len(paths_0) == len(paths_45)

    def test_cross_hatch_count(self):
        """Cross-hatching should produce approximately length / spacing lines."""
        length = 5.5
        hatch_spacing = 0.6
        expected_min = int(length / hatch_spacing) - 1
        paths = generate_handicap_space(Point2D(0, 0), angle=0, length=length)
        # 3 boundary lines + hatches + 1 symbol
        num_hatches = len(paths) - 3 - 1
        assert num_hatches >= expected_min


# ══════════════════════════════════════════════════════════════════════════ #
#  generate_parking_row
# ══════════════════════════════════════════════════════════════════════════ #

class TestGenerateParkingRow:

    def test_single_space(self):
        paths = generate_parking_row(Point2D(0, 0), angle=0, count=1)
        # 1 standard space = 2 lines
        assert len(paths) == 2

    def test_multiple_spaces(self):
        paths = generate_parking_row(Point2D(0, 0), angle=0, count=5)
        # Each standard space produces 2 lines => 5 * 2 = 10
        assert len(paths) == 10

    def test_with_handicap(self):
        paths_normal = generate_parking_row(Point2D(0, 0), angle=0, count=3)
        paths_handicap = generate_parking_row(
            Point2D(0, 0), angle=0, count=3, handicap_indices=[1]
        )
        # The handicap space has more paths than a standard one.
        assert len(paths_handicap) > len(paths_normal)

    def test_all_handicap(self):
        paths = generate_parking_row(
            Point2D(0, 0), angle=0, count=2, handicap_indices=[0, 1]
        )
        # Should have no standard spaces.
        all_blue = all(p.color == "blue" for p in paths)
        assert all_blue

    def test_handicap_color(self):
        paths = generate_parking_row(
            Point2D(0, 0), angle=0, count=2,
            handicap_indices=[0], handicap_color="red",
        )
        # At least some paths should be red (from the handicap space).
        has_red = any(p.color == "red" for p in paths)
        assert has_red

    def test_spacing(self):
        paths = generate_parking_row(
            Point2D(0, 0), angle=0, count=3, spacing=3.0
        )
        # 3 spaces produce 3*spacing = 9.0 m total width (dividers at 0, 3, 6, 9).
        min_x, _, max_x, _ = _path_bounds(paths)
        assert _approx(max_x - min_x, 9.0, tol=0.2)

    def test_rotation(self):
        paths = generate_parking_row(Point2D(0, 0), angle=45, count=2)
        assert len(paths) > 0  # Smoke test that it does not crash.


# ══════════════════════════════════════════════════════════════════════════ #
#  generate_arrow
# ══════════════════════════════════════════════════════════════════════════ #

class TestGenerateArrow:

    @pytest.mark.parametrize("arrow_type", ["straight", "left", "right", "u_turn"])
    def test_valid_types(self, arrow_type):
        paths = generate_arrow(Point2D(0, 0), angle=0, arrow_type=arrow_type)
        assert len(paths) >= 2

    def test_straight_has_three_paths(self):
        paths = generate_arrow(Point2D(0, 0), angle=0, arrow_type="straight")
        assert len(paths) == 3

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown arrow_type"):
            generate_arrow(Point2D(0, 0), angle=0, arrow_type="diagonal")

    def test_color_parameter(self):
        paths = generate_arrow(
            Point2D(0, 0), angle=0, arrow_type="straight", color="yellow"
        )
        for p in paths:
            assert p.color == "yellow"

    def test_rotation_changes_waypoints(self):
        p0 = generate_arrow(Point2D(0, 0), angle=0, arrow_type="straight")
        p90 = generate_arrow(Point2D(0, 0), angle=90, arrow_type="straight")
        # The last waypoint of the first path should differ after rotation.
        # (First waypoints may both be at the origin.)
        wp0 = p0[0].waypoints[-1]
        wp90 = p90[0].waypoints[-1]
        assert not (
            _approx(wp0.x, wp90.x, tol=1e-6)
            and _approx(wp0.y, wp90.y, tol=1e-6)
        )

    def test_u_turn_has_five_paths(self):
        paths = generate_arrow(Point2D(0, 0), angle=0, arrow_type="u_turn")
        assert len(paths) == 5

    def test_line_width_parameter(self):
        paths = generate_arrow(
            Point2D(0, 0), angle=0, arrow_type="left", line_width=0.05
        )
        for p in paths:
            assert p.line_width == 0.05


# ══════════════════════════════════════════════════════════════════════════ #
#  generate_crosswalk
# ══════════════════════════════════════════════════════════════════════════ #

class TestGenerateCrosswalk:

    def test_stripe_count_default(self):
        paths = generate_crosswalk(Point2D(0, 0), angle=0)
        # width=3.0, stripe_width=0.3, gap=0.3 => 3.0 / 0.6 = 5 stripes
        assert len(paths) == 5

    def test_stripe_count_custom(self):
        paths = generate_crosswalk(
            Point2D(0, 0), angle=0, width=2.4, stripe_width=0.3, gap=0.3
        )
        # 2.4 / 0.6 = 4 stripes
        assert len(paths) == 4

    def test_stripe_line_width_matches_stripe_width(self):
        stripe_w = 0.4
        paths = generate_crosswalk(
            Point2D(0, 0), angle=0, stripe_width=stripe_w
        )
        for p in paths:
            assert _approx(p.line_width, stripe_w)

    def test_each_stripe_has_two_waypoints(self):
        paths = generate_crosswalk(Point2D(0, 0), angle=0)
        for p in paths:
            assert len(p.waypoints) == 2

    def test_stripe_length_matches_crosswalk_length(self):
        length = 8.0
        paths = generate_crosswalk(Point2D(0, 0), angle=0, length=length)
        for p in paths:
            assert _approx(p.length, length, tol=0.1)

    def test_color_parameter(self):
        paths = generate_crosswalk(Point2D(0, 0), angle=0, color="yellow")
        for p in paths:
            assert p.color == "yellow"

    def test_rotation(self):
        paths_0 = generate_crosswalk(Point2D(0, 0), angle=0)
        paths_90 = generate_crosswalk(Point2D(0, 0), angle=90)
        # Same number of stripes regardless of rotation.
        assert len(paths_0) == len(paths_90)
        # But the waypoints should differ.
        assert paths_0[0].waypoints[0] != paths_90[0].waypoints[0]

    def test_no_stripes_if_width_too_small(self):
        paths = generate_crosswalk(
            Point2D(0, 0), angle=0, width=0.1, stripe_width=0.3
        )
        # 0.1 < 0.3, so no stripe can fit.
        assert len(paths) == 0

    def test_single_stripe(self):
        paths = generate_crosswalk(
            Point2D(0, 0), angle=0, width=0.3, stripe_width=0.3, gap=0.3
        )
        assert len(paths) == 1
