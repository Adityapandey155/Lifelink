from datetime import datetime, timedelta, time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, deps, matching
from ..database import get_db
from ..geo import geohash_encode, haversine_km
from ..compatibility import compatible_donor_groups, BLOOD_GROUPS

router = APIRouter(prefix="/api/users", tags=["users"])


@router.patch("/me", response_model=schemas.UserOut)
def update_profile(payload: schemas.ProfileUpdate, db: Session = Depends(get_db),
                    current: models.User = Depends(deps.get_current_user)):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current, field, value)
    db.commit()
    db.refresh(current)
    out = schemas.UserOut.model_validate(current)
    out.has_location = current.latitude is not None
    return out


@router.patch("/me/become-donor", response_model=schemas.UserOut)
def become_donor(payload: schemas.BecomeDonorRequest, db: Session = Depends(get_db),
                  current: models.User = Depends(deps.get_current_user)):
    if payload.blood_group not in BLOOD_GROUPS:
        raise HTTPException(400, "Invalid blood group")
    current.is_donor = True
    current.blood_group = payload.blood_group
    if payload.dob:
        current.dob = payload.dob
    if payload.city:
        current.city = payload.city
    db.commit()
    db.refresh(current)
    out = schemas.UserOut.model_validate(current)
    out.has_location = current.latitude is not None
    return out


@router.patch("/me/location")
def update_location(payload: schemas.LocationUpdate, db: Session = Depends(get_db),
                     current: models.User = Depends(deps.get_current_user)):
    current.latitude = payload.latitude
    current.longitude = payload.longitude
    current.geohash = geohash_encode(payload.latitude, payload.longitude)
    db.commit()
    return {"ok": True}


@router.patch("/me/availability")
def set_availability(payload: schemas.AvailabilityUpdate, db: Session = Depends(get_db),
                      current: models.User = Depends(deps.get_current_user)):
    if payload.is_available:
        if not current.is_donor:
            raise HTTPException(400, "You must register as a donor first (blood group required).")
        if current.latitude is None or current.longitude is None:
            raise HTTPException(400, "Location is required before going online. Enable location first.")
        now = datetime.utcnow()
        mapping = {
            "now": None,
            "1h": now + timedelta(hours=1),
            "3h": now + timedelta(hours=3),
            "today": datetime.combine(now.date(), time(23, 59, 59)),
        }
        current.availability_expires_at = mapping.get(payload.duration)
        current.is_available = True
    else:
        current.is_available = False
        current.availability_expires_at = None
    db.commit()
    return {"is_available": current.is_available, "availability_expires_at": current.availability_expires_at}


@router.get("/me/dashboard")
def dashboard(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    nearby, compatible = [], []

    if current.is_donor and current.blood_group:
        open_requests = db.query(models.BloodRequest).filter(
            models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED"])
        ).all()
        for r in open_requests:
            donor_groups = compatible_donor_groups(r.blood_group)
            is_compatible = current.blood_group in donor_groups
            dist = haversine_km(current.latitude, current.longitude, r.latitude, r.longitude) \
                if current.latitude is not None else None
            if is_compatible:
                compatible.append(r)
            if is_compatible and dist is not None and dist <= max(r.search_radius_km, 20):
                nearby.append((r, dist))

    nearby.sort(key=lambda x: x[1])
    responding_others = db.query(models.DonationResponse).filter(
        models.DonationResponse.status.in_(matching.ACTIVE_RESPONSE_STATUSES),
        models.DonationResponse.donor_id != current.id,
    ).count()
    my_active = db.query(models.DonationResponse).filter(
        models.DonationResponse.donor_id == current.id,
        models.DonationResponse.status.in_(matching.ACTIVE_RESPONSE_STATUSES),
    ).count()

    cards = []
    for r, dist in nearby[:10]:
        cards.append({
            "id": r.id, "blood_group": r.blood_group, "units_required": r.units_required,
            "priority": r.priority, "distance_km": round(dist, 2), "hospital_name": r.hospital_name,
            "status": r.status, "is_verified_request": r.is_verified_request,
        })

    return {
        "name": current.name,
        "is_donor": current.is_donor,
        "blood_group": current.blood_group,
        "is_available": current.is_available,
        "availability_expires_at": current.availability_expires_at,
        "nearby_requests_count": len(nearby),
        "compatible_requests_count": len(compatible),
        "people_currently_responding": responding_others,
        "your_active_responses": my_active,
        "nearby_requests": cards,
    }