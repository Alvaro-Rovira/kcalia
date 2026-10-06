"""Entrenamientos: catálogo inicial, plantillas, 1RM estimado, volumen y calorías estimadas. Todo en código, sin IA."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Exercise, Profile, Workout, WorkoutSet, WorkoutTemplate

# (client_id fijo, nombre, grupo muscular, unidad). Los client_id fijos permiten usar el catálogo sin conexión.
CATALOG: list[tuple[str, str, str, str]] = [
    ("ex-press-banca", "Press de banca", "pecho", "reps"),
    ("ex-press-inclinado-mancuernas", "Press inclinado con mancuernas", "pecho", "reps"),
    ("ex-aperturas", "Aperturas con mancuernas", "pecho", "reps"),
    ("ex-cruce-poleas", "Cruce de poleas", "pecho", "reps"),
    ("ex-fondos", "Fondos en paralelas", "pecho", "reps"),
    ("ex-flexiones", "Flexiones", "pecho", "reps"),
    ("ex-dominadas", "Dominadas", "espalda", "reps"),
    ("ex-jalon", "Jalón al pecho", "espalda", "reps"),
    ("ex-remo-barra", "Remo con barra", "espalda", "reps"),
    ("ex-remo-mancuerna", "Remo con mancuerna", "espalda", "reps"),
    ("ex-remo-polea", "Remo en polea baja", "espalda", "reps"),
    ("ex-peso-muerto", "Peso muerto", "espalda", "reps"),
    ("ex-press-militar", "Press militar", "hombros", "reps"),
    ("ex-press-hombro-mancuernas", "Press de hombros con mancuernas", "hombros", "reps"),
    ("ex-elevaciones-laterales", "Elevaciones laterales", "hombros", "reps"),
    ("ex-pajaros", "Pájaros (deltoides posterior)", "hombros", "reps"),
    ("ex-face-pull", "Face pull", "hombros", "reps"),
    ("ex-curl-barra", "Curl con barra", "biceps", "reps"),
    ("ex-curl-mancuernas", "Curl con mancuernas", "biceps", "reps"),
    ("ex-curl-martillo", "Curl martillo", "biceps", "reps"),
    ("ex-press-frances", "Press francés", "triceps", "reps"),
    ("ex-triceps-polea", "Extensión de tríceps en polea", "triceps", "reps"),
    ("ex-fondos-banco", "Fondos en banco", "triceps", "reps"),
    ("ex-sentadilla", "Sentadilla", "piernas", "reps"),
    ("ex-prensa", "Prensa de piernas", "piernas", "reps"),
    ("ex-zancadas", "Zancadas", "piernas", "reps"),
    ("ex-extension-cuadriceps", "Extensión de cuádriceps", "piernas", "reps"),
    ("ex-curl-femoral", "Curl femoral", "piernas", "reps"),
    ("ex-peso-muerto-rumano", "Peso muerto rumano", "piernas", "reps"),
    ("ex-gemelos", "Gemelos de pie", "piernas", "reps"),
    ("ex-hip-thrust", "Hip thrust", "gluteos", "reps"),
    ("ex-patada-gluteo", "Patada de glúteo en polea", "gluteos", "reps"),
    ("ex-plancha", "Plancha", "core", "seg"),
    ("ex-crunch", "Crunch abdominal", "core", "reps"),
    ("ex-elevacion-piernas", "Elevación de piernas colgado", "core", "reps"),
    ("ex-rueda", "Rueda abdominal", "core", "reps"),
    ("ex-cinta", "Cinta (correr)", "cardio", "min"),
    ("ex-bici", "Bicicleta estática", "cardio", "min"),
    ("ex-remo-ergometro", "Remo (ergómetro)", "cardio", "min"),
    ("ex-eliptica", "Elíptica", "cardio", "min"),
]

TEMPLATES: list[tuple[str, str, list[tuple[str, int, int]]]] = [
    (
        "tpl-empuje",
        "Empuje",
        [
            ("ex-press-banca", 4, 8),
            ("ex-press-inclinado-mancuernas", 3, 10),
            ("ex-press-militar", 3, 8),
            ("ex-elevaciones-laterales", 3, 12),
            ("ex-triceps-polea", 3, 12),
        ],
    ),
    (
        "tpl-tiron",
        "Tirón",
        [
            ("ex-dominadas", 4, 6),
            ("ex-remo-barra", 4, 8),
            ("ex-jalon", 3, 10),
            ("ex-face-pull", 3, 15),
            ("ex-curl-barra", 3, 10),
        ],
    ),
    (
        "tpl-pierna",
        "Pierna",
        [
            ("ex-sentadilla", 4, 6),
            ("ex-peso-muerto-rumano", 3, 8),
            ("ex-prensa", 3, 10),
            ("ex-curl-femoral", 3, 12),
            ("ex-gemelos", 4, 12),
        ],
    ),
    (
        "tpl-completo",
        "Cuerpo completo",
        [
            ("ex-sentadilla", 3, 8),
            ("ex-press-banca", 3, 8),
            ("ex-remo-barra", 3, 8),
            ("ex-press-militar", 2, 10),
            ("ex-plancha", 3, 45),
        ],
    ),
]

# MET (equivalente metabólico) del entrenamiento de fuerza según la intensidad (Compendium of Physical Activities).
MET = {"suave": 3.5, "moderada": 5.0, "intensa": 6.0}


def ensure_catalog(db: Session) -> None:
    """La primera vez, cada usuario recibe el catálogo básico y las plantillas Empuje/Tirón/Pierna/Completo."""
    if db.scalar(select(func.count(Exercise.id))):
        return
    for client_id, name, muscle, unit in CATALOG:
        db.add(Exercise(client_id=client_id, name=name, muscle=muscle, unit=unit))
    for position, (client_id, name, items) in enumerate(TEMPLATES):
        exercises = [{"exercise": ex, "sets": sets, "reps": reps} for ex, sets, reps in items]
        db.add(WorkoutTemplate(client_id=client_id, name=name, exercises=exercises, position=position))
    db.commit()


def estimated_1rm(weight: float, reps: int) -> float:
    """Fórmula de Epley; con una sola repetición, el propio peso. Más allá de 12 repeticiones es poco fiable."""
    if weight <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return round(weight, 1)
    return round(weight * (1 + min(reps, 12) / 30), 1)


def estimated_kcal(duration_min: int | None, intensity: str, weight_kg: float) -> int:
    """Calorías estimadas: MET × peso × horas. Es una orientación, no una medida."""
    if not duration_min:
        return 0
    return round(MET.get(intensity, MET["moderada"]) * weight_kg * duration_min / 60)


def _weight_kg(db: Session) -> float:
    profile = db.scalar(select(Profile))
    return profile.weight_kg if profile else 70.0


def estimated_kcal_by_day(db: Session, start: str, end: str) -> dict[str, float]:
    """Calorías estimadas de los entrenos terminados de cada día."""
    weight = _weight_kg(db)
    out: dict[str, float] = {}
    rows = db.execute(
        select(Workout.date, Workout.duration_min, Workout.intensity).where(
            Workout.date >= start, Workout.date <= end, Workout.duration_min.is_not(None)
        )
    )
    for day, minutes, intensity in rows:
        out[day] = out.get(day, 0) + estimated_kcal(minutes, intensity, weight)
    return out


def exercise_dict(exercise: Exercise) -> dict:
    return {
        "id": exercise.id,
        "client_id": exercise.client_id,
        "name": exercise.name,
        "muscle": exercise.muscle,
        "unit": exercise.unit,
        "custom": exercise.custom,
        "archived": exercise.archived,
    }


def template_dict(template: WorkoutTemplate) -> dict:
    return {
        "client_id": template.client_id,
        "name": template.name,
        "exercises": template.exercises,
        "position": template.position,
    }


def set_dict(row: WorkoutSet, exercise_cid: str) -> dict:
    return {
        "client_id": row.client_id,
        "exercise": exercise_cid,
        "position": row.position,
        "reps": row.reps,
        "weight": row.weight,
        "rpe": row.rpe,
        "created_at": row.created_at.isoformat() + "Z",
    }


def workout_dict(workout: Workout, sets: list[dict], weight_kg: float) -> dict:
    volume = sum(s["weight"] * s["reps"] for s in sets)
    return {
        "client_id": workout.client_id,
        "date": workout.date,
        "name": workout.name,
        "notes": workout.notes,
        "template_cid": workout.template_cid,
        "started_at": workout.started_at.isoformat() + "Z",
        "ended_at": workout.ended_at.isoformat() + "Z" if workout.ended_at else None,
        "duration_min": workout.duration_min,
        "intensity": workout.intensity,
        "kcal": estimated_kcal(workout.duration_min, workout.intensity, weight_kg),
        "volume": round(volume, 1),
        "sets": sets,
    }


def workouts_payload(db: Session, workouts: list[Workout]) -> list[dict]:
    """Entrenos con sus series, en dos consultas (sin una por entreno)."""
    if not workouts:
        return []
    cids = dict(db.execute(select(Exercise.id, Exercise.client_id)).all())
    by_workout: dict[int, list[dict]] = {}
    rows = db.scalars(
        select(WorkoutSet)
        .where(WorkoutSet.workout_id.in_([w.id for w in workouts]))
        .order_by(WorkoutSet.position, WorkoutSet.id)
    )
    for row in rows:
        by_workout.setdefault(row.workout_id, []).append(set_dict(row, cids.get(row.exercise_id, "")))
    weight = _weight_kg(db)
    return [workout_dict(w, by_workout.get(w.id, []), weight) for w in workouts]


def last_performance(db: Session) -> dict[str, dict]:
    """Por ejercicio, la última sesión en que se hizo: fecha y su mejor serie (para tener una referencia)."""
    rows = db.execute(
        select(Exercise.client_id, Workout.date, WorkoutSet.weight, WorkoutSet.reps)
        .join(Exercise, Exercise.id == WorkoutSet.exercise_id)
        .join(Workout, Workout.id == WorkoutSet.workout_id)
        .order_by(Workout.date, WorkoutSet.id)
    )
    last: dict[str, dict] = {}
    for cid, day, weight, reps in rows:
        current = last.get(cid)
        if current is None or day > current["date"]:
            last[cid] = {"date": day, "weight": weight, "reps": reps, "sets": 1}
        elif day == current["date"]:
            current["sets"] += 1
            if (weight, reps) > (current["weight"], current["reps"]):
                current["weight"], current["reps"] = weight, reps
    return last


def exercise_history(db: Session, exercise: Exercise, days: int = 365) -> list[dict]:
    """Por sesión: mejor 1RM estimado, volumen y mejor serie (para la gráfica de progresión)."""
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        select(Workout.date, WorkoutSet.weight, WorkoutSet.reps)
        .join(Workout, Workout.id == WorkoutSet.workout_id)
        .where(WorkoutSet.exercise_id == exercise.id, Workout.date >= since)
        .order_by(Workout.date)
    )
    sessions: dict[str, dict] = {}
    for day, weight, reps in rows:
        entry = sessions.setdefault(
            day, {"date": day, "best_1rm": 0.0, "volume": 0.0, "top_weight": 0.0, "top_reps": 0}
        )
        entry["best_1rm"] = max(entry["best_1rm"], estimated_1rm(weight, reps))
        entry["volume"] = round(entry["volume"] + weight * reps, 1)
        if (weight, reps) > (entry["top_weight"], entry["top_reps"]):
            entry["top_weight"], entry["top_reps"] = weight, reps
    return list(sessions.values())
