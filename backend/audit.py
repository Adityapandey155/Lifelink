import json
from . import models


def log_action(db, actor_id, action, meta=None):
    db.add(models.AuditLog(
        actor_id=actor_id,
        action=action,
        meta=json.dumps(meta or {}),
    ))
    db.commit()