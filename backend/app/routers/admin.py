"""Panel de administración: cuentas, consumo de IA y voz, y ajustes de la instalación.

Solo para el administrador (403 a cualquier otra cuenta, también desde la API). Cada acción queda en la auditoría.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import offsite, services
from ..config import get_settings
from ..db import get_db
from ..deps import require_admin, today_local
from ..jobs import BACKUP_STATUS_KEY
from ..models import AdminAudit, AiUsage, AuthSession, User
from ..usage import ai_limit_for, stt_limit_for
from .auth import signup_state

router = APIRouter(prefix="/api/admin", tags=["administración"], dependencies=[Depends(require_admin)])


class LimitsIn(BaseModel):
    # None vuelve al valor por defecto de la configuración.
    ai_daily_limit: int | None = Field(default=None, ge=0, le=10000)
    stt_daily_limit: int | None = Field(default=None, ge=0, le=10000)


class SettingsIn(BaseModel):
    ai_paused: bool | None = None
    signup_open: bool | None = None


class ConfirmIn(BaseModel):
    # Hay que escribir el nombre de la cuenta: borrar es irreversible.
    confirm: str = Field(min_length=1, max_length=64)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _audit(db: Session, admin: User, action: str, target: User | None = None, **details) -> None:
    db.add(
        AdminAudit(
            admin_id=admin.id,
            admin_username=admin.username,
            action=action,
            target_user_id=target.id if target else None,
            target_username=target.username if target else "",
            details=details,
        )
    )


def _usage(db: Session, since: date, until: date) -> dict[int, dict]:
    """Uso por usuario entre dos fechas, en una sola consulta."""
    rows = db.execute(
        select(
            AiUsage.user_id,
            AiUsage.kind,
            func.sum(AiUsage.calls),
            func.sum(AiUsage.prompt_tokens),
            func.sum(AiUsage.completion_tokens),
        )
        .where(AiUsage.date >= since.isoformat(), AiUsage.date <= until.isoformat())
        .group_by(AiUsage.user_id, AiUsage.kind)
    )
    usage: dict[int, dict] = {}
    for user_id, kind, calls, prompt, completion in rows:
        entry = usage.setdefault(user_id, {"ai": 0, "stt": 0, "prompt_tokens": 0, "completion_tokens": 0})
        if kind == "stt":
            entry["stt"] += int(calls or 0)
        else:
            entry["ai"] += int(calls or 0)
            entry["prompt_tokens"] += int(prompt or 0)
            entry["completion_tokens"] += int(completion or 0)
    return usage


def _cost(entry: dict | None) -> float:
    if not entry:
        return 0.0
    s = get_settings()
    cost = entry["prompt_tokens"] / 1e6 * s.ai_price_input + entry["completion_tokens"] / 1e6 * s.ai_price_output
    return round(cost + entry["stt"] * s.stt_price_per_call, 4)


def _totals(usage: dict[int, dict]) -> dict:
    total = {"ai": 0, "stt": 0, "prompt_tokens": 0, "completion_tokens": 0}
    for entry in usage.values():
        for key in total:
            total[key] += entry[key]
    return {**total, "cost": _cost(total)}


def _user_dict(user: User, today: dict, month: dict, sessions: int) -> dict:
    settings = get_settings()
    empty = {"ai": 0, "stt": 0, "prompt_tokens": 0, "completion_tokens": 0}
    return {
        "id": user.id,
        "username": user.username,
        "status": user.status,
        "is_admin": user.is_admin,
        "created_at": _iso(user.created_at),
        "last_seen_at": _iso(user.last_seen_at),
        "sessions": sessions,
        "limits": {
            "ai": ai_limit_for(user, settings),
            "stt": stt_limit_for(user, settings),
            "ai_custom": user.ai_daily_limit,
            "stt_custom": user.stt_daily_limit,
        },
        "today": {**(today or empty), "cost": _cost(today)},
        "month": {**(month or empty), "cost": _cost(month)},
    }


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta ya no existe.")
    return user


def _not_self(admin: User, user: User, what: str) -> None:
    if admin.id == user.id:
        raise HTTPException(409, f"No puedes {what} tu propia cuenta de administrador.")


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    today = today_local(settings)
    month_start = today.replace(day=1)
    statuses = dict(db.execute(select(User.status, func.count(User.id)).group_by(User.status)).all())
    return {
        "pending": statuses.get("pending", 0),
        "users": {"total": sum(statuses.values()), **{key: statuses.get(key, 0) for key in ("approved", "suspended")}},
        "today": {
            **_totals(_usage(db, today, today)),
            "ai_limit": settings.ai_daily_limit,
            "stt_limit": settings.stt_daily_limit,
        },
        "month": _totals(_usage(db, month_start, today)),
        "ai_paused": services.ai_paused(db),
        "signup": {
            "state": signup_state(db),
            "allowed_by_server": settings.allow_signup,
            "open": bool(services.app_setting(db, "signup_open", True)),
            "max_pending": settings.max_pending_accounts,
        },
        "defaults": {
            "ai_user_daily_limit": settings.ai_user_daily_limit,
            "stt_user_daily_limit": settings.stt_user_daily_limit,
            "admin_ai_daily_limit": settings.admin_ai_limit,
        },
        "backup": {
            "configured": offsite.configured(settings),
            "local_keep": settings.backup_keep,
            "remote_keep": settings.backup_remote_keep,
            "encrypted": bool(settings.backup_encryption_key),
            **(services.app_setting(db, BACKUP_STATUS_KEY, {}) or {}),
        },
        "prices": {
            "ai_input_per_million": settings.ai_price_input,
            "ai_output_per_million": settings.ai_price_output,
            "stt_per_call": settings.stt_price_per_call,
        },
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)) -> dict:
    today = today_local()
    usage_today = _usage(db, today, today)
    usage_month = _usage(db, today.replace(day=1), today)
    sessions = dict(
        db.execute(select(AuthSession.user_id, func.count(AuthSession.id)).group_by(AuthSession.user_id)).all()
    )
    # Primero las solicitudes pendientes (las más antiguas arriba), luego el resto por fecha de alta.
    order = {"pending": 0, "approved": 1, "suspended": 2}
    users = sorted(db.scalars(select(User)), key=lambda u: (order.get(u.status, 3), u.created_at))
    return {
        "users": [_user_dict(u, usage_today.get(u.id), usage_month.get(u.id), sessions.get(u.id, 0)) for u in users]
    }


@router.post("/users/{user_id}/approve")
def approve(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = _get_user(db, user_id)
    if user.status != "pending":
        raise HTTPException(409, "Esa cuenta no está pendiente de aprobación.")
    user.status = "approved"
    _audit(db, admin, "approve", user)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reject")
def reject(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Rechazar una solicitud borra la cuenta pendiente (no tiene datos)."""
    user = _get_user(db, user_id)
    _not_self(admin, user, "rechazar")
    if user.status != "pending":
        raise HTTPException(409, "Solo se pueden rechazar solicitudes pendientes.")
    _audit(db, admin, "reject", user)
    services.delete_user(db, user)
    return {"ok": True}


