"""Objetivos según el tipo de día (entreno o descanso), sin IA.

Parten de los objetivos de siempre (la fórmula del plan o los fijados a mano) y suman un ajuste de calorías que
absorben los hidratos: la proteína y la grasa no cambian. Cada tipo de día puede fijarse a mano.

Por defecto los días de descanso compensan los de entreno, de modo que la media de la semana es el objetivo de siempre:
el nivel de actividad del plan ya cuenta el gimnasio, así que sumar en los días de entreno sin restar en los demás lo
contaría dos veces (con 4 días de +200 y 3 de -100, la semana quedaba 70 kcal al día por encima del plan).

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


def _training_days(prefs: Prefs) -> int:
    return len(set(prefs.training_days))


def training_adjust(prefs: Prefs) -> int:
    """Calorías que se suman los días de entreno. Si se entrena a diario no hay días con los que compensar: ninguna."""
    if prefs.balance_rest and _training_days(prefs) == 7:
        return 0
    return prefs.training_kcal_adjust


def rest_adjust(base_kcal: float, prefs: Prefs) -> int:
    """Calorías que se suman (negativas: se restan) los días de descanso.

    Compensando, lo que suben los días de entreno (el ajuste o, si están fijados a mano, su diferencia con el objetivo
    de siempre) se reparte entre los de descanso, redondeado a 10 kcal."""
    if not prefs.balance_rest:
        return prefs.rest_kcal_adjust
    training = _training_days(prefs)
    if training in (0, 7):
        return 0
    extra = prefs.training_targets.kcal - _round(base_kcal) if prefs.training_targets else prefs.training_kcal_adjust
    return _round(-extra * training / (7 - training) / 10) * 10


def _shift(values: dict, kcal_delta: float) -> dict:
    """Mueve las calorías a través de los hidratos (4 kcal/g), sin bajar de 0 g."""
    carbs = max(0, _round(values["carbs"] + kcal_delta / 4))
    return {**values, "carbs": carbs, "kcal": _round(values["kcal"] + (carbs - values["carbs"]) * 4)}


def targets_for(base: dict, prefs: Prefs, kind: str | None, exercise_kcal: float = 0, measured: bool = False) -> dict:
    """Objetivos del día (kcal, protein, carbs, fat) a partir de los de siempre.

    `measured`: el mantenimiento es el gasto real medido, que ya incluye los entrenos; no se suman otra vez."""
    out = {key: _round(base[key]) for key in MACRO_KEYS}
    if kind == "entreno":
        manual = prefs.training_targets
        out = manual.model_dump() if manual else _shift(out, training_adjust(prefs))
    elif kind == "descanso":
        manual = prefs.rest_targets
        out = manual.model_dump() if manual else _shift(out, rest_adjust(base["kcal"], prefs))
    if prefs.add_exercise_kcal and exercise_kcal > 0 and not measured:
        out = _shift(out, exercise_kcal)
    return out
