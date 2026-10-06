import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import services
from .. import workouts as training_lib
from ..db import get_db
from ..deps import require_approved_user, require_user
from ..models import (
    MEASURES,
    BodyMeasurement,
    Exercise,
    Food,
    Meal,
    MealPlan,
    ShoppingCheck,
    User,
    WaterLog,
    WeeklySummary,
    Weight,
    Workout,
    WorkoutSet,
    WorkoutTemplate,
)
from ..schemas import PasswordConfirm
from ..security import SESSION_COOKIE, verify_password

router = APIRouter(prefix="/api", tags=["cuenta"], dependencies=[Depends(require_approved_user)])


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d")


def _download(content: str, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _live_meals(db: Session) -> list[Meal]:
    return list(db.scalars(select(Meal).where(Meal.deleted_at.is_(None)).order_by(Meal.date, Meal.created_at)))


@router.get("/export/json")
def export_json(db: Session = Depends(get_db)) -> dict:
    profile, targets = services.get_profile(db), services.get_targets(db)
    return {
        "app": "Kcalia",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "profile": services.profile_dict(profile) if profile else None,
        "targets": services.targets_dict(targets) if targets else None,
        "meals": [services.meal_dict(m) for m in _live_meals(db)],
        "weights": [{"date": w.date, "kg": w.kg} for w in db.scalars(select(Weight).order_by(Weight.date))],
        "dishes": services.all_dishes(db, limit=100000),
        "products": [services.product_dict(p) for p in services.all_products(db)],
        "foods": [
            {
                "name": f.name,
                "kcal100": f.kcal100,
                "protein100": f.protein100,
                "carbs100": f.carbs100,
                "fat100": f.fat100,
                "fiber100": f.fiber100,
                "alcohol100": f.alcohol100,
                "unit_grams": f.unit_grams,
            }
            for f in db.scalars(select(Food).order_by(Food.name))
        ],
        "weekly_summaries": [s.data for s in db.scalars(select(WeeklySummary).order_by(WeeklySummary.week_start))],
        "prefs": services.get_prefs(db).model_dump(),
        "day_types": services.day_type_overrides(db),
        "meal_plans": [
            {
                "client_id": p.client_id,
                "date": p.date,
                "slot": p.slot,
                "name": p.name,
                "items": p.items,
                "servings": p.servings,
            }
            for p in db.scalars(select(MealPlan).order_by(MealPlan.date, MealPlan.created_at))
        ],
        "shopping_checks": [
            {"week_start": c.week_start, "key": c.key, "checked": c.checked}
            for c in db.scalars(select(ShoppingCheck).order_by(ShoppingCheck.week_start, ShoppingCheck.key))
        ],
        "exercises": [training_lib.exercise_dict(e) for e in db.scalars(select(Exercise).order_by(Exercise.id))],
        "workout_templates": [
            training_lib.template_dict(t)
            for t in db.scalars(select(WorkoutTemplate).order_by(WorkoutTemplate.position))
        ],
        "workouts": training_lib.workouts_payload(
            db, list(db.scalars(select(Workout).order_by(Workout.date, Workout.started_at)))
        ),
        "measurements": [
            {"date": m.date, **{key: getattr(m, key) for key in MEASURES}}
            for m in db.scalars(select(BodyMeasurement).order_by(BodyMeasurement.date))
        ],
        # Las fotos de progreso no se exportan (son imágenes; siguen en la base y en sus copias).
        "water": [
            {"client_id": w.client_id, "date": w.date, "ml": w.ml}
            for w in db.scalars(select(WaterLog).order_by(WaterLog.date, WaterLog.created_at))
        ],
    }


def _es(number: float) -> str:
    """Decimales con coma, para que Excel en español los lea como números."""
    return f"{number:.1f}".replace(".", ",")


@router.get("/export/meals.csv")
def export_meals_csv(db: Session = Depends(get_db)) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(
        [
            "fecha",
            "momento",
            "comida",
            "raciones",
            "kcal",
            "proteinas_g",
            "hidratos_g",
            "grasas_g",
            "fibra_g",
            "alcohol_g",
            "origen",
            "ingredientes",
        ]
    )
    for meal in _live_meals(db):
        ingredients = " | ".join(f"{i['name']} ({_es(i.get('grams', 0))} g)" for i in meal.items)
        writer.writerow(
            [
                meal.date,
                meal.slot,
                meal.name,
                _es(meal.servings),
                _es(meal.kcal),
                _es(meal.protein),
                _es(meal.carbs),
                _es(meal.fat),
                _es(meal.fiber or 0),
                _es(meal.alcohol or 0),
                meal.source,
                ingredients,
            ]
        )
    # BOM para que Excel detecte UTF-8.
    return _download("﻿" + out.getvalue(), f"kcalia-comidas-{_stamp()}.csv", "text/csv; charset=utf-8")


@router.get("/export/weights.csv")
def export_weights_csv(db: Session = Depends(get_db)) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["fecha", "peso_kg"])
    for weight in db.scalars(select(Weight).order_by(Weight.date)):
        writer.writerow([weight.date, f"{weight.kg:.2f}".replace(".", ",")])
    return _download("﻿" + out.getvalue(), f"kcalia-peso-{_stamp()}.csv", "text/csv; charset=utf-8")


