"""Avisos al administrador (si tiene el push activado): solicitudes de cuenta y errores del servidor.

Sin push, el panel de administración muestra las solicitudes pendientes y los errores recientes.
"""

import logging
import threading
import time
from collections import deque
from datetime import UTC, datetime

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


# ---------------------------------------------------------------- errores del servidor

ERROR_ALERT_EVERY = 15 * 60  # como mucho un aviso cada cuarto de hora; los demás se cuentan en el siguiente
_lock = threading.Lock()
_recent: deque[dict] = deque(maxlen=20)
_state = {"last_alert": float("-inf"), "silenced": 0, "total": 0}


def reset_errors() -> None:
    with _lock:
        _recent.clear()
        _state.update(last_alert=float("-inf"), silenced=0, total=0)


def recent_errors() -> list[dict]:
    with _lock:
        return list(_recent)


def errors_summary() -> dict:
    with _lock:
        return {"total": _state["total"], "recent": list(_recent)}


def server_error(method: str, path: str, exc: BaseException, clock=time.monotonic) -> bool:
    """Apunta un 500 y avisa al administrador si hace más de un cuarto de hora del último aviso.

    Solo el tipo de error y la ruta: ni el mensaje ni el cuerpo, que pueden llevar datos de alguien.
    Devuelve si se ha enviado el aviso. Nunca lanza: un aviso que falla no puede empeorar el error.
    """
    kind = type(exc).__name__
    now = clock()
    with _lock:
        _recent.appendleft({"at": datetime.now(UTC).isoformat(timespec="seconds"), "method": method, "path": path,
                            "error": kind})  # fmt: skip
        _state["total"] += 1
        if now - _state["last_alert"] < ERROR_ALERT_EVERY:
            _state["silenced"] += 1
            return False
        silenced, _state["silenced"], _state["last_alert"] = _state["silenced"], 0, now
    extra = f" (y {silenced} más desde el último aviso)" if silenced else ""
    try:
        from .db import SessionLocal

        with SessionLocal() as db, tenancy.unscoped(db):
            admin = db.scalar(select(User).where(User.is_admin.is_(True)))
            if admin is not None:
                push.send_to_user(
                    db,
                    admin.id,
                    {
                        "title": "Kcalia ha tenido un error",
                        "body": f"{kind} en {method} {path}{extra}. Detalles en el registro del contenedor.",
                        "url": "/admin",
                        "tag": "kcalia-error",
                    },
                )
                db.commit()
    except Exception:
        log.exception("No se ha podido avisar del error al administrador")
    return True
