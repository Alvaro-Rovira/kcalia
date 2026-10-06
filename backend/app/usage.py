"""Cupos diarios de IA y de voz, y registro de uso.

Una consulta a la IA (o un audio) solo sale si se cumplen a la vez: cuenta aprobada, límite del usuario, límite
global de la instalación e interruptor de la IA activo. El administrador solo está sujeto a su propio límite (y al
interruptor, que controla él): lo que gasten los demás no le bloquea.
"""

from sqlalchemy.orm import Session

from . import services
from .ai import AiError, AiMeal
from .config import Settings, get_settings
from .deps import today_local
from .models import User


def ai_limit_for(user: User, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    if user.ai_daily_limit is not None:
        return user.ai_daily_limit
    return settings.admin_ai_limit if user.is_admin else settings.ai_user_daily_limit


def stt_limit_for(user: User, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    if user.stt_daily_limit is not None:
        return user.stt_daily_limit
    return settings.stt_daily_limit if user.is_admin else settings.stt_user_daily_limit


def _check(db: Session, user: User, *, kinds: tuple[str, ...], limit: int, global_limit: int, what: str) -> None:
    if user.status != "approved":
        raise AiError("not_approved", "Tu cuenta todavía no está aprobada.", 403)
    if services.ai_paused(db):
        raise AiError(
            "paused",
            "El administrador ha pausado la IA y la voz por ahora. Tu historial y tus productos siguen funcionando.",
            503,
        )
    today = today_local()
    if services.ai_calls_today(db, today, kinds) >= limit:
        raise AiError("limit", f"Has llegado a tu límite de {limit} {what} de hoy. Mañana se renueva.", 429)
    if not user.is_admin and services.global_calls_today(db, today, kinds) >= global_limit:
        raise AiError(
            "global_limit",
            f"Hoy se ha agotado el cupo de {what} de esta instalación. Mañana se renueva; mientras, tu historial "
            "y tus productos siguen funcionando.",
            429,
        )


def check_ai_budget(db: Session, user: User) -> None:
    settings = get_settings()
    _check(
        db,
        user,
        kinds=services.AI_KINDS,
        limit=ai_limit_for(user, settings),
        global_limit=settings.ai_daily_limit,
        what="consultas a la IA",
    )


def check_stt_budget(db: Session, user: User) -> None:
    settings = get_settings()
    _check(
        db,
        user,
        kinds=("stt",),
        limit=stt_limit_for(user, settings),
        global_limit=settings.stt_daily_limit,
        what="audios",
    )


def run_ai(db: Session, kind: str, call):
    """Ejecuta una llamada a la IA y apunta su uso (también el de las que fallan tras gastar tokens)."""
    today = today_local()
    try:
        result, usage = call()
    except AiError as error:
        usage = getattr(error, "usage", None)
        if usage:
            services.record_usage(db, today, kind, usage)
        raise
    services.record_usage(db, today, kind, usage)
    return result


__all__ = ["AiMeal", "ai_limit_for", "check_ai_budget", "check_stt_budget", "run_ai", "stt_limit_for"]