@router.get("/export/water.csv")
def export_water_csv(db: Session = Depends(get_db)) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["fecha", "agua_ml"])
    rows = db.execute(select(WaterLog.date, func.sum(WaterLog.ml)).group_by(WaterLog.date).order_by(WaterLog.date))
    for day, ml in rows:
        writer.writerow([day, int(ml or 0)])
    return _download("\ufeff" + out.getvalue(), f"kcalia-agua-{_stamp()}.csv", "text/csv; charset=utf-8")


@router.get("/export/measurements.csv")
def export_measurements_csv(db: Session = Depends(get_db)) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["fecha", "cintura_cm", "pecho_cm", "brazo_cm", "cadera_cm", "muslo_cm"])
    for row in db.scalars(select(BodyMeasurement).order_by(BodyMeasurement.date)):
        writer.writerow([row.date, *("" if getattr(row, m) is None else _es(getattr(row, m)) for m in MEASURES)])
    return _download("\ufeff" + out.getvalue(), f"kcalia-medidas-{_stamp()}.csv", "text/csv; charset=utf-8")


@router.get("/export/workouts.csv")
def export_workouts_csv(db: Session = Depends(get_db)) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["fecha", "entreno", "ejercicio", "serie", "repeticiones", "peso_kg", "rpe", "duracion_min"])
    rows = db.execute(
        select(Workout.date, Workout.name, Exercise.name, WorkoutSet.position, WorkoutSet.reps, WorkoutSet.weight)
        .add_columns(WorkoutSet.rpe, Workout.duration_min)
        .join(Workout, Workout.id == WorkoutSet.workout_id)
        .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
        .order_by(Workout.date, Workout.started_at, WorkoutSet.position, WorkoutSet.id)
    )
    for day, workout, exercise, position, reps, weight, rpe, minutes in rows:
        writer.writerow(
            [day, workout, exercise, position + 1, reps, _es(weight), "" if rpe is None else _es(rpe), minutes or ""]
        )
    return _download("\ufeff" + out.getvalue(), f"kcalia-entrenos-{_stamp()}.csv", "text/csv; charset=utf-8")


def _confirm(user: User, body: PasswordConfirm) -> None:
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(403, "La contraseña no es correcta.")


@router.post("/data/delete")
def delete_data(body: PasswordConfirm, user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    """Borra todos los datos pero conserva la cuenta."""
    _confirm(user, body)
    services.wipe_data(db)
    return {"ok": True}


@router.post("/account/delete")
def delete_account(
    body: PasswordConfirm, response: Response, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict:
    """Borra los datos y la cuenta de quien lo pide (y nada de nadie más)."""
    _confirm(user, body)
    if user.is_admin:
        raise HTTPException(
            409,
            "Eres el administrador: antes de borrar tu cuenta, pasa el rol a otra con scripts/make-admin.py.",
        )
    services.delete_user(db, user)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
