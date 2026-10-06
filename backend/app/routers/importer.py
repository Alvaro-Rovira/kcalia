"""Importar datos desde otras apps (CSV) o desde una exportación de Kcalia (JSON). Necesita conexión."""

import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import importer, services
from ..db import get_db
from ..deps import require_approved_user, today_local
from ..matching import extras, totals
from ..models import Meal
from ..summary import week_start

router = APIRouter(prefix="/api/import", tags=["importar"], dependencies=[Depends(require_approved_user)])


def _read(upload: UploadFile) -> bytes:
    raw = upload.file.read(importer.MAX_BYTES + 1)
    if len(raw) > importer.MAX_BYTES:
        raise HTTPException(413, "El fichero pesa demasiado (máximo 5 MB).")
    if not raw:
        raise HTTPException(422, "El fichero está vacío.")
    return raw


def _prepare(raw: bytes, mapping: str, month_first: bool):
    try:
        parsed = importer.read_csv(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    guessed = importer.guess_mapping(parsed.columns)
    if mapping:
        try:
            chosen = json.loads(mapping)
        except ValueError as exc:
            raise HTTPException(422, "El mapeo de columnas no es válido.") from exc
        for key, column in chosen.items():
            if key in importer.FIELDS and (column is None or column in parsed.columns):
                guessed[key] = column
    return parsed, guessed, importer.prepare(parsed, guessed, month_first)


def _classify(db: Session, rows: list[importer.Row]) -> tuple[set[str], set[str]]:
    """client_id ya importados y los de filas que parecen ya apuntadas (mismo día, momento y calorías)."""
    ids = {r.client_id for r in rows}
    imported = set(db.scalars(select(Meal.client_id).where(Meal.client_id.in_(ids)))) if ids else set()
    dates = {r.date for r in rows}
    manual = (
        {
            (m.date, m.slot, round(m.kcal))
            for m in db.scalars(
                select(Meal).where(Meal.date.in_(dates), Meal.deleted_at.is_(None), Meal.client_id.not_like("imp-%"))
            )
        }
        if dates
        else set()
    )
    duplicates = {r.client_id for r in rows if (r.date, r.slot, round(r.kcal)) in manual}
    return imported, duplicates


@router.post("/csv/preview")
def preview(
    file: UploadFile = File(...),
    mapping: str = Form(default=""),
    month_first: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> dict:
    parsed, used, prepared = _prepare(_read(file), mapping, month_first)
    imported, duplicates = _classify(db, prepared.rows)
    return {
        "format": parsed.format,
        "columns": parsed.columns,
        "mapping": used,
        "rows": len(parsed.rows),
        "valid": len(prepared.rows),
        "new": sum(r.client_id not in imported and r.client_id not in duplicates for r in prepared.rows),
        "already": len(imported),
        "duplicates": len(duplicates - imported),
        "errors": prepared.errors[:20],
        "error_count": len(prepared.errors),
        "sample": [
            {
                "date": r.date,
                "slot": r.slot,
                "name": r.name,
                "kcal": r.kcal,
                "protein": r.protein,
                "carbs": r.carbs,
                "fat": r.fat,
            }
            for r in prepared.rows[:8]
        ],
    }


@router.post("/csv")
def import_csv(
    file: UploadFile = File(...),
    mapping: str = Form(default=""),
    month_first: bool = Form(default=False),
    skip_duplicates: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> dict:
    _, _, prepared = _prepare(_read(file), mapping, month_first)
    imported, duplicates = _classify(db, prepared.rows)
    created = skipped_dup = 0
    weeks: set[date] = set()
    for row in prepared.rows:
        if row.client_id in imported:
            continue
        if skip_duplicates and row.client_id in duplicates:
            skipped_dup += 1
            continue
        items = importer.meal_items(row)
        db.add(
            Meal(
                client_id=row.client_id,
                date=row.date,
                slot=row.slot,
                name=row.name[:160],
                text="",
                items=items,
                servings=1,
                source="import",
                confidence=0.7,
                assumptions=["Importada de otra app"],
                **totals(items),
                **extras(items),
            )
        )
        weeks.add(week_start(date.fromisoformat(row.date)))
        created += 1
    db.commit()
    today = today_local()
    for monday in weeks:
        services.refresh_week_if_stored(db, monday.isoformat(), today)
    services.ensure_summaries(db, today)
    return {
        "created": created,
        "already": len(imported),
        "skipped_duplicates": skipped_dup,
        "errors": len(prepared.errors),
    }


@router.post("/json")
def import_json(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    try:
        data = json.loads(_read(file).decode("utf-8-sig"))
        counts = importer.import_kcalia(db, data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc) if "Kcalia" in str(exc) else "El fichero no es un JSON válido.") from exc
    services.ensure_summaries(db, today_local())
    return {"created": counts}
