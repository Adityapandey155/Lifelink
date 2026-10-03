from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, deps, matching, notify, audit
from ..database import get_db
from ..geo import haversine_km, jitter_coordinate
from ..compatibility import compatible_donor_groups, BLOOD_GROUPS

router = APIRouter(prefix="/api/requests", tags=["requests"])

MAX_OPEN_REQUESTS_PER_USER = 5
CREATE_COOLDOWN_MINUTES = 10
PRIORITIES = ["CRITICAL", "URGENT", "NORMAL"]


@router.post("")
async def create_request(payload: schemas.RequestCreate, db: Session = Depends(get_db),
                          current: models.User = Depends(deps.get_current_user)):
    if payload.blood_group not in BLOOD_GROUPS:
        raise HTTPException(400, "Invalid blood group")
    if payload.priority not in PRIORITIES:
        raise HTTPException(400, "Invalid priority")

    # Anti-abuse: cooldown + max open requests
    if current.last_request_created_at and current.role != "admin":
        elapsed = (datetime.utcnow() - current.last_request_created_at).total_seconds() / 60
        if elapsed < CREATE_COOLDOWN_MINUTES:
            raise HTTPException(429, f"Please wait {round(CREATE_COOLDOWN_MINUTES - elapsed)} more minute(s) before creating another request")
    open_count = db.query(models.BloodRequest).filter(
        models.BloodRequest.creator_id == current.id,
        models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED", "HOSPITAL_CONTACTED", "DONOR_CONFIRMED", "DONATION_IN_PROGRESS"]),
    ).count()
    if open_count >= MAX_OPEN_REQUESTS_PER_USER:
        raise HTTPException(429, "You have too many active requests open already")

    hospital = db.query(models.Hospital).filter(models.Hospital.owner_user_id == current.id).first()
    is_verified = bool(hospital and hospital.verification_status == "approved")

    expires_at = payload.required_by or (datetime.utcnow() + timedelta(hours=6))

    req = models.BloodRequest(
        creator_id=current.id,
        hospital_id=hospital.id if hospital else None,
        blood_group=payload.blood_group,
        units_required=payload.units_required,
        priority=payload.priority,
        hospital_name=payload.hospital_name,
        contact_person=payload.contact_person,
        contact_phone=payload.contact_phone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        description=payload.description,
        required_by=payload.required_by,
        expires_at=expires_at,
        is_verified_request=is_verified,
    )
    db.add(req)
    current.last_request_created_at = datetime.utcnow()
    db.commit()
    db.refresh(req)

    matches, radius = matching.progressive_search(db, req)
    req.search_radius_km = radius
    db.commit()
    broadcast_targets = matching.find_all_compatible_donors(db, req, radius)
    await notify.notify_donors(db, req, broadcast_targets)
    audit.log_action(db, current.id, "create_request", {"request_id": req.id})

    return {"id": req.id, "status": req.status, "search_radius_km": radius, "potential_donors": len(broadcast_targets)}


def _serialize_for_viewer(db: Session, r: models.BloodRequest, viewer: models.User):
    dist = None
    if viewer.latitude is not None:
        dist = haversine_km(viewer.latitude, viewer.longitude, r.latitude, r.longitude)
    lat, lon = jitter_coordinate(r.latitude, r.longitude, seed=r.id)
    return {
        "id": r.id, "blood_group": r.blood_group, "units_required": r.units_required,
        "priority": r.priority, "hospital_name": r.hospital_name, "status": r.status,
        "is_verified_request": r.is_verified_request, "description": r.description,
        "required_by": r.required_by, "created_at": r.created_at,
        "distance_km": round(dist, 2) if dist is not None else None,
        "approx_latitude": lat, "approx_longitude": lon,
        "is_demo": r.is_demo, "is_owner": r.creator_id == viewer.id,
    }


