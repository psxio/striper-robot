"""Core data models for the striper_pathgen package."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Point2D:
    """A 2D point in local coordinates (meters)."""

    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        """Euclidean distance to another point."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> Point2D:
        return cls(x=d["x"], y=d["y"])


@dataclass
class GeoPoint:
    """A GPS coordinate."""

    lat: float
    lon: float
    alt: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lon": self.lon, "alt": self.alt}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> GeoPoint:
        return cls(lat=d["lat"], lon=d["lon"], alt=d.get("alt", 0.0))


@dataclass
class PaintPath:
    """A path the robot follows while painting.

    Attributes:
        waypoints: Ordered list of 2D waypoints defining the path.
        line_width: Width of the painted line in meters (default 0.1 m / ~4 in).
        color: Paint color name (default "white").
        speed: Target travel speed in m/s while painting (default 0.5).
    """

    waypoints: list[Point2D]
    line_width: float = 0.1
    color: str = "white"
    speed: float = 0.5

    @property
    def start(self) -> Point2D:
        """First waypoint."""
        return self.waypoints[0]

    @property
    def end(self) -> Point2D:
        """Last waypoint."""
        return self.waypoints[-1]

    @property
    def length(self) -> float:
        """Total path length in meters."""
        total = 0.0
        for i in range(len(self.waypoints) - 1):
            total += self.waypoints[i].distance_to(self.waypoints[i + 1])
        return total

    def reversed(self) -> PaintPath:
        """Return a copy of this path with waypoints in reverse order."""
        return PaintPath(
            waypoints=list(reversed(self.waypoints)),
            line_width=self.line_width,
            color=self.color,
            speed=self.speed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "waypoints": [p.to_dict() for p in self.waypoints],
            "line_width": self.line_width,
            "color": self.color,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaintPath:
        return cls(
            waypoints=[Point2D.from_dict(p) for p in d["waypoints"]],
            line_width=d.get("line_width", 0.1),
            color=d.get("color", "white"),
            speed=d.get("speed", 0.5),
        )


@dataclass
class TransitPath:
    """A non-painting movement between paint segments."""

    waypoints: list[Point2D]

    @property
    def length(self) -> float:
        total = 0.0
        for i in range(len(self.waypoints) - 1):
            total += self.waypoints[i].distance_to(self.waypoints[i + 1])
        return total

    def to_dict(self) -> dict[str, Any]:
        return {"waypoints": [p.to_dict() for p in self.waypoints]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TransitPath:
        return cls(waypoints=[Point2D.from_dict(p) for p in d["waypoints"]])


@dataclass
class PaintSegment:
    """A paint path together with its index in the overall job."""

    path: PaintPath
    index: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path.to_dict(), "index": self.index}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaintSegment:
        return cls(path=PaintPath.from_dict(d["path"]), index=d["index"])


@dataclass
class PaintJob:
    """A complete painting job specification.

    Attributes:
        job_id: Unique identifier for this job.
        segments: Ordered list of paint segments to execute.
        datum: GPS reference point for local coordinate origin.
        metadata: Arbitrary metadata (e.g. customer name, lot id).
    """

    job_id: str
    segments: list[PaintSegment]
    datum: GeoPoint
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        segments: list[PaintSegment],
        datum: GeoPoint,
        metadata: dict[str, Any] | None = None,
    ) -> PaintJob:
        """Create a new PaintJob with an auto-generated UUID."""
        return cls(
            job_id=str(uuid.uuid4()),
            segments=segments,
            datum=datum,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "segments": [s.to_dict() for s in self.segments],
            "datum": self.datum.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaintJob:
        return cls(
            job_id=d["job_id"],
            segments=[PaintSegment.from_dict(s) for s in d["segments"]],
            datum=GeoPoint.from_dict(d["datum"]),
            metadata=d.get("metadata", {}),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> PaintJob:
        return cls.from_dict(json.loads(text))
