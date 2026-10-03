from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    role = Column(String, default="user")  # user | admin
    city = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    photo_url = Column(String, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geohash = Column(String, nullable=True)

    consent_notifications = Column(Boolean, default=True)
    is_available = Column(Boolean, default=False)
    is_donor = Column(Boolean, default=False)
    availability_expires_at = Column(DateTime, nullable=True)

    is_blocked = Column(Boolean, default=False)
    is_verified_email = Column(Boolean, default=False)
    is_verified_phone = Column(Boolean, default=False)

    last_request_created_at = Column(DateTime, nullable=True)
    is_demo = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    verification_status = Column(String, default="pending")  # pending|approved|rejected|suspended
    admin_notes = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)

    blood_group = Column(String, nullable=True)     # ✅ new — not everyone is a donor
    units_required = Column(Integer, default=1)
    priority = Column(String, default="NORMAL")  # CRITICAL|URGENT|NORMAL

    hospital_name = Column(String, nullable=False)
    contact_person = Column(String, nullable=False)
    contact_phone = Column(String, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    required_by = Column(DateTime, nullable=True)
    status = Column(String, default="OPEN")
    search_radius_km = Column(Float, default=5)
    matching_active = Column(Boolean, default=True)
    is_verified_request = Column(Boolean, default=False)
    fulfilled_units = Column(Integer, default=0)
    is_demo = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class DonationResponse(Base):
    __tablename__ = "donation_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=False)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="RESPONDED")
    contact_shared = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=True)
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reported_request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String, default="OPEN")  # OPEN|REVIEWED|DISMISSED|ACTIONED
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)