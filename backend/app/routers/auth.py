from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_session
from ..models import AuthSession, User, utcnow
from ..schemas import Credentials
from ..security import (
    SESSION_COOKIE,
    hash_password,
    hash_token,
    login_throttle,
    new_session_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def _start_session(db: Session, response: Response, user: User) -> None:
    settings = get_settings()
    token, token_hash = new_session_token()
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))
    db.add(
        AuthSession(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=settings.session_days),
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict:
    registered = (db.scalar(select(func.count(User.id))) or 0) > 0
    session = current_session(request, db)
    user = db.get(User, session.user_id) if session else None
    return {
        "registered": registered,
        "authenticated": user is not None,
        "username": user.username if user else None,
    }


@router.post("/register")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(func.count(User.id))):
        raise HTTPException(403, "El registro está cerrado: esta instalación ya tiene su cuenta.")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _start_session(db, response, user)
    return {"username": user.username}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    ip = _client_ip(request)
    wait = login_throttle.retry_after(ip)
    if wait:
        minutes = max(1, round(wait / 60))
        raise HTTPException(429, f"Demasiados intentos fallidos. Espera unos {minutes} min y vuelve a probar.")
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.lower()))
    if user is None or not verify_password(user.password_hash, body.password):
        login_throttle.fail(ip)
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    login_throttle.reset(ip)
    _start_session(db, response, user)
    return {"username": user.username}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
