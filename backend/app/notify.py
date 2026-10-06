"""Avisos al administrador. El aviso por notificación push llega con los recordatorios (fase 4.1);
mientras tanto, las solicitudes pendientes se ven con el indicador del panel de administración."""

import logging

from sqlalchemy.orm import Session

from .models import User

log = logging.getLogger("kcalia.notify")


def new_account_request(db: Session, user: User) -> None:
    log.info("Nueva solicitud de cuenta: %s", user.username)
