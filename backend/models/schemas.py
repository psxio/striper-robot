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
    map_state: Optional[dict] = None  # {lat, lng, zoom}
    limits: Optional[dict] = None  # {max_lots, max_jobs}


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

    @field_validator('date')
    @classmethod
    def check_date(cls, v):
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError('Invalid date format')
        return v


class JobUpdate(BaseModel):
    status: Optional[Literal["pending", "completed"]] = None
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

class UserPreferencesUpdate(BaseModel):
    active_lot_id: Optional[str] = None
    map_state: Optional[dict] = None  # {lat, lng, zoom}
