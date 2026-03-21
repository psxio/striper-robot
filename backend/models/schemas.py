"""Pydantic v2 request/response models for the Strype Cloud API."""

import re
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Any, Literal


def validate_password_complexity(password: str) -> str:
    """Require at least 1 letter and 1 digit."""
    if not re.search(r'[a-zA-Z]', password):
        raise ValueError('Password must contain at least one letter')
    if not re.search(r'\d', password):
        raise ValueError('Password must contain at least one digit')
    return password


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(default="", max_length=100)

    @field_validator('password')
    @classmethod
    def check_password(cls, v):
        return validate_password_complexity(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    plan: str
    active_lot_id: Optional[str] = None
    active_organization_id: Optional[str] = None
    map_state: Optional[dict] = None  # {lat, lng, zoom}
    limits: Optional[dict] = None  # {max_lots, max_jobs}
    email_verified: bool = False
    organizations: Optional[list[dict]] = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# --- Password Reset ---

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    @field_validator('new_password')
    @classmethod
    def check_password(cls, v):
        return validate_password_complexity(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator('new_password')
    @classmethod
    def check_password(cls, v):
        return validate_password_complexity(v)


# --- Profile ---

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    company_name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=30)


class DeleteAccountRequest(BaseModel):
    password: str


# --- Lots ---

class LotCenter(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class LotCreate(BaseModel):
    name: str = Field(max_length=200)
    center: LotCenter
    zoom: int = Field(default=18, ge=0, le=22)
    features: list[Any] = Field(default=[], max_length=10000)


class LotUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    center: Optional[LotCenter] = None
    zoom: Optional[int] = Field(default=None, ge=0, le=22)
    features: Optional[list[Any]] = Field(default=None, max_length=10000)


class LotResponse(BaseModel):
    id: str
    name: str
    center: LotCenter
    zoom: int
    features: list[Any]
    created: str   # ISO datetime
    modified: str  # ISO datetime -- NOT "updated_at"


class PaginatedLotResponse(BaseModel):
    items: list[LotResponse]
    total: int
    page: int
    limit: int


# --- Jobs ---

class JobCreate(BaseModel):
    lotId: str
    date: str
    time_preference: Optional[Literal["morning", "afternoon", "evening"]] = "morning"

    @field_validator('date')
    @classmethod
    def check_date(cls, v):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError('Invalid date format')
        return v


class JobUpdate(BaseModel):
    status: Optional[Literal["pending", "in_progress", "completed"]] = None
    date: Optional[str] = None

    @field_validator('date')
    @classmethod
    def check_date(cls, v):
        if v is not None:
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError('Invalid date format')
        return v


class JobResponse(BaseModel):
    id: str
    lotId: str
    date: str
    status: str
    time_preference: Optional[str] = "morning"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    robot_id: Optional[str] = None
    created: str
    modified: str


class PaginatedJobResponse(BaseModel):
    items: list[JobResponse]
    total: int
    page: int
    limit: int


# --- Waitlist ---

class WaitlistRequest(BaseModel):
    email: EmailStr
    source: str = "landing"


# --- User Preferences ---

class MapState(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zoom: int = Field(ge=0, le=22)


class UserPreferencesUpdate(BaseModel):
    active_lot_id: Optional[str] = None
    map_state: Optional[MapState] = None


# --- Robots ---

class RobotCreate(BaseModel):
    serial_number: str = Field(max_length=100)
    hardware_version: str = Field(default="v1", max_length=20)
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    notes: str = Field(default="", max_length=1000)


class RobotUpdate(BaseModel):
    status: Optional[Literal["available", "assigned", "shipped", "maintenance", "retired"]] = None
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=1000)


class RobotResponse(BaseModel):
    id: str
    serial_number: str
    status: str
    hardware_version: str
    firmware_version: Optional[str] = None
    last_seen_at: Optional[str] = None
    last_battery_pct: Optional[int] = None
    last_state: Optional[str] = None
    notes: str
    created_at: str
    updated_at: str


class AssignRobotRequest(BaseModel):
    robot_id: str
    user_id: str


class AssignmentUpdate(BaseModel):
    status: Optional[Literal["preparing", "shipped", "active", "returning", "returned"]] = None
    tracking_number: Optional[str] = Field(default=None, max_length=200)
    return_tracking: Optional[str] = Field(default=None, max_length=200)


class AssignmentResponse(BaseModel):
    id: str
    robot_id: str
    user_id: str
    status: str
    tracking_number: Optional[str] = None
    shipped_at: Optional[str] = None
    delivered_at: Optional[str] = None
    return_tracking: Optional[str] = None
    returned_at: Optional[str] = None
    label_url: Optional[str] = None
    return_label_url: Optional[str] = None
    created_at: str
    updated_at: str
    # Joined fields
    serial_number: Optional[str] = None
    user_email: Optional[str] = None


# --- Recurring Schedules ---

class ScheduleCreate(BaseModel):
    lot_id: str
    frequency: Literal["weekly", "biweekly", "monthly"]
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    time_preference: Literal["morning", "afternoon", "evening"] = "morning"


class ScheduleUpdate(BaseModel):
    frequency: Optional[Literal["weekly", "biweekly", "monthly"]] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    time_preference: Optional[Literal["morning", "afternoon", "evening"]] = None
    active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: str
    lot_id: str
    frequency: str
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    time_preference: str
    active: bool
    next_run: str
    created_at: str
    updated_at: str


# --- Cost Estimates ---

class EstimateRequest(BaseModel):
    features: list[Any] = Field(default=[])


class EstimateResponse(BaseModel):
    total_line_length_ft: float
    paint_gallons: float
    estimated_runtime_min: int
    estimated_cost: float


# --- Admin ---

class SetPlanRequest(BaseModel):
    plan: Literal["free", "pro", "robot", "enterprise"]


# --- Telemetry ---

class TelemetryHeartbeat(BaseModel):
    battery_pct: Optional[int] = Field(default=None, ge=0, le=100)
    lat: Optional[float] = None
    lng: Optional[float] = None
    state: Optional[Literal["idle", "mowing", "painting", "transit", "error", "charging"]] = None
    paint_level_pct: Optional[int] = Field(default=None, ge=0, le=100)
    error_code: Optional[str] = None
    rssi: Optional[int] = None


class TelemetryResponse(BaseModel):
    battery_pct: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    state: Optional[str] = None
    paint_level_pct: Optional[int] = None
    error_code: Optional[str] = None
    rssi: Optional[int] = None
    created_at: str


# --- Billing ---

class ChangePlanRequest(BaseModel):
    plan: Literal["free", "pro", "robot", "enterprise"]
