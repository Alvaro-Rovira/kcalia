"""Recordatorios para apuntar las comidas y pesarse. Los lanza el planificador del propio proceso cada minuto.

Cada aviso tiene una franja de 45 minutos desde su hora. Si en ese momento ya está apuntado lo que pedía (una comida
en ese momento del día o el peso de hoy), no se envía; en ambos casos se anota para no repetirlo ese día.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import push, services, tenancy
from .config import get_settings
from .db import SessionLocal
from .models import Meal, PushSubscription, ReminderLog, User, Weight

log = logging.getLogger("kcalia.reminders")

WINDOW = timedelta(minutes=45)
SLOT_TEXT = {
    "desayuno": "el desayuno",
    "comida": "la comida",
    "merienda": "la merienda",
    "cena": "la cena",
    "snack": "lo que has picado",
}


def _in_window(hhmm: str, now: datetime) -> bool:
    hour, minute = (int(x) for x in hhmm.split(":"))
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return start <= now < start + WINDOW


def _logged(db: Session, day: str, kind: str) -> bool:
    return db.scalar(select(ReminderLog.id).where(ReminderLog.date == day, ReminderLog.kind == kind)) is not None


def due_for_user(db: Session, user_id: int, now: datetime) -> list[tuple[str, dict | None]]:
    """(tipo, aviso) que tocan ahora; aviso None si ya estaba hecho y solo hay que anotarlo."""
    prefs = services.get_prefs(db)
    if not prefs.reminders:
        return []
    day = now.date().isoformat()
    out: list[tuple[str, dict | None]] = []
    for reminder in prefs.meal_reminders:
        kind = f"meal:{reminder.slot}"
        if not reminder.enabled or not _in_window(reminder.time, now) or _logged(db, day, kind):
            continue
        done = db.scalar(
            select(Meal.id).where(Meal.date == day, Meal.slot == reminder.slot, Meal.deleted_at.is_(None)).limit(1)
        )
        payload = {
            "title": "¿Apuntamos?",
            "body": f"Cuéntame qué has tomado en {SLOT_TEXT[reminder.slot]}: una frase y listo.",
            "url": "/?nueva=1",
            "tag": f"kcalia-{kind}",
        }
        out.append((kind, None if done else payload))
    if prefs.weigh_reminder and now.weekday() in prefs.weigh_days and _in_window(prefs.weigh_reminder, now):
        if not _logged(db, day, "weigh"):
            done = db.scalar(select(Weight.id).where(Weight.date == day))
            payload = {
                "title": "Toca pesarse",
                "body": "En ayunas y después del baño: así la media de 7 días es fiable.",
                "url": "/peso",
                "tag": "kcalia-weigh",
            }
            out.append(("weigh", None if done else payload))
    return out


def run(now: datetime | None = None) -> int:
    """Revisa los avisos de todas las cuentas con recordatorios activos. Devuelve cuántos se enviaron."""
    settings = get_settings()
    if not settings.push_configured:
        return 0
    now = now or datetime.now(settings.zone).replace(tzinfo=None)
    sent = 0
    with SessionLocal() as db, tenancy.unscoped(db):
        user_ids = list(
            db.scalars(
                select(User.id)
                .where(User.status == "approved")
                .where(User.id.in_(select(PushSubscription.user_id).distinct()))
            )
        )
    for user_id in user_ids:
        with SessionLocal() as db, tenancy.as_user(db, user_id):
            for kind, payload in due_for_user(db, user_id, now):
                delivered = push.send_to_user(db, user_id, payload) if payload else 0
                tenancy.scope(db, user_id)
                db.add(ReminderLog(date=now.date().isoformat(), kind=kind, sent=bool(delivered)))
                db.commit()
                sent += delivered
    if sent:
        log.info("Recordatorios enviados: %s", sent)
    return sent
