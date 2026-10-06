"""Registro de entrenamientos: ejercicios, plantillas, sesiones y series. Todo idempotente por client_id."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import workouts as lib
from ..db import get_db
from ..deps import require_approved_user
from ..models import Exercise, Workout, WorkoutSet, WorkoutTemplate, utcnow
from ..schemas import ExerciseIn, ExercisePatch, SetIn, SetPatch, TemplateIn, WorkoutIn, WorkoutPatch

router = APIRouter(prefix="/api", tags=["entreno"], dependencies=[Depends(require_approved_user)])

RECENT = 40


def _exercise(db: Session, client_id: str) -> Exercise:
    exercise = db.scalar(select(Exercise).where(Exercise.client_id == client_id))
    if exercise is None:
        raise HTTPException(404, "No encuentro ese ejercicio.")
    return exercise


def _workout(db: Session, client_id: str) -> Workout:
    workout = db.scalar(select(Workout).where(Workout.client_id == client_id))
    if workout is None:
        raise HTTPException(404, "No encuentro ese entreno. Puede que ya se hubiera borrado.")
    return workout


def _one(db: Session, workout: Workout) -> dict:
    return lib.workouts_payload(db, [workout])[0]


@router.get("/training")
def training(db: Session = Depends(get_db)) -> dict:
    """Todo lo que la pantalla de entreno necesita, en una petición (y para tenerlo sin conexión)."""
    lib.ensure_catalog(db)
    exercises = db.scalars(select(Exercise).order_by(Exercise.muscle, Exercise.name)).all()
    templates = db.scalars(select(WorkoutTemplate).order_by(WorkoutTemplate.position, WorkoutTemplate.id)).all()
    recent = db.scalars(select(Workout).order_by(Workout.date.desc(), Workout.started_at.desc()).limit(RECENT)).all()
    return {
        "exercises": [lib.exercise_dict(e) for e in exercises],
        "templates": [lib.template_dict(t) for t in templates],
        "workouts": lib.workouts_payload(db, list(recent)),
        "last": lib.last_performance(db),
    }


# ---------------------------------------------------------------- ejercicios


@router.post("/exercises", status_code=201)
def create_exercise(body: ExerciseIn, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(Exercise).where(Exercise.client_id == body.client_id))
    if existing is None:
        existing = Exercise(
            client_id=body.client_id, name=body.name.strip(), muscle=body.muscle, unit=body.unit, custom=True
        )
        db.add(existing)
        db.commit()
    return lib.exercise_dict(existing)


@router.patch("/exercises/{client_id}")
def update_exercise(client_id: str, body: ExercisePatch, db: Session = Depends(get_db)) -> dict:
    exercise = _exercise(db, client_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(exercise, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    return lib.exercise_dict(exercise)


@router.get("/exercises/{client_id}/history")
def exercise_history(
    client_id: str, days: int = Query(default=365, ge=7, le=3650), db: Session = Depends(get_db)
) -> dict:
    exercise = _exercise(db, client_id)
    return {"exercise": lib.exercise_dict(exercise), "sessions": lib.exercise_history(db, exercise, days)}


# ---------------------------------------------------------------- plantillas


@router.put("/templates")
def save_template(body: TemplateIn, db: Session = Depends(get_db)) -> dict:
    """Crea o actualiza una plantilla (idempotente por client_id)."""
    known = set(db.scalars(select(Exercise.client_id)))
    unknown = [item.exercise for item in body.exercises if item.exercise not in known]
    if unknown:
        raise HTTPException(422, "La plantilla incluye un ejercicio que no existe.")
    template = db.scalar(select(WorkoutTemplate).where(WorkoutTemplate.client_id == body.client_id))
    if template is None:
        count = len(db.scalars(select(WorkoutTemplate.id)).all())
        template = WorkoutTemplate(client_id=body.client_id, position=count)
        db.add(template)
    template.name = body.name.strip()
    template.exercises = [item.model_dump() for item in body.exercises]
    db.commit()
    return lib.template_dict(template)


@router.delete("/templates/{client_id}")
def delete_template(client_id: str, db: Session = Depends(get_db)) -> dict:
    db.execute(delete(WorkoutTemplate).where(WorkoutTemplate.client_id == client_id))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- sesiones


@router.post("/workouts", status_code=201)
def create_workout(body: WorkoutIn, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(Workout).where(Workout.client_id == body.client_id))
    if existing is not None:
        return _one(db, existing)  # reintento de la cola offline
    started = body.started_at.replace(tzinfo=None) if body.started_at else utcnow()
    workout = Workout(
        client_id=body.client_id,
        date=body.date,
        name=body.name.strip(),
        template_cid=body.template_cid,
        started_at=started,
    )
    db.add(workout)
    db.commit()
    return _one(db, workout)


@router.patch("/workouts/{client_id}")
def update_workout(client_id: str, body: WorkoutPatch, db: Session = Depends(get_db)) -> dict:
    workout = _workout(db, client_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("ended_at"):
        changes["ended_at"] = changes["ended_at"].replace(tzinfo=None)
        if "duration_min" not in changes:
            minutes = round((changes["ended_at"] - workout.started_at).total_seconds() / 60)
            changes["duration_min"] = max(1, min(600, minutes))
    for key, value in changes.items():
        setattr(workout, key, value)
    db.commit()
    return _one(db, workout)


@router.delete("/workouts/{client_id}")
def delete_workout(client_id: str, db: Session = Depends(get_db)) -> dict:
    workout = db.scalar(select(Workout).where(Workout.client_id == client_id))
    if workout is not None:
        db.delete(workout)
        db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- series


@router.post("/workouts/{workout_cid}/sets", status_code=201)
def add_set(workout_cid: str, body: SetIn, db: Session = Depends(get_db)) -> dict:
    workout = _workout(db, workout_cid)
    existing = db.scalar(select(WorkoutSet).where(WorkoutSet.client_id == body.client_id))
    if existing is None:
        exercise = _exercise(db, body.exercise)
        db.add(
            WorkoutSet(
                client_id=body.client_id,
                workout_id=workout.id,
                exercise_id=exercise.id,
                position=body.position,
                reps=body.reps,
                weight=body.weight,
                rpe=body.rpe,
            )
        )
        db.commit()
    return _one(db, workout)


def _set(db: Session, client_id: str) -> WorkoutSet:
    row = db.scalar(select(WorkoutSet).where(WorkoutSet.client_id == client_id))
    if row is None:
        raise HTTPException(404, "No encuentro esa serie.")
    return row


@router.patch("/sets/{client_id}")
def update_set(client_id: str, body: SetPatch, db: Session = Depends(get_db)) -> dict:
    row = _set(db, client_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    return _one(db, db.get(Workout, row.workout_id))


@router.delete("/sets/{client_id}")
def delete_set(client_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(WorkoutSet).where(WorkoutSet.client_id == client_id))
    if row is None:
        return {"ok": True}
    workout = db.get(Workout, row.workout_id)
    db.delete(row)
    db.commit()
    return _one(db, workout)
