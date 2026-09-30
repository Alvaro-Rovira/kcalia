from datetime import datetime, timedelta
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import AiClient
from .config import Settings, get_settings
from .db import get_db
from .models import AuthSession, User, utcnow
from .security import SESSION_COOKIE, hash_token


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
        db.commit()
    return session


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = current_session(request, db)
    if session is None:
        had_cookie = SESSION_COOKIE in request.cookies
        raise HTTPException(
            status_code=401,
            detail={
                "code": "session_expired" if had_cookie else "unauthenticated",
                "message": "Tu sesión ha caducado. Vuelve a entrar." if had_cookie else "Inicia sesión para continuar.",
            },
        )
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=401, detail={"code": "unauthenticated", "message": "Inicia sesión para continuar."}
        )
    return user
