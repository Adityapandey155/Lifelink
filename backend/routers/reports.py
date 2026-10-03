from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, deps
from ..database import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("")
def create_report(payload: schemas.ReportCreate, db: Session = Depends(get_db),
                   current: models.User = Depends(deps.get_current_user)):
    r = models.Report(reporter_id=current.id, reported_user_id=payload.reported_user_id,
                       reported_request_id=payload.reported_request_id, reason=payload.reason)
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "status": r.status}