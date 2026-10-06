"""Resolución de comidas sin IA: historial exacto, historial aproximado y caché de ingredientes."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .textnorm import (
    DEFAULT_UNIT,
    MASS_UNITS,
    UNITS,
    VOLUME_UNITS,
    food_key,
    numbers_in,
    parse_part,
    split_parts,
)

SIMILARITY_THRESHOLD = 0.85
TOKEN_THRESHOLD = 0.75
CONNECTORS = frozenset({"con", "y", "e", "a", "al", "en"})
MACROS = ("kcal", "protein", "carbs", "fat")
# Datos secundarios: pueden faltar (comidas antiguas, respuestas sin ellos) y entonces cuentan como 0.
EXTRAS = ("fiber", "alcohol")


def similarity(a: str, b: str) -> float:
    """0..1. Tolera erratas y cambios de orden ("tostada con tomate" / "tomate con tostada")."""
    if not a or not b:
        return 0.0
    return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100


def tokens_aligned(a: str, b: str) -> bool:
    """Cada palabra de un texto tiene su pareja (salvo erratas) en el otro.

    Evita que "pechuga de pollo con arroz" y "pechuga de pavo con arroz" pasen por la
    misma comida solo porque casi todas las letras coinciden.
    """
    left = [t for t in a.split() if t not in CONNECTORS]
    right = [t for t in b.split() if t not in CONNECTORS]

    def covered(tokens: list[str], others: list[str]) -> bool:
        return all(any(fuzz.ratio(t, o) >= TOKEN_THRESHOLD * 100 for o in others) for t in tokens)

    return bool(left) and bool(right) and covered(left, right) and covered(right, left)


def find_similar(
    norm: str,
    candidates: Iterable[tuple[int, str]],
    threshold: float = SIMILARITY_THRESHOLD,
    limit: int = 3,
) -> list[tuple[int, float]]:
    """Candidatos parecidos, de mayor a menor similitud.

    Las cantidades deben coincidir: "2 huevos" y "3 huevos" se parecen mucho como texto
    pero no son la misma comida, y de eso se encarga la caché de ingredientes.
    """
    wanted = numbers_in(norm)
    scored = []
    for dish_id, candidate in candidates:
        if candidate == norm:
            continue
        score = similarity(norm, candidate)
        if score >= threshold and numbers_in(candidate) == wanted and tokens_aligned(norm, candidate):
            scored.append((dish_id, round(score, 3)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


@dataclass
class FoodInfo:
    name: str
    kcal100: float
    protein100: float
    carbs100: float
    fat100: float
    unit_grams: dict[str, float] = field(default_factory=dict)
    fiber100: float | None = None
    alcohol100: float | None = None


def canonical_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    return UNITS.get(food_key(unit), None)


def _grams_for(qty: float, unit: str | None, food: FoodInfo) -> float | None:
    if unit in MASS_UNITS:
        return qty * MASS_UNITS[unit]
    if unit in VOLUME_UNITS:
        density = food.unit_grams.get("ml")
        return qty * VOLUME_UNITS[unit] * density if density else None
    per_unit = food.unit_grams.get(unit or DEFAULT_UNIT)
    return qty * per_unit if per_unit else None


def resolve_from_foods(text: str, lookup: Callable[[str], FoodInfo | None]) -> list[dict] | None:
    """Compone la comida con ingredientes ya conocidos. Todo o nada: si falta uno, None."""
    parts = split_parts(text)
    if not parts:
        return None
    items = []
    for part in parts:
        qty, unit, key = parse_part(part)
        if not key or qty <= 0:
            return None
        food = lookup(key)
        if food is None:
            return None
        grams = _grams_for(qty, unit, food)
        if not grams or grams <= 0 or grams > 5000:
            return None
        factor = grams / 100
        item = {
            "name": food.name,
            "qty": qty,
            "unit": unit or DEFAULT_UNIT,
            "grams": round(grams, 1),
            "kcal": round(food.kcal100 * factor, 1),
            "protein": round(food.protein100 * factor, 1),
            "carbs": round(food.carbs100 * factor, 1),
            "fat": round(food.fat100 * factor, 1),
        }
        if food.fiber100 is not None:
            item["fiber"] = round(food.fiber100 * factor, 1)
        if food.alcohol100:
            item["alcohol"] = round(food.alcohol100 * factor, 1)
        items.append(item)
    return items


@dataclass
class FoodUpdate:
    key: str
    name: str
    kcal100: float
    protein100: float
    carbs100: float
    fat100: float
    unit_grams: dict[str, float]
    fiber100: float | None = None
    alcohol100: float | None = None


def _per100(item: dict) -> dict[str, float]:
    grams = item["grams"]
    values = {f"{m}100": round(item[m] / grams * 100, 2) for m in MACROS}
    for extra in EXTRAS:
        if item.get(extra) is not None:
            values[f"{extra}100"] = round(item[extra] / grams * 100, 2)
    return values


def _unit_grams(qty: float, unit: str | None, grams: float) -> dict[str, float]:
    if qty <= 0 or unit in MASS_UNITS:
        return {}
    if unit in VOLUME_UNITS:
        return {"ml": round(grams / (qty * VOLUME_UNITS[unit]), 3)}
    return {unit or DEFAULT_UNIT: round(grams / qty, 1)}


def _related(a: str, b: str) -> bool:
    return bool(set(a.split()) & set(b.split())) or fuzz.partial_ratio(a, b) >= 70


def learn_foods(text: str, items: list[dict]) -> list[FoodUpdate]:
    """Qué guardar en la caché de ingredientes a partir de una respuesta de la IA.

    Si el texto tiene tantos trozos como ingredientes devolvió la IA y se corresponden
    uno a uno, se guarda además la forma en que el usuario lo escribió ("tostada pan
    integral") y cuántos gramos supone su unidad, para resolverlo solo la próxima vez.
    """
    usable = [i for i in items if i.get("grams", 0) > 0]
    updates: dict[str, FoodUpdate] = {}

    def add(key: str, name: str, item: dict, units: dict[str, float]) -> None:
        if not key:
            return
        if key in updates:
            updates[key].unit_grams.update(units)
            return
        updates[key] = FoodUpdate(key=key, name=name, unit_grams=dict(units), **_per100(item))

    for item in usable:
        unit = canonical_unit(item.get("unit"))
        qty = float(item.get("qty") or 0)
        units = _unit_grams(qty, unit, item["grams"]) if (unit and qty > 0) else {}
        add(food_key(item["name"]), item["name"], item, units)

    parts = split_parts(text)
    if len(parts) == len(usable) == len(items):
        parsed = [parse_part(p) for p in parts]
        if all(key and _related(key, food_key(i["name"])) for (_, _, key), i in zip(parsed, usable, strict=True)):
            for (qty, unit, key), item in zip(parsed, usable, strict=True):
                add(key, item["name"], item, _unit_grams(qty, unit, item["grams"]))

    return list(updates.values())


def totals(items: list[dict], servings: float = 1.0) -> dict[str, float]:
    return {m: round(sum(float(i.get(m, 0)) for i in items) * servings, 1) for m in MACROS}


def extras(items: list[dict], servings: float = 1.0) -> dict[str, float]:
    """Fibra y alcohol de la comida; lo que no traiga el dato cuenta como 0."""
    return {e: round(sum(float(i.get(e) or 0) for i in items) * servings, 1) for e in EXTRAS}
