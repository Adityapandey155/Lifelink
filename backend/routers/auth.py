from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, security, deps
from ..database import get_db
from ..compatibility import BLOOD_GROUPS

router = APIRouter(prefix="/api/auth", tags=["auth"])

_FAILED_LOGINS = {}  # email -> (count, lock_until)


@router.post("/register", response_model=schemas.TokenResponse)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if payload.blood_group not in BLOOD_GROUPS:
        raise HTTPException(400, "Invalid blood group")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(models.User).filter(models.User.phone == payload.phone).first():
        raise HTTPException(400, "Phone already registered")

    user = models.User(
        name=payload.name, email=payload.email, phone=payload.phone,
        password_hash=security.hash_password(payload.password),
        blood_group=payload.blood_group, dob=payload.dob, city=payload.city,
        photo_url=payload.photo_url, consent_notifications=payload.consent_notifications,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = security.create_access_token({"sub": str(user.id)})
    out = schemas.UserOut.model_validate(user)
    out.has_location = False
    return {"access_token": token, "token_type": "bearer", "user": out}


@router.post("/register", response_model=schemas.TokenResponse)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    if payload.register_as_donor:
        if not payload.blood_group or payload.blood_group not in BLOOD_GROUPS:
            raise HTTPException(400, "A valid blood group is required to register as a donor")

    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    if db.query(models.User).filter(models.User.phone == payload.phone).first():
        raise HTTPException(400, "Phone already registered")

    user = models.User(
        name=payload.name, email=payload.email, phone=payload.phone,
        password_hash=security.hash_password(payload.password),
        blood_group=payload.blood_group if payload.register_as_donor else None,
        is_donor=payload.register_as_donor,
        dob=payload.dob, city=payload.city,
        photo_url=payload.photo_url, consent_notifications=payload.consent_notifications,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = security.create_access_token({"sub": str(user.id)})
    out = schemas.UserOut.model_validate(user)
    out.has_location = False
    return {"access_token": token, "token_type": "bearer", "user": out}


@router.get("/me", response_model=schemas.UserOut)
def me(current: models.User = Depends(deps.get_current_user)):
    out = schemas.UserOut.model_validate(current)
    out.has_location = current.latitude is not None
    return out