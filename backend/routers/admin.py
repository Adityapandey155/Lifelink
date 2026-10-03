import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, deps, matching, notify, audit, security
from ..database import get_db
from ..compatibility import BLOOD_GROUPS

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    today = datetime.utcnow().date()
    active_donors = db.query(models.User).filter(models.User.is_available == True).count()
    requests_today = db.query(models.BloodRequest).filter(
        models.BloodRequest.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    fulfilled = db.query(models.BloodRequest).filter(models.BloodRequest.status == "FULFILLED").count()
    critical_active = db.query(models.BloodRequest).filter(
        models.BloodRequest.priority == "CRITICAL",
        models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED"])
    ).count()
    verified_hospitals = db.query(models.Hospital).filter(models.Hospital.verification_status == "approved").count()

    # avg response time (first response vs request creation) for requests with >=1 response
    reqs_with_resp = db.query(models.BloodRequest.id, models.BloodRequest.created_at).all()
    diffs = []
    for rid, created in reqs_with_resp:
        first = db.query(models.DonationResponse).filter(models.DonationResponse.request_id == rid)\
            .order_by(models.DonationResponse.created_at.asc()).first()
        if first:
            diffs.append((first.created_at - created).total_seconds() / 60)
    avg_response = round(sum(diffs) / len(diffs), 1) if diffs else None

    return {
        "active_donors": active_donors,
        "emergency_requests_today": requests_today,
        "requests_fulfilled": fulfilled,
        "average_response_time_minutes": avg_response,
        "active_critical_requests": critical_active,
        "verified_hospitals": verified_hospitals,
        "total_users": db.query(models.User).count(),
        "total_hospitals": db.query(models.Hospital).count(),
        "total_requests": db.query(models.BloodRequest).count(),
        "open_reports": db.query(models.Report).filter(models.Report.status == "OPEN").count(),
    }


@router.get("/hospitals")
def list_hospitals(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    items = db.query(models.Hospital).order_by(models.Hospital.created_at.desc()).all()
    return [{"id": h.id, "name": h.name, "address": h.address, "verification_status": h.verification_status,
             "owner_user_id": h.owner_user_id, "is_demo": h.is_demo, "created_at": h.created_at} for h in items]


@router.patch("/hospitals/{hospital_id}")
def moderate_hospital(hospital_id: int, action: str, notes: str = "", db: Session = Depends(get_db),
                       admin: models.User = Depends(deps.get_current_admin)):
    h = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not h:
        raise HTTPException(404, "Not found")
    mapping = {"approve": "approved", "reject": "rejected", "suspend": "suspended"}
    if action not in mapping:
        raise HTTPException(400, "Invalid action")
    h.verification_status = mapping[action]
    h.admin_notes = notes
    db.commit()
    audit.log_action(db, admin.id, f"hospital_{action}", {"hospital_id": h.id})
    return {"verification_status": h.verification_status}


@router.get("/users")
def list_users(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    items = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [{"id": u.id, "name": u.name, "email": u.email, "blood_group": u.blood_group,
             "is_available": u.is_available, "is_blocked": u.is_blocked, "role": u.role,
             "is_demo": u.is_demo, "created_at": u.created_at} for u in items]


@router.patch("/users/{user_id}/block")
def block_user(user_id: int, blocked: bool, db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    u.is_blocked = blocked
    db.commit()
    audit.log_action(db, admin.id, "block_user" if blocked else "unblock_user", {"user_id": u.id})
    return {"is_blocked": u.is_blocked}


@router.get("/requests")
def list_requests_admin(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    items = db.query(models.BloodRequest).order_by(models.BloodRequest.created_at.desc()).all()
    return [{"id": r.id, "blood_group": r.blood_group, "priority": r.priority, "status": r.status,
             "hospital_name": r.hospital_name, "is_verified_request": r.is_verified_request,
             "is_demo": r.is_demo, "created_at": r.created_at} for r in items]


@router.patch("/requests/{request_id}/cancel")
def admin_cancel_request(request_id: int, db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    r = db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    r.status = "CANCELLED"
    r.matching_active = False
    db.commit()
    audit.log_action(db, admin.id, "admin_cancel_request", {"request_id": r.id})
    return {"status": r.status}


@router.get("/reports")
def list_reports(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    items = db.query(models.Report).order_by(models.Report.created_at.desc()).all()
    return [{"id": r.id, "reporter_id": r.reporter_id, "reported_user_id": r.reported_user_id,
             "reported_request_id": r.reported_request_id, "reason": r.reason,
             "status": r.status, "created_at": r.created_at} for r in items]


@router.patch("/reports/{report_id}")
def update_report(report_id: int, status: str, db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    r = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not r:
        raise HTTPException(404, "Not found")
    r.status = status
    db.commit()
    return {"status": r.status}


@router.get("/audit-logs")
def audit_logs(db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    items = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(200).all()
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "meta": a.meta,
             "created_at": a.created_at} for a in items]


# ---------------- DEMO MODE ----------------

DEMO_CITY = {"name": "Bengaluru (DEMO)", "lat": 12.9716, "lon": 77.5946}


@router.post("/demo/seed-donors")
def seed_demo_donors(count: int = 15, db: Session = Depends(get_db), admin: models.User = Depends(deps.get_current_admin)):
    created = []
    for i in range(count):
        email = f"demo_donor_{random.randint(100000,999999)}@lifelink.demo"
        lat = DEMO_CITY["lat"] + (random.random() - 0.5) * 0.12
        lon = DEMO_CITY["lon"] + (random.random() - 0.5) * 0.12
        u = models.User(
            name=f"Demo Donor {i+1}",
            email=email,
            phone=f"9{random.randint(100000000,999999999)}",
            password_hash=security.hash_password("demo1234"),
            blood_group=random.choice(BLOOD_GROUPS),
            city=DEMO_CITY["name"],
            role="user",
            latitude=lat, longitude=lon,
            is_available=True,
            is_donor=True,  
            is_demo=True,
        )
        db.add(u)
        created.append(u)
    db.commit()
    audit.log_action(db, admin.id, "demo_seed_donors", {"count": count})
    return {"created": len(created), "label": "DEMO DATA"}


@router.post("/demo/simulate")
async def simulate_full_flow(blood_group: str = "B+", db: Session = Depends(get_db),
                              admin: models.User = Depends(deps.get_current_admin)):
    """
    Runs the full section-29 scenario end-to-end automatically:
    create hospital -> create request -> match -> donor accepts -> hospital contacts -> fulfilled.
    """
    steps = []

    # ensure at least a few demo donors exist
    if db.query(models.User).filter(models.User.is_demo == True, models.User.is_available == True).count() < 3:
        seed_demo_donors(count=15, db=db, admin=admin)
        steps.append("Seeded demo donors")

    demo_owner_email = "demo_hospital_owner@lifelink.demo"
    owner = db.query(models.User).filter(models.User.email == demo_owner_email).first()
    if not owner:
        owner = models.User(
            name="Demo Hospital Coordinator", email=demo_owner_email,
            phone=f"8{random.randint(100000000,999999999)}",
            password_hash=security.hash_password("demo1234"),
            blood_group="O+", role="user", is_demo=True,
            latitude=DEMO_CITY["lat"], longitude=DEMO_CITY["lon"],
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
    steps.append(f"Demo requester ready: {owner.email}")

    hospital = db.query(models.Hospital).filter(models.Hospital.owner_user_id == owner.id).first()
    if not hospital:
        hospital = models.Hospital(
            owner_user_id=owner.id, name="Apollo Example Hospital (DEMO)",
            address="Demo Address, Bengaluru", latitude=DEMO_CITY["lat"], longitude=DEMO_CITY["lon"],
            verification_status="approved", is_demo=True,
        )
        db.add(hospital)
        db.commit()
        db.refresh(hospital)
    steps.append("Demo hospital verified ✓")

    req = models.BloodRequest(
        creator_id=owner.id, hospital_id=hospital.id, blood_group=blood_group,
        units_required=2, priority="CRITICAL", hospital_name=hospital.name,
        contact_person="Demo Coordinator", contact_phone=owner.phone,
        latitude=DEMO_CITY["lat"] + (random.random()-0.5)*0.02,
        longitude=DEMO_CITY["lon"] + (random.random()-0.5)*0.02,
        description="DEMO: Simulated emergency for presentation purposes.",
        expires_at=datetime.utcnow() + timedelta(hours=6),
        is_verified_request=True, is_demo=True,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    steps.append(f"Emergency request #{req.id} created ({blood_group}, CRITICAL)")

    matches, radius = matching.progressive_search(db, req)
    req.search_radius_km = radius
    db.commit()
    await notify.notify_donors(db, req, matches)
    steps.append(f"Matching engine found {len(matches)} potential donor(s) within {radius} km")

    if matches:
        top = matches[0]["donor"]
        resp = models.DonationResponse(request_id=req.id, donor_id=top.id, status="RESPONDED", contact_shared=True)
        db.add(resp)
        top.is_available = False
        req.status = "DONOR_RESPONDED"
        db.commit()
        db.refresh(resp)
        steps.append(f"Simulated donor '{top.name}' clicked DONATE NOW and confirmed sharing contact info")

        resp.status = "CONTACTED"
        db.commit()
        steps.append("Hospital marked donor as CONTACTED")

        resp.status = "CONFIRMED"
        db.commit()
        steps.append("Donor CONFIRMED for donation")

        resp.status = "DONATING"
        db.commit()
        steps.append("DONATION IN PROGRESS")

        resp.status = "FULFILLED"
        req.fulfilled_units += 1
        if req.fulfilled_units >= req.units_required:
            req.status = "FULFILLED"
        db.commit()
        steps.append("Request marked FULFILLED ✅ (DEMO)")
    else:
        steps.append("No demo donors matched — try seeding more donors")

    audit.log_action(db, admin.id, "demo_simulate", {"request_id": req.id})
    return {"label": "DEMO DATA", "request_id": req.id, "steps": steps}