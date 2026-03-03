"""Path ordering optimizer to minimise non-painting transit distance."""

from __future__ import annotations

import random
from typing import Sequence

from .models import PaintPath, Point2D


def _transit_distance(a: PaintPath, b: PaintPath) -> float:
    """Distance from the end of segment *a* to the start of segment *b*."""
    return a.end.distance_to(b.start)


def calculate_total_transit_distance(segments: Sequence[PaintPath]) -> float:
    """Sum of distances between consecutive segment endpoints.

    This is the total distance the robot must travel without painting.
    """
    if len(segments) <= 1:
        return 0.0
    total = 0.0
    for i in range(len(segments) - 1):
        total += segments[i].end.distance_to(segments[i + 1].start)
    return total


def _endpoint_distance(seg_a: PaintPath, seg_b: PaintPath) -> tuple[float, bool, bool]:
    """Return (min_dist, reverse_a, reverse_b) considering direction reversal.

    We check all four endpoint pairings and return the combination that
    gives the shortest transit between the two segments.
    """
    best = seg_a.end.distance_to(seg_b.start)
    ra, rb = False, False

    d = seg_a.end.distance_to(seg_b.end)
    if d < best:
        best, ra, rb = d, False, True

    d = seg_a.start.distance_to(seg_b.start)
    if d < best:
        best, ra, rb = d, True, False

    d = seg_a.start.distance_to(seg_b.end)
    if d < best:
        best, ra, rb = d, True, True

    return best, ra, rb


def _nearest_neighbor_order(segments: list[PaintPath]) -> list[PaintPath]:
    """Greedy nearest-neighbour ordering that also considers reversing segments."""
    if len(segments) <= 1:
        return list(segments)

    remaining = list(segments)
    ordered: list[PaintPath] = [remaining.pop(0)]

    while remaining:
        current = ordered[-1]
        best_idx = 0
        best_dist = float("inf")
        best_reverse_current = False
        best_reverse_next = False

        for i, candidate in enumerate(remaining):
            dist, rev_cur, rev_next = _endpoint_distance(current, candidate)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
                best_reverse_current = rev_cur
                best_reverse_next = rev_next

        if best_reverse_current:
            ordered[-1] = ordered[-1].reversed()

        chosen = remaining.pop(best_idx)
        if best_reverse_next:
            chosen = chosen.reversed()
        ordered.append(chosen)

    return ordered


def _two_opt_improve(segments: list[PaintPath], max_iterations: int = 1000) -> list[PaintPath]:
    """Apply 2-opt local search to improve segment ordering.

    For each pair of edges (i, i+1) and (j, j+1), check if reversing the
    sub-tour between i+1 and j yields a shorter total transit distance.
    Also considers reversing individual segment directions after each swap.
    """
    n = len(segments)
    if n <= 2:
        return segments

    route = list(segments)
    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1
        for i in range(n - 1):
            for j in range(i + 2, n):
                # Current cost of edges (i, i+1) and (j, j+1 if exists).
                cost_before = route[i].end.distance_to(route[i + 1].start)
                if j + 1 < n:
                    cost_before += route[j].end.distance_to(route[j + 1].start)

                # Cost after reversing the sub-route [i+1 .. j].
                # Reversing the sub-route means each segment in that range is
                # also reversed, and their order is flipped.
                new_sub = [seg.reversed() for seg in reversed(route[i + 1 : j + 1])]

                cost_after = route[i].end.distance_to(new_sub[0].start)
                if j + 1 < n:
                    cost_after += new_sub[-1].end.distance_to(route[j + 1].start)

                if cost_after < cost_before - 1e-9:
                    route[i + 1 : j + 1] = new_sub
                    improved = True

    return route


def optimize_path_order(segments: list[PaintPath], seed: int | None = None) -> list[PaintPath]:
    """Optimise the order (and direction) of paint segments.

    Strategy:
        1. Nearest-neighbour greedy construction.
        2. 2-opt local search improvement.

    Args:
        segments: Unordered paint paths.
        seed: Optional random seed (reserved for future randomised restarts).

    Returns:
        A reordered (and possibly direction-reversed) list of PaintPaths that
        minimises total transit distance.
    """
    if seed is not None:
        random.seed(seed)

    if len(segments) <= 1:
        return list(segments)

    ordered = _nearest_neighbor_order(segments)
    ordered = _two_opt_improve(ordered)
    return ordered