@router.get("")
def list_requests(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    reqs = db.query(models.BloodRequest).filter(
        models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED"])
    ).order_by(models.BloodRequest.created_at.desc()).all()
    return [_serialize_for_viewer(db, r, current) for r in reqs]

@router.get("/mine")
def list_my_requests(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    reqs = db.query(models.BloodRequest).filter(
        models.BloodRequest.creator_id == current.id
    ).order_by(models.BloodRequest.created_at.desc()).all()
    return [_serialize_for_viewer(db, r, current) for r in reqs]

@router.delete("/mine/clear")
def clear_my_requests(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    # Pehle unke response/notifications hatao taaki foreign-key crash na ho
    req_ids = [r.id for r in db.query(models.BloodRequest.id).filter(models.BloodRequest.creator_id == current.id).all()]
    
    if req_ids:
        db.query(models.DonationResponse).filter(models.DonationResponse.request_id.in_(req_ids)).delete(synchronize_session=False)
        db.query(models.Notification).filter(models.Notification.request_id.in_(req_ids)).delete(synchronize_session=False)
        db.query(models.BloodRequest).filter(models.BloodRequest.creator_id == current.id).delete(synchronize_session=False)
        db.commit()
        
    return {"deleted": len(req_ids)}


@router.get("/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    data = _serialize_for_viewer(db, r, current)
    if r.creator_id == current.id or current.role == "admin":
        data["exact_latitude"] = r.latitude
        data["exact_longitude"] = r.longitude
        data["contact_person"] = r.contact_person
        data["contact_phone"] = r.contact_phone
    my_response = db.query(models.DonationResponse).filter(
        models.DonationResponse.request_id == r.id, models.DonationResponse.donor_id == current.id
    ).first()
    data["my_response_status"] = my_response.status if my_response else None
    data["compatible_for_me"] = bool(current.is_donor and current.blood_group and current.blood_group in compatible_donor_groups(r.blood_group))
    return data


@router.get("/{request_id}/matches")
def get_matches(request_id: int, db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    if r.creator_id != current.id and current.role != "admin":
        raise HTTPException(403, "Not authorized")
    
    found_all = matching.find_all_compatible_donors(db, r, 20)
    available_compatible = matching.find_available_matches(db, r, r.search_radius_km)
    responses_count = db.query(models.DonationResponse).filter(
        models.DonationResponse.request_id == r.id, models.DonationResponse.status != "CANCELLED"
    ).count()
    status_label = r.status if responses_count > 0 else "WAITING FOR DONOR"
    return {
        "potential_donors_found": len(found_all),
        "available_compatible": len(available_compatible),
        "responses_count": responses_count,
        "status": status_label,
        "search_radius_km": r.search_radius_km,
    }


@router.post("/{request_id}/expand-radius")
async def expand_radius(request_id: int, db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    if r.creator_id != current.id and current.role != "admin":
        raise HTTPException(403, "Not authorized")
    steps = matching.RADIUS_STEPS
    idx = steps.index(r.search_radius_km) if r.search_radius_km in steps else 0
    new_radius = steps[min(idx + 1, len(steps) - 1)]
    r.search_radius_km = new_radius
    db.commit()
    broadcast_targets = matching.find_all_compatible_donors(db, r, new_radius)
    new_targets = await notify.notify_donors(db, r, broadcast_targets)
    return {"search_radius_km": new_radius, "newly_notified": len(new_targets), "total_matches": len(broadcast_targets)}


@router.patch("/{request_id}/status")
def update_status(request_id: int, payload: schemas.RequestStatusUpdate, db: Session = Depends(get_db),
                   current: models.User = Depends(deps.get_current_user)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    if r.creator_id != current.id and current.role != "admin":
        raise HTTPException(403, "Not authorized")
    if payload.status not in ["CANCELLED", "FULFILLED"]:
        raise HTTPException(400, "Invalid status transition")
    r.status = payload.status
    r.matching_active = False
    db.commit()
    return {"status": r.status}