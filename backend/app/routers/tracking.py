"""Seguimiento además de la comida: preferencias, agua, medidas corporales y fotos de progreso."""

from datetime import date as date_type

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..deps import require_approved_user
from ..models import MEASURES, BodyMeasurement, ProgressPhoto, WaterLog
from ..schemas import MeasurementIn, PrefsPatch, WaterIn

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


# ---------------------------------------------------------------- medidas corporales


def _measure_dict(row: BodyMeasurement) -> dict:
    return {"date": row.date, **{m: getattr(row, m) for m in MEASURES}}


@router.get("/measurements")
def list_measurements(db: Session = Depends(get_db)) -> dict:
    rows = db.scalars(select(BodyMeasurement).order_by(BodyMeasurement.date))
    return {"entries": [_measure_dict(r) for r in rows]}


@router.put("/measurements")
def save_measurement(body: MeasurementIn, db: Session = Depends(get_db)) -> dict:
    """Guarda las medidas de un día (idempotente: el mismo día se sobrescribe). Sin ninguna medida, lo borra."""
    row = db.scalar(select(BodyMeasurement).where(BodyMeasurement.date == body.date))
    values = {m: getattr(body, m) for m in MEASURES}
    if all(v is None for v in values.values()):
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(BodyMeasurement(date=body.date, **values))
    else:
        for key, value in values.items():
            setattr(row, key, value)
    db.commit()
    return list_measurements(db)


@router.delete("/measurements/{date}")
def delete_measurement(date: str, db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(BodyMeasurement).where(BodyMeasurement.date == _iso(date)))
    if row is not None:
        db.delete(row)
        db.commit()
    return list_measurements(db)


# ---------------------------------------------------------------- fotos de progreso

PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_BYTES = 4 * 1024 * 1024


def _photo_dict(row: ProgressPhoto) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "date": row.date,
        "size": row.size,
        "created_at": row.created_at.isoformat() + "Z",
    }


@router.get("/photos")
def list_photos(db: Session = Depends(get_db)) -> dict:
    # Sin la imagen: la columna `data` es diferida y aquí no se toca.
    rows = db.scalars(select(ProgressPhoto).order_by(ProgressPhoto.date.desc(), ProgressPhoto.id.desc()))
    return {"photos": [_photo_dict(r) for r in rows]}


@router.post("/photos", status_code=201)
def upload_photo(
    image: UploadFile = File(...),
    date: str = Form(...),
    client_id: str = Form(..., min_length=8, max_length=40),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(select(ProgressPhoto).where(ProgressPhoto.client_id == client_id))
    if existing is not None:
        return _photo_dict(existing)  # reintento: ya estaba
    mime = (image.content_type or "").lower()
    if mime not in PHOTO_TYPES:
        raise HTTPException(415, "Ese formato de imagen no me vale. Prueba con una foto JPG o PNG.")
    data = image.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "La foto pesa demasiado.")
    if not data:
        raise HTTPException(422, "La foto está vacía.")
    row = ProgressPhoto(client_id=client_id, date=_iso(date), mime=mime, size=len(data), data=data)
    db.add(row)
    db.commit()
    return _photo_dict(row)


@router.get("/photos/{photo_id}/image")
def photo_image(photo_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.get(ProgressPhoto, photo_id)
    if row is None:
        raise HTTPException(404, "Esa foto ya no existe.")
    return Response(row.data, media_type=row.mime, headers={"Cache-Control": "private, max-age=604800"})


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(ProgressPhoto, photo_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return {"ok": True}
