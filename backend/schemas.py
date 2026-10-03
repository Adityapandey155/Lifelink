from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from .compatibility import BLOOD_GROUPS


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=6)
    register_as_donor: bool = False
    register_as_hospital: bool = False
    blood_group: Optional[str] = None
    dob: Optional[date] = None
    city: Optional[str] = None
    photo_url: Optional[str] = None
    consent_notifications: bool = True
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: str
    blood_group: Optional[str] = None
    role: str
    is_donor: bool                       # ✅ NEW
    city: Optional[str] = None
    dob: Optional[date] = None
    photo_url: Optional[str] = None
    is_available: bool
    availability_expires_at: Optional[datetime] = None
    consent_notifications: bool
    is_verified_email: bool
    is_verified_phone: bool
    has_location: Optional[bool] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Users ----------
class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


class AvailabilityUpdate(BaseModel):
    is_available: bool
    duration: str = "now"  # now | 1h | 3h | today


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    photo_url: Optional[str] = None
    consent_notifications: Optional[bool] = None


# ---------- Hospitals ----------
class HospitalCreate(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HospitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: Optional[str]
    verification_status: str
    admin_notes: Optional[str] = None
    created_at: datetime


# ---------- Requests ----------
class RequestCreate(BaseModel):
    blood_group: str
    units_required: int = Field(ge=1, le=20)
    priority: str  # CRITICAL | URGENT | NORMAL
    hospital_name: str
    contact_person: str
    contact_phone: str
    latitude: float
    longitude: float
    description: Optional[str] = None
    required_by: Optional[datetime] = None


class RequestStatusUpdate(BaseModel):
    status: str


class DonateConfirm(BaseModel):
    confirm: bool


class DonationStatusUpdate(BaseModel):
    status: str  # CONTACTED | CONFIRMED | DONATING | FULFILLED | CANCELLED


class ReportCreate(BaseModel):
    reported_user_id: Optional[int] = None
    reported_request_id: Optional[int] = None
    reason: str

class BecomeDonorRequest(BaseModel):
    blood_group: str
    dob: Optional[date] = None
    city: Optional[str] = None