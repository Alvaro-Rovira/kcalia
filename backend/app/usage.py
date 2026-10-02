"""Cupo diario de IA y registro de uso: lo comparten las comidas y la lectura de etiquetas."""

from sqlalchemy.orm import Session

from . import services
from .ai import AiError, AiMeal
from .config import get_settings
from .deps import today_local


def check_ai_budget(db: Session) -> None:
    settings = get_settings()
    if services.ai_calls_today(db, today_local(settings)) >= settings.ai_daily_limit:
        raise AiError(
            "limit",
            f"Has llegado al límite de {settings.ai_daily_limit} consultas a la IA de hoy. "
            "Las comidas de tu historial siguen funcionando.",
            429,
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


__all__ = ["AiMeal", "check_ai_budget", "run_ai"]
