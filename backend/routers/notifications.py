from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, deps
from ..database import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/me")
def my_notifications(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    items = db.query(models.Notification).filter(models.Notification.user_id == current.id)\
        .order_by(models.Notification.created_at.desc()).limit(50).all()
    return [{"id": n.id, "type": n.type, "message": n.message, "read": n.read,
             "request_id": n.request_id, "created_at": n.created_at} for n in items]


@router.patch("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    n = db.query(models.Notification).filter(models.Notification.id == notification_id,
                                               models.Notification.user_id == current.id).first()
    if not n:
        raise HTTPException(404, "Not found")
    n.read = True
    db.commit()
    return {"ok": True}


@router.patch("/read-all")
def mark_all_read(db: Session = Depends(get_db), current: models.User = Depends(deps.get_current_user)):
    db.query(models.Notification).filter(models.Notification.user_id == current.id, models.Notification.read == False)\
        .update({"read": True})
    db.commit()
    return {"ok": True}