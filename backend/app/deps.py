from datetime import datetime, timedelta
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tenancy
from .ai import AiClient
from .config import Settings, get_settings
from .db import get_db
from .models import AuthSession, User, utcnow
from .security import SESSION_COOKIE, hash_token

# Lo único que responde sin una cuenta aprobada. Cerrar sesión también: una cuenta pendiente o bloqueada
# tiene que poder salir. Cualquier otra ruta de /api, también las que se añadan mañana, exige cuenta aprobada.
PUBLIC_API_PATHS = frozenset(
    {"/api/health", "/api/auth/login", "/api/auth/register", "/api/auth/status", "/api/auth/logout"}
)

STATUS_MESSAGES = {
    "pending": "Tu cuenta está pendiente de aprobación. Podrás usar la app en cuanto el administrador la apruebe.",
    "suspended": "Tu cuenta está bloqueada. Si crees que es un error, habla con el administrador.",
}


def today_local(settings: Settings | None = None):
    settings = settings or get_settings()
    return datetime.now(settings.zone).date()


@lru_cache
def get_ai_client() -> AiClient:
    return AiClient(get_settings())


def current_session(request: Request, db: Session) -> AuthSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None:
        return None
    now = utcnow()
    if session.expires_at < now:
        db.delete(session)
        db.commit()
        return None
    # Sesión deslizante: se renueva con el uso, como mucho una escritura por hora.
    if now - session.last_seen > timedelta(hours=1):
        session.last_seen = now
        session.expires_at = now + timedelta(days=get_settings().session_days)
        user = db.get(User, session.user_id)
        if user is not None:
            user.last_seen_at = now
        db.commit()
    return session


def session_user(request: Request, db: Session) -> User | None:
    session = current_session(request, db)
    return db.get(User, session.user_id) if session else None


def _unauthenticated(request: Request) -> HTTPException:
    had_cookie = SESSION_COOKIE in request.cookies
    return HTTPException(
        status_code=401,
        detail={
            "code": "session_expired" if had_cookie else "unauthenticated",
            "message": "Tu sesión ha caducado. Vuelve a entrar." if had_cookie else "Inicia sesión para continuar.",
        },
    )


def enforce_access(request: Request, db: Session = Depends(get_db)) -> None:
    """Dependencia global de la app: toda ruta /api no pública exige una cuenta aprobada.

    Además deja la sesión de base de datos limitada a los datos de ese usuario (ver tenancy.py).
    """
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_API_PATHS:
        return
    user = session_user(request, db)
    if user is None:
        raise _unauthenticated(request)
    if user.status != "approved":
        raise HTTPException(
            status_code=403,
            detail={"code": f"account_{user.status}", "message": STATUS_MESSAGES.get(user.status, "Sin acceso.")},
        )
    tenancy.scope(db, user.id)
    request.state.user = user


def require_user(request: Request) -> User:
    """El usuario aprobado de esta petición (lo deja `enforce_access`)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise _unauthenticated(request)
    return user


# Nombre explícito para leer los routers: la comprobación de aprobación la hace siempre enforce_access.
require_approved_user = require_user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = require_user(request)
    if not user.is_admin:
        raise HTTPException(403, "Esto solo puede verlo el administrador.")
    # El panel trabaja con las cuentas de todos.
    db.info[tenancy.ALL_KEY] = True
    return user
