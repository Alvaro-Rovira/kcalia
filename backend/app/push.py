"""Envío de notificaciones Web Push a las suscripciones de un usuario, con limpieza de las caducadas."""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tenancy, webpush
from .config import get_settings
from .models import PushSubscription, utcnow

log = logging.getLogger("kcalia.push")

MAX_FAILURES = 5
_http: httpx.Client | None = None


def http_client() -> httpx.Client:
    """Cliente HTTP compartido. Las pruebas lo sustituyen por uno simulado (nunca se llama a un servicio real)."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=10)
    return _http


def set_http_client(client: httpx.Client | None) -> None:
    global _http
    _http = client


def send_to_user(db: Session, user_id: int, payload: dict) -> int:
    """Envía `payload` ({title, body, url, tag}) a todos los dispositivos del usuario.

    Devuelve cuántos lo recibieron.
    """
    settings = get_settings()
    if not settings.push_configured:
        return 0
    sent = 0
    with tenancy.as_user(db, user_id):
        for sub in db.scalars(select(PushSubscription)).all():
            result = webpush.send(
                sub.endpoint,
                sub.p256dh,
                sub.auth,
                payload,
                private_key=settings.vapid_private_key,
                public_key=settings.vapid_public_key,
                subject=settings.vapid_subject or f"https://{settings.domain}",
                http=http_client(),
            )
            if result.ok:
                sent += 1
                sub.last_ok_at, sub.failures = utcnow(), 0
            elif result.gone:
                # 404/410: el navegador ya no la usa (desinstalada, permisos retirados...). Se borra.
                log.info("Suscripción caducada (%s): se borra", result.status)
                db.delete(sub)
            else:
                sub.failures += 1
                if sub.failures >= MAX_FAILURES:
                    log.warning("Suscripción con %s fallos seguidos: se borra", sub.failures)
                    db.delete(sub)
        db.commit()
    return sent
