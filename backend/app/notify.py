"""Avisos al administrador: una notificación cuando alguien solicita una cuenta (si tiene el push activado).

Sin push, basta con el indicador de solicitudes pendientes del panel de administración.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import push, tenancy
from .models import User

log = logging.getLogger("kcalia.notify")


def new_account_request(db: Session, user: User) -> None:
    log.info("Nueva solicitud de cuenta: %s", user.username)
    admin = db.scalar(select(User).where(User.is_admin.is_(True)))
    if admin is None:
        return
    try:
        with tenancy.unscoped(db):
            push.send_to_user(
                db,
                admin.id,
                {
                    "title": "Nueva solicitud de cuenta",
                    "body": f"{user.username} quiere usar Kcalia. Apruébala o recházala en el panel.",
                    "url": "/admin",
                    "tag": "kcalia-admin",
                },
            )
    except Exception:  # un aviso que falla no puede romper el registro
        log.exception("No se ha podido avisar al administrador")
