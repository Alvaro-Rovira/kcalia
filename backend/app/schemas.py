from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Sex = Literal["hombre", "mujer"]
Activity = Literal["sedentario", "ligero", "moderado", "alto", "muy_alto"]
Goal = Literal["definicion_ligera", "definicion_agresiva", "volumen", "mantenimiento", "recomposicion"]
Slot = Literal["desayuno", "comida", "merienda", "cena", "snack"]
Source = Literal["ai", "exact", "fuzzy", "cache", "favorite", "recent", "manual", "photo", "product", "drink"]
Via = Literal["text", "voice", "photo", "tap"]


def _iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class RegisterIn(BaseModel):
    # Las reglas (longitud, caracteres, contraseñas débiles) las aplica security.py con mensajes claros.
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    # Campo trampa: invisible para las personas; si llega relleno, es un robot.
    website: str = Field(default="", max_length=200)


class PasswordConfirm(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class ProfileIn(BaseModel):
    sex: Sex
    age: int = Field(ge=14, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    activity: Activity
    goal: Goal
    target_weight_kg: float | None = Field(default=None, ge=30, le=300)


class ProfileSave(ProfileIn):
    recalculate: bool = True
    # Fecha local del cliente, para anotar el peso inicial en su día.
    today: str | None = None

    _check_today = field_validator("today")(lambda cls, v: _iso_date(v) if v else v)


class PrefsIn(BaseModel):
    weight_unit: Literal["kg", "lb"]


class TargetsIn(BaseModel):
    kcal: int = Field(ge=800, le=8000)
    protein: int = Field(ge=20, le=500)
    carbs: int = Field(ge=0, le=1200)
    fat: int = Field(ge=10, le=400)


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qty: float = Field(default=1, ge=0, le=10000)
    unit: str = Field(default="g", max_length=16)
    grams: float = Field(default=0, ge=0, le=5000)
    # Si el ingrediente sale de la etiqueta de un producto guardado.
    product_id: int | None = None
    # Añadido a mano por el usuario: al guardar la comida se aprende en la caché de ingredientes.
    manual: bool = False
    kcal: float = Field(ge=0, le=6000)
    protein: float = Field(ge=0, le=600)
    carbs: float = Field(ge=0, le=1200)
    fat: float = Field(ge=0, le=600)
    # Opcionales: las comidas antiguas no los tienen.
    fiber: float | None = Field(default=None, ge=0, le=300)
    alcohol: float | None = Field(default=None, ge=0, le=500)


class ResolveIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    skip_history: bool = False
    force_ai: bool = False


class MealIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=40)
    date: str
    slot: Slot
    name: str = Field(min_length=1, max_length=160)
    text: str = Field(default="", max_length=600)
    items: list[Item] = Field(min_length=1, max_length=30)
    servings: float = Field(default=1.0, gt=0, le=20)
    source: Source = "ai"
    via: Via = "text"
    confidence: float = Field(default=0.8, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    dish_id: int | None = None

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


class MealPatch(BaseModel):
    date: str | None = None
    slot: Slot | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    items: list[Item] | None = Field(default=None, min_length=1, max_length=30)
    servings: float | None = Field(default=None, gt=0, le=20)

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v) if v else v)


class DishPatch(BaseModel):
    favorite: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)


class WeightIn(BaseModel):
    date: str
    kg: float = Field(ge=30, le=300)

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    alias: str = Field(default="", max_length=60)
    basis: Literal["g", "ml"] = "g"
    kcal100: float = Field(ge=0, le=950)
    protein100: float = Field(ge=0, le=100)
    carbs100: float = Field(ge=0, le=100)
    fat100: float = Field(ge=0, le=100)
    fiber100: float | None = Field(default=None, ge=0, le=100)
    sugars100: float | None = Field(default=None, ge=0, le=100)
    salt100: float | None = Field(default=None, ge=0, le=100)
    unit_label: str = Field(default="", max_length=30)
    unit_grams: float | None = Field(default=None, gt=0, le=5000)
    barcode: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _plausible(self):
        if self.protein100 + self.carbs100 + self.fat100 > 105:
            raise ValueError("proteínas, hidratos y grasas por 100 g no pueden sumar más de 100 g")
        return self


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    alias: str | None = Field(default=None, max_length=60)
    basis: Literal["g", "ml"] | None = None
    kcal100: float | None = Field(default=None, ge=0, le=950)
    protein100: float | None = Field(default=None, ge=0, le=100)
    carbs100: float | None = Field(default=None, ge=0, le=100)
    fat100: float | None = Field(default=None, ge=0, le=100)
    fiber100: float | None = Field(default=None, ge=0, le=100)
    sugars100: float | None = Field(default=None, ge=0, le=100)
    salt100: float | None = Field(default=None, ge=0, le=100)
    unit_label: str | None = Field(default=None, max_length=30)
    unit_grams: float | None = Field(default=None, gt=0, le=5000)
    barcode: str | None = Field(default=None, max_length=20)


HHMM = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


class MealReminder(BaseModel):
    slot: Literal["desayuno", "comida", "merienda", "cena", "snack"]
    time: HHMM
    enabled: bool = True


def _default_meal_reminders() -> list[MealReminder]:
    return [
        MealReminder(slot="desayuno", time="10:30"),
        MealReminder(slot="comida", time="16:00"),
        MealReminder(slot="cena", time="22:15"),
    ]


