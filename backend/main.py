import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models, security, matching, notify
from .database import engine, Base, SessionLocal
from .websocket_manager import manager
from .routers import auth, users, hospitals, requests, donations, notifications, reports, admin, public

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LifeLink API")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

for r in [auth.router, users.router, hospitals.router, requests.router,
          donations.router, notifications.router, reports.router, admin.router, public.router]:
    app.include_router(r)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = security.decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        await websocket.close(code=4001)
        return
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


@app.on_event("startup")
def create_default_admin():
    db: Session = SessionLocal()
    try:
        admin_user = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin_user:
            admin_user = models.User(
                name="LifeLink Admin", email="admin@lifelink.local", phone="9000000000",
                password_hash=security.hash_password("admin123"),
                blood_group="O+", role="admin",
            )
            db.add(admin_user)
            db.commit()
            print("=" * 60)
            print("Default admin created:")
            print("  email:    admin@lifelink.local")
            print("  password: admin123")
            print("=" * 60)
    finally:
        db.close()


@app.on_event("startup")
async def start_background_loop():
    asyncio.create_task(background_worker())


async def background_worker():
    while True:
        db: Session = SessionLocal()
        try:
            now = datetime.utcnow()

            # expire donor availability windows
            expired_donors = db.query(models.User).filter(
                models.User.is_available == True,
                models.User.availability_expires_at.isnot(None),
                models.User.availability_expires_at < now,
            ).all()
            for d in expired_donors:
                d.is_available = False

            # expire stale requests
            stale = db.query(models.BloodRequest).filter(
                models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED"]),
                models.BloodRequest.expires_at < now,
            ).all()
            for r in stale:
                r.status = "EXPIRED"
                r.matching_active = False
            db.commit()

            # progressive radius expansion + escalation suggestion
            active_reqs = db.query(models.BloodRequest).filter(
                models.BloodRequest.status.in_(["OPEN", "DONOR_RESPONDED"]),
                models.BloodRequest.matching_active == True,
            ).all()
            for r in active_reqs:
                age_minutes = (now - r.created_at).total_seconds() / 60
                responses_count = db.query(models.DonationResponse).filter(
                    models.DonationResponse.request_id == r.id,
                    models.DonationResponse.status != "CANCELLED",
                ).count()
                if responses_count >= r.units_required:
                    r.matching_active = False
                    db.commit()
                    continue
                if age_minutes >= 10 and r.search_radius_km < 20:
                    old_radius = r.search_radius_km
                    new_radius = 10 if old_radius <= 5 else 20
                    r.search_radius_km = new_radius
                    db.commit()
                    broadcast_targets = matching.find_all_compatible_donors(db, r, new_radius)
                    await notify.notify_donors(db, r, broadcast_targets)
                    await manager.send_to_user(r.creator_id, {
                        "type": "escalation",
                        "request_id": r.id,
                        "message": (f"No sufficient donor response yet. Search radius expanded to {new_radius} km. "
                                    f"Suggested: notify blood banks / hospital emergency services."),
                        "responses_count": responses_count,
                    })
        finally:
            db.close()
        await asyncio.sleep(30)


# Serve frontend (must be included AFTER API routes so /api/* and /ws are matched first)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")