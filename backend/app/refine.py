"""Una sola canalización para los ingredientes de cualquier comida (texto, voz, foto, plan, sugerencias y sin IA).

La IA solo aporta lo que únicamente ella sabe: qué alimento es, su preparación y cuánto hay cuando nadie lo dice. El
resto lo pone el código, siempre igual:

1. Emparejar cada ingrediente con la tabla oficial (`foodtable`).
2. Gramos: con una unidad conocida (pieza, loncha, cucharada, vaso, ml…) los calcula la tabla; en fotos manda la
   estimación visual.
3. Valores: los de la tabla si hay coincidencia; si no, los macros de la IA con la energía recalculada con los
   factores de la UE.
4. Aceite de cocinar: si el texto no menciona ninguna grasa, lo añade el código según la preparación (plancha,
   horno, salteado) y quita el que hubiera puesto la IA. Lo frito y rebozado ya lleva su grasa en la tabla.
5. Juntar ingredientes repetidos.
"""

import re

from .foodtable import Entry, FoodTable, key, prep_from_words, table
from .matching import canonical_unit
from .textnorm import MASS_UNITS, VOLUME_UNITS, strip_accents

EU_KCAL = {"protein": 4, "carbs": 4, "fat": 9, "fiber": 2, "alcohol": 7}  # Reglamento (UE) 1169/2011, anexo XIV
NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fiber", "alcohol")

# Aceite que absorbe lo cocinado sin rebozar, en gramos por cada 100 g de alimento, con mínimo y máximo por
# ingrediente (una pizca para engrasar la sartén; ni el filete más grande absorbe más de una cucharada).
OIL_RATES = {"plancha": 2.0, "horno": 3.0, "salteado": 5.0}
OIL_MIN, OIL_MAX = 2.0, 10.0
OIL_ENTRY = "aceite-oliva"
OIL_NAME = "aceite de oliva (para cocinar)"
FAT_ENTRIES = frozenset(
    {
        "aceite-oliva",
        "aceite-girasol",
        "aceite-coco",
        "aceite-vegetal",
        "mantequilla",
        "mantequilla-sal",
        "margarina",
        "ghee",
    }
)
FAT_WORDS = frozenset({"aceite", "aove", "mantequilla", "margarina", "manteca", "ghee"})
LIQUID_ML = {"vaso": 200, "taza": 250}
_DRESSING = frozenset({"aliño", "alino", "aderezo"})  # aceite de aliñar una ensalada: lo propone la IA
OFFICIAL = frozenset({"tabla", "etiqueta", "manual", "usuario"})
UNTOUCHED = {"etiqueta", "manual", "usuario"}

_FAT_MENTION = re.compile(r"\b(aceite|aove|mantequilla|margarina|manteca|ghee|chorrito)\b")
# «atún en aceite» o «sardinas en aceite de oliva» nombran la conserva, no la grasa de cocinar.
_CANNED_IN_OIL = re.compile(r"\ben aceite( de (oliva|girasol))?\b")


def eu_kcal(protein: float, carbs: float, fat: float, fiber: float = 0, alcohol: float = 0) -> float:
    return (
        EU_KCAL["protein"] * protein
        + EU_KCAL["carbs"] * carbs
        + EU_KCAL["fat"] * fat
        + EU_KCAL["fiber"] * fiber
        + EU_KCAL["alcohol"] * alcohol
    )


def mentions_fat(text: str) -> bool:
    """El usuario ha dicho algo de la grasa («con AOVE», «sin aceite», «un chorrito»): entonces manda él."""
    plain = _CANNED_IN_OIL.sub(" ", strip_accents((text or "").lower()))
    return bool(_FAT_MENTION.search(plain))


def official_share(items: list[dict]) -> float:
    """Parte de las kcal de la comida que sale de valores oficiales o del propio usuario (0 a 1)."""
    total = sum(float(i.get("kcal") or 0) for i in items)
    if total <= 0:
        return 0.0
    official = sum(float(i.get("kcal") or 0) for i in items if i.get("source") in OFFICIAL)
    return round(official / total, 3)


def _match(ft: FoodTable, item: dict) -> Entry | None:
    food = item.get("food")
    if food:
        found = ft.match(food, item.get("prep"))
        if found is not None:
            return found
    return ft.match_name(item.get("name", ""))


def _prep(item: dict, entry: Entry | None) -> str | None:
    if item.get("prep"):
        return item["prep"]
    if entry is not None:
        return entry.prep
    return prep_from_words(item.get("name", ""))[1]


def _grams(item: dict, entry: Entry | None, photo: bool) -> float:
    ai_grams = float(item.get("grams") or 0)
    if photo or entry is None:
        return ai_grams
    qty = float(item.get("qty") or 0)
    unit = canonical_unit(item.get("unit")) or item.get("unit")
    if qty <= 0 or unit in MASS_UNITS:
        return ai_grams
    if unit in VOLUME_UNITS:
        grams = qty * VOLUME_UNITS[unit] * entry.density
    elif unit in entry.units:
        grams = qty * entry.units[unit]
    elif unit in LIQUID_ML and entry.liquid:
        grams = qty * LIQUID_ML[unit] * entry.density
    else:
        return ai_grams
    # Si la tabla y la IA difieren más del doble, entienden la unidad de forma distinta («1 pieza» de nueces: una nuez
    # para la tabla, un puñado para la IA). Entonces vale el peso que estimó la IA.
    if ai_grams > 0 and not 0.5 <= grams / ai_grams <= 2:
        return ai_grams
    return grams


