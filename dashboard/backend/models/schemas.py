"""Pydantic models for the striping robot dashboard API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RobotState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ESTOPPED = "estopped"
    ERROR = "error"
    DISCONNECTED = "disconnected"


# --- GeoJSON / Path models ---

class GeoPoint(BaseModel):
    lat: float
    lng: float


class PathPreview(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict[str, Any]] = Field(default_factory=list)


class PathUploadResponse(BaseModel):
    filename: str
    path_count: int
    bounds: Optional[dict[str, Any]] = None
    geojson: PathPreview


class TemplateType(str, Enum):
    STANDARD = "standard"
    ANGLED_60 = "angled_60"
    ANGLED_45 = "angled_45"
    HANDICAP = "handicap"
    COMPACT = "compact"


class TemplateRequest(BaseModel):
    template_type: TemplateType = TemplateType.STANDARD
    origin: GeoPoint
    angle: float = 0.0
    count: int = 10
    spacing_ft: float = 9.0
    length_ft: float = 18.0
    include_end_lines: bool = True


class TemplateResponse(BaseModel):
    template_type: TemplateType
    line_count: int
    geojson: PathPreview


# --- Job models ---

class JobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    path_data: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class JobUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[JobStatus] = None
    path_data: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class JobResponse(BaseModel):
    id: int
    name: str
    status: JobStatus
    created_at: str
    updated_at: str
    path_data: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


# --- Robot models ---

class RobotStatus(BaseModel):
    state: RobotState = RobotState.DISCONNECTED
    position: Optional[GeoPoint] = None
    speed: float = 0.0
    heading: float = 0.0
    battery: float = 100.0
    paint_level: float = 100.0
    gps_accuracy: float = 0.0
    current_job_id: Optional[int] = None
    job_progress: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
