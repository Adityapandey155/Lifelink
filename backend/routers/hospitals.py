from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, deps
from ..database import get_db
from ..geo import geohash_encode

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])


@router.post("", response_model=schemas.HospitalOut)
def create_hospital(payload: schemas.HospitalCreate, db: Session = Depends(get_db),
                     current: models.User = Depends(deps.get_current_user)):
    existing = db.query(models.Hospital).filter(models.Hospital.owner_user_id == current.id).first()
    if existing:
        raise HTTPException(400, "You already registered a hospital/organization")
    h = models.Hospital(owner_user_id=current.id, name=payload.name, address=payload.address,
                         latitude=payload.latitude, longitude=payload.longitude)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@router.get("/me", response_model=schemas.HospitalOut)
def my_hospital(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    h = db.query(models.Hospital).filter(models.Hospital.owner_user_id == current.id).first()
    if not h:
        raise HTTPException(404, "No hospital registered")
    return h