class DayTargetsIn(BaseModel):
    kcal: int = Field(ge=800, le=8000)
    protein: int = Field(ge=20, le=500)
    carbs: int = Field(ge=0, le=1200)
    fat: int = Field(ge=10, le=400)


Weekday = Annotated[int, Field(ge=0, le=6)]


class Prefs(BaseModel):
    """Preferencias guardadas por usuario. Cada campo tiene un valor por defecto: lo nuevo no rompe lo viejo."""

    model_config = {"extra": "ignore"}

    # Objetivo de agua; None = automático (35 ml por kg de peso).
    water_goal_ml: int | None = Field(default=None, ge=500, le=8000)
    # Objetivos distintos en días de entreno y de descanso (desactivado: todos los días, el objetivo de siempre).
    day_types: bool = False
    training_days: list[Weekday] = Field(default_factory=lambda: [0, 2, 4], max_length=7)  # 0 = lunes
    training_kcal_adjust: int = Field(default=200, ge=-800, le=800)
    rest_kcal_adjust: int = Field(default=-100, ge=-800, le=800)
    # Objetivos fijados a mano para cada tipo de día (None = calculados con el ajuste).
    training_targets: DayTargetsIn | None = None
    rest_targets: DayTargetsIn | None = None
    # Sumar al objetivo del día las calorías estimadas del entrenamiento (si no, solo es informativo).
    add_exercise_kcal: bool = False
    # Temporizador de descanso entre series, en segundos.
    rest_seconds: int = Field(default=90, ge=15, le=600)
    # Recordatorios por notificación: apagados hasta que el usuario los activa desde Ajustes.
    reminders: bool = False
    meal_reminders: list[MealReminder] = Field(default_factory=_default_meal_reminders, max_length=5)
    weigh_reminder: HHMM | None = "08:30"
    weigh_days: list[Weekday] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], max_length=7)


class PrefsPatch(BaseModel):
    model_config = {"extra": "forbid"}

    water_goal_ml: int | None = Field(default=None, ge=500, le=8000)
    day_types: bool | None = None
    training_days: list[Weekday] | None = Field(default=None, max_length=7)
    training_kcal_adjust: int | None = Field(default=None, ge=-800, le=800)
    rest_kcal_adjust: int | None = Field(default=None, ge=-800, le=800)
    training_targets: DayTargetsIn | None = None
    rest_targets: DayTargetsIn | None = None
    add_exercise_kcal: bool | None = None
    rest_seconds: int | None = Field(default=None, ge=15, le=600)
    reminders: bool | None = None
    meal_reminders: list[MealReminder] | None = Field(default=None, max_length=5)
    weigh_reminder: HHMM | None = None
    weigh_days: list[Weekday] | None = Field(default=None, max_length=7)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=800, pattern=r"^https://")
    keys: dict[str, str]

    @model_validator(mode="after")
    def _keys(self):
        if not self.keys.get("p256dh") or not self.keys.get("auth"):
            raise ValueError("faltan las claves p256dh y auth")
        return self


class EndpointIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=800)


class DayTypeIn(BaseModel):
    date: str
    # None vuelve al día de la semana por defecto.
    kind: Literal["entreno", "descanso"] | None = None

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


class WaterIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=40)
    date: str
    ml: int = Field(ge=10, le=3000)

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


class MeasurementIn(BaseModel):
    date: str
    waist: float | None = Field(default=None, ge=30, le=250)
    chest: float | None = Field(default=None, ge=40, le=250)
    arm: float | None = Field(default=None, ge=10, le=100)
    hip: float | None = Field(default=None, ge=40, le=250)
    thigh: float | None = Field(default=None, ge=20, le=150)

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


Muscle = Literal["pecho", "espalda", "hombros", "biceps", "triceps", "piernas", "gluteos", "core", "cardio", "otro"]
Intensity = Literal["suave", "moderada", "intensa"]


class ExerciseIn(BaseModel):
    client_id: str = Field(min_length=4, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    muscle: Muscle = "otro"
    unit: Literal["reps", "seg", "min"] = "reps"


class ExercisePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    muscle: Muscle | None = None
    archived: bool | None = None


class TemplateExercise(BaseModel):
    exercise: str = Field(min_length=4, max_length=40)
    sets: int = Field(default=3, ge=1, le=20)
    reps: int = Field(default=10, ge=1, le=600)


class TemplateIn(BaseModel):
    client_id: str = Field(min_length=4, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    exercises: list[TemplateExercise] = Field(default_factory=list, max_length=30)


class WorkoutIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=40)
    date: str
    name: str = Field(default="Entreno", min_length=1, max_length=60)
    template_cid: str | None = Field(default=None, max_length=40)
    started_at: datetime | None = None

    _check_date = field_validator("date")(lambda cls, v: _iso_date(v))


class WorkoutPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    notes: str | None = Field(default=None, max_length=1000)
    ended_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=1, le=600)
    intensity: Intensity | None = None


class SetIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=40)
    exercise: str = Field(min_length=4, max_length=40)
    reps: int = Field(ge=0, le=600)
    weight: float = Field(default=0, ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=1, le=10)
    position: int = Field(default=0, ge=0, le=1000)


class SetPatch(BaseModel):
    reps: int | None = Field(default=None, ge=0, le=600)
    weight: float | None = Field(default=None, ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=1, le=10)
