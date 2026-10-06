"""Acceso: inicio de sesión, solicitud de cuenta, estado de la sesión y salida.

Son las únicas rutas de /api que responden sin una cuenta aprobada (ver deps.PUBLIC_API_PATHS).
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import notify, services
from ..config import get_settings
from ..db import get_db
from ..deps import session_user
from ..models import AuthSession, User, utcnow
from ..schemas import LoginIn, RegisterIn
from ..security import (
    DUMMY_HASH,
    SESSION_COOKIE,
    hash_password,
    hash_token,
    login_throttle,
    new_session_token,
    password_problem,
    register_limit,
    username_problem,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("kcalia.auth")

REQUEST_RECEIVED = {
    "status": "received",
    "message": "Solicitud recibida. Cuando el administrador la apruebe podrás entrar con tu usuario y contraseña.",
}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def start_session(db: Session, response: Response, user: User) -> None:
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
    user.last_seen_at = utcnow()
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


def signup_state(db: Session) -> str:
    """first (instalación sin cuentas), open, closed (cerrado) o full (demasiadas solicitudes pendientes)."""
    settings = get_settings()
    if not db.scalar(select(func.count(User.id))):
        return "first"
    if not settings.allow_signup or not services.app_setting(db, "signup_open", True):
        return "closed"
    pending = db.scalar(select(func.count(User.id)).where(User.status == "pending")) or 0
    return "full" if pending >= settings.max_pending_accounts else "open"


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict:
    """La sesión actual (el «me» de la app): quién eres y en qué estado está tu cuenta."""
    user = session_user(request, db)
    state = signup_state(db)
    return {
        "registered": state != "first",
        "authenticated": user is not None,
        "username": user.username if user else None,
        "status": user.status if user else None,
        "is_admin": bool(user and user.is_admin),
        "signup": state,
    }


def _check_credentials(username: str, password: str) -> None:
    problem = username_problem(username) or password_problem(username, password)
    if problem:
        raise HTTPException(422, problem)


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    username = body.username.strip()
    state = signup_state(db)
    if state == "first":
        # Instalación nueva: la primera cuenta es la del administrador, aprobada y con sesión iniciada.
        _check_credentials(username, body.password)
        user = User(username=username, password_hash=hash_password(body.password), status="approved", is_admin=True)
        db.add(user)
        db.commit()
        start_session(db, response, user)
        return {"status": "approved", "username": user.username}

    if body.website.strip():
        # Campo trampa relleno: es un robot. Misma respuesta que a una persona y no se crea nada.
        log.info("Solicitud de cuenta descartada por el campo trampa")
        return REQUEST_RECEIVED
    if state == "closed":
        raise HTTPException(403, "Ahora mismo no se admiten cuentas nuevas.")
    if state == "full":
        raise HTTPException(
            503, "Hay muchas solicitudes pendientes de revisar. Vuelve a intentarlo dentro de unos días."
        )
    if not register_limit.allow(_client_ip(request)):
        raise HTTPException(429, "Demasiadas solicitudes desde esta conexión. Prueba dentro de una hora.")
    _check_credentials(username, body.password)

    exists = db.scalar(select(User.id).where(func.lower(User.username) == username.lower()))
    if exists is None:
        user = User(username=username, password_hash=hash_password(body.password), status="pending")
        db.add(user)
        db.commit()
        notify.new_account_request(db, user)
    else:
        # Ya existe: no se dice (ni se nota en el tiempo de respuesta). Quien sea, no podrá entrar.
        hash_password(body.password)
    return REQUEST_RECEIVED


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    name = body.username.strip().lower()
    keys = (f"ip:{_client_ip(request)}", f"user:{name}")
    wait = max(login_throttle.retry_after(key) for key in keys)
    if wait:
        when = f"{max(1, round(wait / 60))} min" if wait >= 60 else f"{wait} s"
        raise HTTPException(429, f"Demasiados intentos fallidos. Espera unos {when} y vuelve a probar.")
    user = db.scalar(select(User).where(func.lower(User.username) == name))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if user is None or not valid:
        for key in keys:
            login_throttle.fail(key)
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    for key in keys:
        login_throttle.reset(key)
    start_session(db, response, user)
    return {"username": user.username, "status": user.status}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