def _from_entry(item: dict, entry: Entry, grams: float) -> dict:
    factor = grams / 100
    out = {**item, "grams": grams, "source": "tabla", "ref": entry.ref, "food": item.get("food") or entry.food}
    for n in NUTRIENTS:
        out[n] = getattr(entry, f"{n}100") * factor
    if not out["alcohol"]:
        out.pop("alcohol")
    return out


def _from_ai(item: dict) -> dict:
    out = {**item, "source": "ia"}
    out.pop("ref", None)
    out["kcal"] = eu_kcal(
        float(item.get("protein") or 0),
        float(item.get("carbs") or 0),
        float(item.get("fat") or 0),
        float(item.get("fiber") or 0),
        float(item.get("alcohol") or 0),
    )
    return out


def _is_fat(item: dict, entry: Entry | None) -> bool:
    if entry is not None:
        return entry.id in FAT_ENTRIES
    words = key(item.get("name", "")).split()
    return bool(words) and words[0] in FAT_WORDS


def _cooking_oil(item: dict, entry: Entry | None, grams: float) -> float:
    prep = _prep(item, entry)
    if prep not in OIL_RATES or (entry is not None and entry.oil) or grams <= 0:
        return 0.0
    return min(OIL_MAX, max(OIL_MIN, OIL_RATES[prep] * grams / 100))


def _merge(items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in items:
        name = item["name"].strip().lower()
        first = merged.get(name)
        if first is None:
            merged[name] = dict(item)
            continue
        if first.get("unit") == item.get("unit"):
            first["qty"] = float(first.get("qty") or 0) + float(item.get("qty") or 0)
        else:
            first["unit"], first["qty"] = "g", None  # unidades distintas: queda el total en gramos
        for n in ("grams", *NUTRIENTS):
            if first.get(n) is not None or item.get(n) is not None:
                first[n] = float(first.get(n) or 0) + float(item.get(n) or 0)
    for item in merged.values():
        if item.get("qty") is None:
            item["qty"] = item["grams"]
    return list(merged.values())


def _rounded(item: dict) -> dict:
    out = dict(item)
    for n in ("qty", "grams", *NUTRIENTS):
        if out.get(n) is not None:
            out[n] = round(float(out[n]), 1)
    return out


def refine(items: list[dict], *, text: str = "", photo: bool = False) -> tuple[list[dict], list[str]]:
    """Ingredientes con valores oficiales donde los hay, gramos y aceite calculados en código. Devuelve también
    notas para el usuario sobre lo que se ha supuesto."""
    ft = table()
    user_fat = mentions_fat(text)
    out: list[dict] = []
    notes: list[str] = []
    oil_grams = 0.0
    dropped_oil = False
    for item in items:
        source = item.get("source") or (
            "etiqueta" if item.get("product_id") else "manual" if item.get("manual") else None
        )
        if source in UNTOUCHED:
            out.append({**item, "source": source})
            continue
        entry = _match(ft, item)
        if not user_fat and _is_fat(item, entry) and not _DRESSING.intersection(key(item.get("name", "")).split()):
            dropped_oil = True  # la grasa de cocinar la pone el código, según la preparación
            continue
        grams = _grams(item, entry, photo)
        refined = _from_entry(item, entry, grams) if entry is not None else _from_ai(item)
        refined["prep"] = _prep(item, entry)
        if not user_fat:
            oil_grams += _cooking_oil(item, entry, grams)
        out.append(refined)

    if oil_grams > 0:
        oil = ft.entries[OIL_ENTRY]
        base = {"name": OIL_NAME, "qty": oil_grams, "unit": "g", "food": oil.food, "prep": "ninguna"}
        out.append(_from_entry(base, oil, oil_grams))
        notes.append(f"Aceite para cocinar: {round(oil_grams)} g según la preparación (dímelo si no llevaba)")
    elif dropped_oil:
        notes.append("Sin aceite de cocinar: lo frito ya lo lleva incluido")
    return [_rounded(i) for i in _merge(out)], notes


def revalue(items: list[dict]) -> list[dict]:
    """Pone valores oficiales a ingredientes ya guardados (historial), sin tocar sus gramos ni añadir o quitar nada.

    Lo que se apuntó antes de la tabla conserva la estructura que el usuario revisó y guardó; solo cambian las
    cifras por 100 g de lo que está en la tabla. Lo que no está, recalcula su energía con los factores de la UE.
    """
    ft = table()
    out = []
    for item in items:
        source = item.get("source") or (
            "etiqueta" if item.get("product_id") else "manual" if item.get("manual") else None
        )
        if source in UNTOUCHED:
            out.append({**item, "source": source})
            continue
        entry = _match(ft, item)
        grams = float(item.get("grams") or 0)
        out.append(_rounded(_from_entry(item, entry, grams) if entry is not None else _from_ai(item)))
    return out
