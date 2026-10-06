"""Suscripción a notificaciones (recordatorios y, para el admin, solicitudes de cuenta)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import push, tenancy
from ..config import get_settings
from ..db import get_db
from ..deps import require_approved_user, require_user
from ..models import PushSubscription, User
from ..schemas import EndpointIn, PushSubscriptionIn

router = APIRouter(prefix="/api/push", tags=["notificaciones"], dependencies=[Depends(require_approved_user)])


@router.get("")
def status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return {
        "configured": settings.push_configured,
        "public_key": settings.vapid_public_key if settings.push_configured else None,
        "devices": len(db.scalars(select(PushSubscription.id)).all()),
    }


@router.post("/subscribe")
def subscribe(body: PushSubscriptionIn, user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    if not get_settings().push_configured:
        raise HTTPException(503, "Las notificaciones no están configuradas en el servidor.")
    # El mismo navegador pudo estar suscrito con otra cuenta: la suscripción pasa a esta.
    with tenancy.unscoped(db):
        db.execute(delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    db.add(PushSubscription(endpoint=body.endpoint, p256dh=body.keys["p256dh"], auth=body.keys["auth"]))
    db.commit()
    return status(db)


@router.post("/unsubscribe")
def unsubscribe(body: EndpointIn, db: Session = Depends(get_db)) -> dict:
    db.execute(delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    db.commit()
    return status(db)


@router.post("/test")
def test(user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    sent = push.send_to_user(
        db,
        user.id,
        {"title": "Kcalia", "body": "Así te llegarán los recordatorios.", "url": "/ajustes", "tag": "kcalia-test"},
    )
    return {"sent": sent}