@router.post("/users/{user_id}/suspend")
def suspend(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = _get_user(db, user_id)
    _not_self(admin, user, "bloquear")
    user.status = "suspended"
    _audit(db, admin, "suspend", user)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/unsuspend")
def unsuspend(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = _get_user(db, user_id)
    if user.status != "suspended":
        raise HTTPException(409, "Esa cuenta no está bloqueada.")
    user.status = "approved"
    _audit(db, admin, "unsuspend", user)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/delete")
def delete_account(
    user_id: int, body: ConfirmIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    user = _get_user(db, user_id)
    _not_self(admin, user, "eliminar")
    if body.confirm.strip().lower() != user.username.lower():
        raise HTTPException(422, "Escribe el nombre de la cuenta exactamente para confirmar el borrado.")
    _audit(db, admin, "delete", user, status=user.status)
    services.delete_user(db, user)
    return {"ok": True}


@router.patch("/users/{user_id}/limits")
def set_limits(
    user_id: int, body: LimitsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    user = _get_user(db, user_id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(user, key, value)
    _audit(db, admin, "limits", user, **changes)
    db.commit()
    return {"ok": True, "limits": {"ai": ai_limit_for(user), "stt": stt_limit_for(user)}}


@router.post("/users/{user_id}/logout-all")
def logout_all(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = _get_user(db, user_id)
    closed = db.execute(delete(AuthSession).where(AuthSession.user_id == user.id)).rowcount
    _audit(db, admin, "logout_all", user, sessions=closed)
    db.commit()
    return {"ok": True, "closed": closed}


@router.patch("/settings")
def update_settings(body: SettingsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    changes = body.model_dump(exclude_none=True)
    for key, value in changes.items():
        services.set_app_setting(db, key, value)
    if changes:
        _audit(db, admin, "settings", None, **changes)
    db.commit()
    return {"ai_paused": services.ai_paused(db), "signup_open": bool(services.app_setting(db, "signup_open", True))}


@router.get("/audit")
def audit_log(limit: int = Query(default=60, ge=1, le=500), db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(AdminAudit).order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc()).limit(limit))
    return {
        "entries": [
            {
                "id": row.id,
                "admin": row.admin_username,
                "action": row.action,
                "target": row.target_username,
                "details": row.details,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }
