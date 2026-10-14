"""Gasto real: cuánto gasta de verdad la persona, a partir de lo que apunta y de cómo cambia su peso.

La fórmula (Mifflin-St Jeor × actividad) puede desviarse un 10-20 %. Con varias semanas de datos el balance lo dice
mejor: si se comen de media 2.200 kcal y el peso baja 0,27 kg a la semana, el gasto es 2.200 + 0,27 × 7.700 / 7.
Además absorbe lo que se olvide apuntar de forma habitual, porque se mide en las mismas «unidades» que el registro.

Sin IA. Ventana de 28 días hasta ayer (hoy aún no está completo). Solo cuentan los días con al menos la mitad del
objetivo apuntado (los demás casi seguro están a medias) y hace falta un mínimo de días y de pesajes.
"""

from datetime import date, timedelta

KCAL_PER_KG = 7700  # energía de un kilo de peso corporal perdido o ganado (mayoritariamente grasa)
WINDOW_DAYS = 28
MIN_DAYS = 10
MIN_WEIGHINS = 4
MIN_SPAN_DAYS = 10
FULL_DAYS = 21  # con 3 semanas de días y de pesajes la medida ya no se mezcla con la fórmula
COMPLETE_SHARE = 0.5
PLAUSIBLE = (0.6, 1.5)  # fuera de este rango frente a la fórmula, algo falla en los datos
UPDATE_STEP = 100  # diferencia a partir de la cual se propone actualizar el gasto aplicado


def _slope_per_day(points: list[tuple[int, float]]) -> float:
    """Pendiente por mínimos cuadrados (kg/día): la tendencia, sin dejarse llevar por un pesaje suelto."""
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in points)
    den = sum((x - mean_x) ** 2 for x, _ in points)
    return num / den if den else 0.0


def estimate(
    *,
    intake: dict[str, float],
    targets_by_day: dict[str, float],
    weights: dict[str, float],
    formula_tdee: float,
    today: date,
) -> dict:
    end = today - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    in_window = lambda iso: start.isoformat() <= iso <= end.isoformat()  # noqa: E731
    valid = [
        kcal
        for iso, kcal in intake.items()
        if in_window(iso) and kcal > 0 and kcal >= COMPLETE_SHARE * targets_by_day.get(iso, formula_tdee)
    ]
    points = sorted((date.fromisoformat(iso).toordinal(), kg) for iso, kg in weights.items() if in_window(iso))
    span = points[-1][0] - points[0][0] if points else 0
    result = {
        "status": "insuficiente",
        "reason": None,
        "observed": None,
        "estimate": None,
        "formula": round(formula_tdee),
        "days": len(valid),
        "weighins": len(points),
        "span_days": span,
        "slope_kg_week": None,
        "weight_factor": 0.0,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }
    if len(valid) < MIN_DAYS:
        result["reason"] = (
            f"Hacen falta al menos {MIN_DAYS} días completos apuntados en las últimas 4 semanas (llevas {len(valid)})."
        )
        return result
    if len(points) < MIN_WEIGHINS or span < MIN_SPAN_DAYS:
        result["reason"] = (
            f"Hacen falta al menos {MIN_WEIGHINS} pesajes repartidos en {MIN_SPAN_DAYS} días o más "
            f"(llevas {len(points)} en {span} días)."
        )
        return result

    slope = _slope_per_day(points)
    observed = sum(valid) / len(valid) - slope * KCAL_PER_KG
    factor = min(1.0, len(valid) / FULL_DAYS) * min(1.0, span / FULL_DAYS)
    result.update(observed=round(observed), slope_kg_week=round(slope * 7, 2), weight_factor=round(factor, 2))
    low, high = PLAUSIBLE
    if not low * formula_tdee <= observed <= high * formula_tdee:
        result["status"] = "dudoso"
        result["reason"] = (
            "El resultado se aleja demasiado de lo esperable. Suele pasar si no se ha apuntado todo lo que se come "
            "o si un pesaje recoge mucha retención de agua. Sigue apuntando y pesándote y se corregirá solo."
        )
        return result
    result["status"] = "ok"
    result["estimate"] = round(factor * observed + (1 - factor) * formula_tdee)
    return result
