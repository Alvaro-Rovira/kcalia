"""Objetivos según el tipo de día (entreno o descanso), sin IA.

Parten de los objetivos de siempre (la fórmula del plan o los fijados a mano) y suman un ajuste de calorías que
absorben los hidratos: la proteína y la grasa no cambian. Cada tipo de día puede fijarse a mano.

El móvil tiene un espejo de este módulo (frontend/src/lib/dayTargets.ts) y los dos se prueban con el mismo fichero de
casos (backend/tests/fixtures/day_target_cases.json): si cambias uno, cambia el otro.
"""

import math
from datetime import date

from .schemas import Prefs

KINDS = ("entreno", "descanso")
MACRO_KEYS = ("kcal", "protein", "carbs", "fat")


def kind_for(day: date, prefs: Prefs, overrides: dict[str, str]) -> str | None:
    """entreno, descanso o None si los tipos de día están desactivados."""
    if not prefs.day_types:
        return None
    override = overrides.get(day.isoformat())
    if override in KINDS:
        return override
    return "entreno" if day.weekday() in prefs.training_days else "descanso"


def _round(value: float) -> int:
    """Mitades hacia arriba, igual que Math.round en el móvil (round de Python redondea al par)."""
    return math.floor(value + 0.5)


def _shift(values: dict, kcal_delta: float) -> dict:
    """Mueve las calorías a través de los hidratos (4 kcal/g), sin bajar de 0 g."""
    carbs = max(0, _round(values["carbs"] + kcal_delta / 4))
    return {**values, "carbs": carbs, "kcal": _round(values["kcal"] + (carbs - values["carbs"]) * 4)}


def targets_for(base: dict, prefs: Prefs, kind: str | None, exercise_kcal: float = 0) -> dict:
    """Objetivos del día (kcal, protein, carbs, fat) a partir de los de siempre."""
    out = {key: _round(base[key]) for key in MACRO_KEYS}
    if kind == "entreno":
        manual = prefs.training_targets
        out = manual.model_dump() if manual else _shift(out, prefs.training_kcal_adjust)
    elif kind == "descanso":
        manual = prefs.rest_targets
        out = manual.model_dump() if manual else _shift(out, prefs.rest_kcal_adjust)
    if prefs.add_exercise_kcal and exercise_kcal > 0:
        out = _shift(out, exercise_kcal)
    return out
