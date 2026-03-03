"""Parse and generate missions from parking lot layout definitions.

A lot layout is a JSON file describing the complete set of markings for a
parking lot.  It supports multiple rows of spaces at different positions and
angles, plus standalone elements like arrows and crosswalks.

Example layout JSON::

    {
        "name": "Main Street Lot",
        "datum": {"lat": 30.2672, "lon": -97.7431},
        "heading": 45.0,
        "elements": [
            {
                "type": "parking_row",
                "origin": [0.0, 0.0],
                "angle": 0.0,
                "count": 10,
                "spacing": 2.7432,
                "length": 5.4864,
                "handicap": [0]
            },
            {
                "type": "parking_row",
                "origin": [0.0, 12.0],
                "angle": 0.0,
                "count": 10,
                "spacing": 2.7432,
                "length": 5.4864,
                "handicap": [0, 9]
            },
            {
                "type": "arrow",
                "origin": [13.0, 6.0],
                "angle": 90.0
            },
            {
                "type": "crosswalk",
                "origin": [-2.0, 6.0],
                "angle": 0.0
            }
        ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .models import GeoPoint, PaintJob, PaintPath, PaintSegment, Point2D
from .path_optimizer import optimize_path_order
from .template_generator import (
    generate_arrow,
    generate_crosswalk,
    generate_parking_row,
    generate_standard_space,
    generate_handicap_space,
)


@dataclass
class LotLayout:
    """A complete parking lot layout definition."""

    name: str
    datum: GeoPoint
    heading: float
    elements: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LotLayout:
        datum_d = d["datum"]
        return cls(
            name=d.get("name", "Untitled"),
            datum=GeoPoint(lat=datum_d["lat"], lon=datum_d["lon"]),
            heading=d.get("heading", 0.0),
            elements=d.get("elements", []),
        )

    @classmethod
    def from_json(cls, path: str) -> LotLayout:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "datum": {"lat": self.datum.lat, "lon": self.datum.lon},
            "heading": self.heading,
            "elements": self.elements,
        }

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


def generate_from_layout(layout: LotLayout, optimize: bool = True) -> PaintJob:
    """Generate a PaintJob from a LotLayout definition.

    Args:
        layout: The lot layout describing all marking elements.
        optimize: If True, optimize path ordering to minimize transit distance.

    Returns:
        A PaintJob ready for export to waypoints or GeoJSON.
    """
    all_paths: list[PaintPath] = []

    for elem in layout.elements:
        elem_type = elem["type"]
        origin = Point2D(
            elem.get("origin", [0.0, 0.0])[0],
            elem.get("origin", [0.0, 0.0])[1],
        )
        angle = elem.get("angle", 0.0)

        if elem_type == "parking_row":
            paths = generate_parking_row(
                origin=origin,
                angle=angle,
                count=elem.get("count", 1),
                spacing=elem.get("spacing", 2.7432),
                length=elem.get("length", 5.4864),
                handicap_indices=elem.get("handicap", []),
            )
            all_paths.extend(paths)

        elif elem_type == "standard_space":
            count = elem.get("count", 1)
            spacing = elem.get("spacing", 2.7)
            for i in range(count):
                space_origin = Point2D(origin.x + i * spacing, origin.y)
                paths = generate_standard_space(origin=space_origin, angle=angle)
                all_paths.extend(paths)

        elif elem_type == "handicap_space":
            count = elem.get("count", 1)
            spacing = elem.get("spacing", 3.6)
            for i in range(count):
                space_origin = Point2D(origin.x + i * spacing, origin.y)
                paths = generate_handicap_space(origin=space_origin, angle=angle)
                all_paths.extend(paths)

        elif elem_type == "arrow":
            paths = generate_arrow(origin=origin, angle=angle)
            all_paths.extend(paths)

        elif elem_type == "crosswalk":
            paths = generate_crosswalk(origin=origin, angle=angle)
            all_paths.extend(paths)

        else:
            raise ValueError(f"Unknown element type: {elem_type!r}")

    if not all_paths:
        raise ValueError("Layout produced no paint paths")

    if optimize:
        all_paths = optimize_path_order(all_paths)

    segments = [PaintSegment(path=p, index=i) for i, p in enumerate(all_paths)]
    job = PaintJob(
        job_id=layout.name.lower().replace(" ", "-"),
        segments=segments,
        datum=layout.datum,
        metadata={
            "source": "lot_layout",
            "layout_name": layout.name,
            "element_count": len(layout.elements),
        },
    )
    return job
