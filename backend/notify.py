from . import models
from .websocket_manager import manager


async def notify_donors(db, request: models.BloodRequest, targets: list):
    """
    targets: list of dicts {donor, distance_km, eta_minutes, is_available}
    Notifies ALL compatible donors — active or inactive. Inactive donors must
    explicitly opt in ("I'm Available to Help") before they can respond.
    """
    already_notified = {
        n.user_id for n in db.query(models.Notification).filter(
            models.Notification.request_id == request.id,
            models.Notification.type == "emergency_request",
        ).all()
    }
    new_targets = [t for t in targets if t["donor"].id not in already_notified]

    for t in new_targets:
        donor = t["donor"]
        msg = (f"{request.units_required} unit(s) of {request.blood_group} blood urgently required "
               f"near your location (~{t['distance_km']} km away). Priority: {request.priority}.")
        db.add(models.Notification(
            user_id=donor.id, request_id=request.id,
            type="emergency_request", message=msg,
        ))
    db.commit()

    for t in new_targets:
        donor = t["donor"]
        await manager.send_to_user(donor.id, {
            "type": "new_request",
            "request_id": request.id,
            "blood_group": request.blood_group,
            "units_required": request.units_required,
            "priority": request.priority,
            "distance_km": t["distance_km"],
            "eta_minutes": t["eta_minutes"],
            "hospital_name": request.hospital_name,
            "donor_is_available": t["is_available"],
        })

    await manager.send_to_user(request.creator_id, {
        "type": "matches_updated",
        "request_id": request.id,
        "potential_donors": len(targets),
    })
    return new_targets