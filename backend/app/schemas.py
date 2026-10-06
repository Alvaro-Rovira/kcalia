from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Sex = Literal["hombre", "mujer"]
Activity = Literal["sedentario", "ligero", "moderado", "alto", "muy_alto"]
Goal = Literal["definicion_ligera", "definicion_agresiva", "volumen", "mantenimiento", "recomposicion"]
Slot = Literal["desayuno", "comida", "merienda", "cena", "snack"]
Source = Literal["ai", "exact", "fuzzy", "cache", "favorite", "recent", "manual", "photo", "product"]
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
    kcal: float = Field(ge=0, le=6000)
    protein: float = Field(ge=0, le=600)
    carbs: float = Field(ge=0, le=1200)
    fat: float = Field(ge=0, le=600)


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
