from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, deps, matching
from ..database import get_db
from ..websocket_manager import manager
from ..geo import haversine_km
from ..compatibility import compatible_donor_groups

router = APIRouter(prefix="/api", tags=["donations"])

VALID_TRANSITIONS = {
    "RESPONDED": ["CONTACTED", "CANCELLED"],
    "CONTACTED": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["DONATING", "CANCELLED"],
    "DONATING": ["FULFILLED", "CANCELLED"],
    "FULFILLED": [],
    "CANCELLED": [],
}


@router.post("/requests/{request_id}/donate")
async def donate_now(request_id: int, payload: schemas.DonateConfirm, db: Session = Depends(get_db),
                      current: models.User = Depends(deps.get_current_user)):
    if not payload.confirm:
        raise HTTPException(400, "Confirmation required")

    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Request not found")
    if r.status not in ["OPEN", "DONOR_RESPONDED"] or r.expires_at < datetime.utcnow():
        raise HTTPException(400, "This request is no longer active")
    if current.blood_group not in compatible_donor_groups(r.blood_group):
        raise HTTPException(400, "Your blood group is not compatible with this request")
    if not current.is_donor:                                   
        raise HTTPException(400, "You must register as a donor first")
    if not current.is_available:
        raise HTTPException(400, "You must be marked 'Ready to Donate' first")
    if current.latitude is None:
        raise HTTPException(400, "Location is required to respond to a request")

    existing = db.query(models.DonationResponse).filter(
        models.DonationResponse.request_id == r.id, models.DonationResponse.donor_id == current.id
    ).first()
    if existing:
        raise HTTPException(400, "You already responded to this request")

    already_active = db.query(models.DonationResponse).filter(
        models.DonationResponse.donor_id == current.id,
        models.DonationResponse.status.in_(matching.ACTIVE_RESPONSE_STATUSES),
    ).first()
    if already_active:
        raise HTTPException(400, "You are already responding to another active request")

    resp = models.DonationResponse(
        request_id=r.id, donor_id=current.id, status="RESPONDED", contact_shared=True,
    )
    db.add(resp)

    # Donor becomes committed -> auto unavailable for other emergencies
    current.is_available = False
    current.availability_expires_at = None

    if r.status == "OPEN":
        r.status = "DONOR_RESPONDED"

    db.commit()
    db.refresh(resp)

    responses_count = db.query(models.DonationResponse).filter(
        models.DonationResponse.request_id == r.id, models.DonationResponse.status != "CANCELLED"
    ).count()
    if responses_count >= r.units_required:
        r.matching_active = False
        db.commit()

    dist = haversine_km(r.latitude, r.longitude, current.latitude, current.longitude)
    db.add(models.Notification(
        user_id=r.creator_id, request_id=r.id, type="donation_response",
        message=f"A compatible donor ({current.blood_group}) responded to your request.",
    ))
    db.commit()

    await manager.send_to_user(r.creator_id, {
        "type": "donation_response",
        "request_id": r.id,
        "response_id": resp.id,
        "donor_name": current.name,
        "donor_phone": current.phone,
        "donor_blood_group": current.blood_group,
        "distance_km": round(dist, 2) if dist is not None else None,
        "responses_count": responses_count,
    })
    await manager.send_to_user(current.id, {
        "type": "response_confirmed",
        "request_id": r.id,
        "message": "Thank you! Your contact info has been shared with the request coordinator.",
    })

    return {
        "response_id": resp.id,
        "status": resp.status,
        "shared": ["name", "phone", "blood_group", "approximate_location"],
        "note": "Donation eligibility must be confirmed by qualified medical professionals at the hospital.",
    }


@router.get("/requests/{request_id}/responses")
def list_responses(request_id: int, db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    if r.creator_id != current.id and current.role != "admin":
        raise HTTPException(403, "Not authorized")
    responses = db.query(models.DonationResponse).filter(models.DonationResponse.request_id == r.id).all()
    out = []
    for resp in responses:
        donor = db.query(models.User).get(resp.donor_id)
        dist = haversine_km(r.latitude, r.longitude, donor.latitude, donor.longitude)
        item = {
            "id": resp.id, "status": resp.status, "created_at": resp.created_at,
            "blood_group": donor.blood_group, "distance_km": round(dist, 2) if dist is not None else None,
        }
        if resp.contact_shared:
            item["donor_name"] = donor.name
            item["donor_phone"] = donor.phone
        out.append(item)
    return out


@router.get("/donations/me")
def my_donations(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    responses = db.query(models.DonationResponse).filter(models.DonationResponse.donor_id == current.id)\
        .order_by(models.DonationResponse.created_at.desc()).all()
    out = []
    for resp in responses:
        r = db.query(models.BloodRequest).get(resp.request_id)
        out.append({
            "response_id": resp.id, "status": resp.status,
            "request_id": r.id, "blood_group": r.blood_group,
            "hospital_name": r.hospital_name, "priority": r.priority,
            "request_status": r.status, "created_at": resp.created_at,
        })
    return out


@router.patch("/donations/{response_id}/status")
async def update_response_status(response_id: int, payload: schemas.DonationStatusUpdate,
                                  db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    resp = db.query(models.DonationResponse).filter(models.DonationResponse.id == response_id).first()
    if not resp:
        raise HTTPException(404, "Not found")
    r = db.query(models.BloodRequest).get(resp.request_id)
    if r.creator_id != current.id and current.role != "admin":
        raise HTTPException(403, "Not authorized")
    allowed = VALID_TRANSITIONS.get(resp.status, [])
    if payload.status not in allowed:
        raise HTTPException(400, f"Cannot move from {resp.status} to {payload.status}")

    resp.status = payload.status
    resp.updated_at = datetime.utcnow()

    if payload.status == "FULFILLED":
        r.fulfilled_units += 1
        if r.fulfilled_units >= r.units_required:
            r.status = "FULFILLED"
            r.matching_active = False
    db.commit()

    await manager.send_to_user(resp.donor_id, {
        "type": "response_status_update", "request_id": r.id, "status": resp.status,
    })
    await manager.send_to_user(r.creator_id, {
        "type": "matches_updated", "request_id": r.id, "response_status": resp.status,
    })
    return {"status": resp.status, "request_status": r.status}