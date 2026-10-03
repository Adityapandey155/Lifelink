from datetime import datetime
from sqlalchemy.orm import Session
from . import models
from .compatibility import compatible_donor_groups
from .geo import haversine_km, estimate_travel_minutes

ACTIVE_RESPONSE_STATUSES = ["RESPONDED", "CONTACTED", "CONFIRMED", "DONATING"]
RADIUS_STEPS = [5, 10, 20]


def _base_compatible_query(db: Session, request: models.BloodRequest):
    groups = compatible_donor_groups(request.blood_group)
    return db.query(models.User).filter(
        models.User.is_donor.is_(True),          # must be a REGISTERED donor
        models.User.blood_group.in_(groups),
        models.User.is_blocked.is_(False),
        models.User.latitude.isnot(None),
        models.User.longitude.isnot(None),
    )


def _within_radius(request: models.BloodRequest, query, radius_km: float):
    now = datetime.utcnow()
    results = []
    for donor in query.all():
        is_avail = donor.is_available and not (
            donor.availability_expires_at and donor.availability_expires_at < now
        )
        dist = haversine_km(request.latitude, request.longitude, donor.latitude, donor.longitude)
        if dist is None or dist > radius_km:
            continue
        results.append({
            "donor": donor,
            "distance_km": round(dist, 2),
            "eta_minutes": estimate_travel_minutes(dist),
            "is_available": is_avail,
        })
    return results


def find_all_compatible_donors(db: Session, request: models.BloodRequest, radius_km: float = None):
    """
    ALL registered donors who are blood-compatible and within radius,
    regardless of current availability. Used for notifications + 'Potential Donors Found'.
    """
    radius = radius_km if radius_km is not None else request.search_radius_km
    query = _base_compatible_query(db, request)
    results = _within_radius(request, query, radius)
    priority_weight = {"CRITICAL": 0, "URGENT": 1, "NORMAL": 2}.get(request.priority, 2)
    results.sort(key=lambda c: (not c["is_available"], c["distance_km"], priority_weight))
    return results


def find_available_matches(db: Session, request: models.BloodRequest, radius_km: float = None):
    """
    Donors who are currently 'Ready to Donate' AND not already committed elsewhere.
    Used for 'Available & Compatible' stat + donation eligibility.
    """
    all_compatible = find_all_compatible_donors(db, request, radius_km)
    available = []
    for c in all_compatible:
        if not c["is_available"]:
            continue
        already_active = db.query(models.DonationResponse).filter(
            models.DonationResponse.donor_id == c["donor"].id,
            models.DonationResponse.status.in_(ACTIVE_RESPONSE_STATUSES),
            models.DonationResponse.request_id != request.id,
        ).first()
        if already_active:
            continue
        available.append(c)
    return available


# Backward-compatible alias (some code may still reference find_matches)
find_matches = find_available_matches


def progressive_search(db: Session, request: models.BloodRequest, min_needed: int = 3):
    """Expand 5km -> 10km -> 20km based on currently AVAILABLE donor count."""
    matches, radius = [], RADIUS_STEPS[0]
    for r in RADIUS_STEPS:
        matches = find_available_matches(db, request, r)
        radius = r
        if len(matches) >= min_needed:
            break
    return matches, radius