"""Tests for striper_pathgen.path_optimizer — path ordering and distance."""

from __future__ import annotations

import math

import pytest

from striper_pathgen.models import PaintPath, Point2D
from striper_pathgen.path_optimizer import (
    calculate_total_transit_distance,
    optimize_path_order,
)


# ── helpers ────────────────────────────────────────────────────────────── #

def _make_path(x1, y1, x2, y2) -> PaintPath:
    return PaintPath(waypoints=[Point2D(x1, y1), Point2D(x2, y2)])


# ══════════════════════════════════════════════════════════════════════════ #
#  calculate_total_transit_distance
# ══════════════════════════════════════════════════════════════════════════ #

class TestCalculateTotalTransitDistance:

    def test_empty_list(self):
        assert calculate_total_transit_distance([]) == 0.0

    def test_single_segment(self):
        assert calculate_total_transit_distance([_make_path(0, 0, 1, 0)]) == 0.0

    def test_two_adjacent_segments(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(1, 0, 2, 0)
        assert math.isclose(calculate_total_transit_distance([a, b]), 0.0)

    def test_two_distant_segments(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(10, 0, 11, 0)
        dist = calculate_total_transit_distance([a, b])
        assert math.isclose(dist, 9.0)

    def test_three_segments(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(5, 0, 6, 0)
        c = _make_path(10, 0, 11, 0)
        dist = calculate_total_transit_distance([a, b, c])
        assert math.isclose(dist, 4.0 + 4.0)

    def test_distance_depends_on_order(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(100, 0, 101, 0)
        c = _make_path(2, 0, 3, 0)
        dist_abc = calculate_total_transit_distance([a, b, c])
        dist_acb = calculate_total_transit_distance([a, c, b])
        # a->b->c is worse than a->c->b.
        assert dist_abc > dist_acb


# ══════════════════════════════════════════════════════════════════════════ #
#  optimize_path_order
# ══════════════════════════════════════════════════════════════════════════ #

class TestOptimizePathOrder:

    def test_empty_list(self):
        result = optimize_path_order([])
        assert result == []

    def test_single_segment(self):
        seg = _make_path(0, 0, 1, 0)
        result = optimize_path_order([seg])
        assert len(result) == 1

    def test_already_optimal(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(1, 0, 2, 0)
        c = _make_path(2, 0, 3, 0)
        result = optimize_path_order([a, b, c])
        dist = calculate_total_transit_distance(result)
        assert math.isclose(dist, 0.0)

    def test_reduces_transit_distance(self, scattered_paths):
        original_dist = calculate_total_transit_distance(scattered_paths)
        optimized = optimize_path_order(scattered_paths)
        optimized_dist = calculate_total_transit_distance(optimized)
        assert optimized_dist < original_dist

    def test_preserves_segment_count(self, scattered_paths):
        optimized = optimize_path_order(scattered_paths)
        assert len(optimized) == len(scattered_paths)

    def test_nearest_neighbor_groups_nearby(self):
        """Segments close together should end up adjacent in the result."""
        paths = [
            _make_path(0, 0, 0, 1),
            _make_path(50, 50, 50, 51),
            _make_path(0.5, 0, 0.5, 1),
            _make_path(50.5, 50, 50.5, 51),
        ]
        result = optimize_path_order(paths)
        dist = calculate_total_transit_distance(result)
        # A naive order might give ~142 total transit.
        # Optimized should be much less (grouping the two clusters).
        assert dist < 80

    def test_two_opt_improvement(self):
        """Construct a case where 2-opt should improve over greedy."""
        # Four paths arranged in a square pattern that greedy might mis-order.
        paths = [
            _make_path(0, 0, 0, 1),
            _make_path(10, 10, 10, 11),
            _make_path(10, 0, 10, 1),
            _make_path(0, 10, 0, 11),
        ]
        result = optimize_path_order(paths)
        dist = calculate_total_transit_distance(result)
        # The best tour visits them in a loop: 0->2->1->3 or similar.
        # Total transit should be about 3 * ~10 = ~30 or better.
        assert dist < 35

    def test_seed_parameter_accepted(self, scattered_paths):
        """The seed parameter should be accepted without error."""
        result = optimize_path_order(scattered_paths, seed=42)
        assert len(result) == len(scattered_paths)

    def test_reversibility_is_used(self):
        """Optimizer should reverse segments when it reduces distance."""
        # Path A ends at (10,0), path B goes from (0,0) to (10,0).
        # Without reversal, transit A->B is 10. With B reversed, transit is 0.
        a = _make_path(0, 0, 10, 0)
        b = _make_path(0, 0, 10, 0)
        result = optimize_path_order([a, b])
        dist = calculate_total_transit_distance(result)
        assert math.isclose(dist, 0.0)

    def test_two_segments(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(1, 0, 2, 0)
        result = optimize_path_order([a, b])
        dist = calculate_total_transit_distance(result)
        assert math.isclose(dist, 0.0)

    def test_three_segments_out_of_order(self):
        a = _make_path(0, 0, 1, 0)
        b = _make_path(4, 0, 5, 0)
        c = _make_path(2, 0, 3, 0)
        result = optimize_path_order([a, b, c])
        dist = calculate_total_transit_distance(result)
        # Optimal order is a -> c -> b with transit 1 + 1 = 2.
        assert dist <= 2.0 + 1e-9

    def test_large_set_does_not_crash(self):
        """Optimizer should handle a moderately large set without errors."""
        import random
        rng = random.Random(123)
        paths = [
            _make_path(rng.uniform(0, 100), rng.uniform(0, 100),
                       rng.uniform(0, 100), rng.uniform(0, 100))
            for _ in range(50)
        ]
        result = optimize_path_order(paths)
        assert len(result) == 50
        # Optimized should be less than the original order.
        orig_dist = calculate_total_transit_distance(paths)
        opt_dist = calculate_total_transit_distance(result)
        assert opt_dist <= orig_dist + 1e-9
