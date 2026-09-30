from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..config import get_settings
from ..db import get_db
from ..deps import require_user, today_local
from ..models import WeeklySummary
from ..summary import week_start

router = APIRouter(prefix="/api", tags=["resumen"], dependencies=[Depends(require_user)])


@router.get("/summary/week")
def week(start: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Resumen de una semana calculado al momento (la actual, si no se indica otra)."""
    targets = services.get_targets(db)
    if targets is None:
        raise HTTPException(409, "Completa primero tu perfil.")
    today = today_local()
    try:
        monday = week_start(date.fromisoformat(start)) if start else week_start(today)
    except ValueError as exc:
        raise HTTPException(422, "Esa fecha no es válida.") from exc
    return services.compute_week(db, monday, today, targets)


@router.get("/summary/history")
def history(db: Session = Depends(get_db)) -> dict:
    today = today_local()
    services.ensure_summaries(db, today)
    rows = db.scalars(select(WeeklySummary).order_by(WeeklySummary.week_start.desc()).limit(104)).all()
    return {"summaries": [row.data for row in rows]}


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return services.compute_stats(db, today_local(settings), settings.ai_daily_limit)
