"""Seguimiento además de la comida: preferencias y agua."""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..deps import require_approved_user
from ..models import WaterLog
from ..schemas import PrefsPatch, WaterIn

router = APIRouter(prefix="/api", tags=["seguimiento"], dependencies=[Depends(require_approved_user)])


def _iso(value: str) -> str:
    try:
        date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, "Esa fecha no es válida.") from exc
    return value


@router.get("/prefs")
def get_prefs(db: Session = Depends(get_db)) -> dict:
    return services.get_prefs(db).model_dump()


@router.patch("/prefs")
def patch_prefs(body: PrefsPatch, db: Session = Depends(get_db)) -> dict:
    prefs = services.update_prefs(db, body.model_dump(exclude_unset=True))
    db.commit()
    return prefs.model_dump()


def _water_day(db: Session, day: str) -> dict:
    entries = db.scalars(select(WaterLog).where(WaterLog.date == day).order_by(WaterLog.created_at, WaterLog.id)).all()
    return {
        "date": day,
        "total_ml": sum(e.ml for e in entries),
        "goal_ml": services.water_goal(db),
        "entries": [
            {"client_id": e.client_id, "ml": e.ml, "created_at": e.created_at.isoformat() + "Z"} for e in entries
        ],
    }


@router.get("/water")
def water_day(date: str, db: Session = Depends(get_db)) -> dict:
    return _water_day(db, _iso(date))


@router.get("/water/days")
def water_days(start: str, end: str, db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(WaterLog.date, func.sum(WaterLog.ml))
        .where(WaterLog.date >= _iso(start), WaterLog.date <= _iso(end))
        .group_by(WaterLog.date)
        .order_by(WaterLog.date)
    )
    return {"goal_ml": services.water_goal(db), "days": [{"date": d, "ml": int(ml or 0)} for d, ml in rows]}


@router.post("/water", status_code=201)
def add_water(body: WaterIn, db: Session = Depends(get_db)) -> dict:
    # Reintento de la cola offline: mismo client_id, no se suma dos veces.
    if db.scalar(select(WaterLog.id).where(WaterLog.client_id == body.client_id)) is None:
        db.add(WaterLog(client_id=body.client_id, date=body.date, ml=body.ml))
        db.commit()
    return _water_day(db, body.date)


@router.delete("/water/{client_id}")
def delete_water(client_id: str, db: Session = Depends(get_db)) -> dict:
    entry = db.scalar(select(WaterLog).where(WaterLog.client_id == client_id))
    if entry is None:
        return {"ok": True}  # ya borrado (la cola puede repetirlo)
    day = entry.date
    db.delete(entry)
    db.commit()
    return _water_day(db, day)
