"""Tabla de alimentos con valores oficiales: CIQUAL 2025 (ANSES), USDA FoodData Central y recetas estándar.

Las cifras se leen tal cual de los extractos literales de cada fuente (`data/*.tsv`); aquí solo se interpreta la
coma decimal y los «-», «traces» y «< x» (cantidades no medibles) como 0. Los nombres en español, las preparaciones,
los pesos de las unidades y las densidades están en `data/alimentos.json`; los platos que no figuran en ninguna fuente
se calculan con su receta (`data/recetas.json`). Fuentes y licencias: `data/FUENTES.md`.

El emparejado es estricto a propósito: un valor oficial de otro alimento o de otra preparación sería peor que la
estimación de la IA, así que si no hay coincidencia clara se devuelve None.
"""

import csv
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .textnorm import food_key as _base_key

DATA_DIR = Path(__file__).parent / "data"
PREPS = ("crudo", "cocido", "plancha", "horno", "salteado", "frito", "rebozado", "guisado", "ninguna")
NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fiber", "alcohol")
SOURCES = {"ciqual": "ciqual_2025.tsv", "usda": "usda_fdc.tsv"}

# Palabras (ya normalizadas y en singular) que indican la preparación. Las que también son alimentos («romana») solo
# cuentan detrás de «a»/«al»: «calamares a la romana» sí, «lechuga romana» no.
PREP_WORDS: dict[str, str] = {
    **dict.fromkeys(("crudo", "cruda"), "crudo"),
    **dict.fromkeys(("cocido", "cocida", "hervido", "hervida", "vapor", "escalfado", "escalfada"), "cocido"),
    **dict.fromkeys(("plancha", "parrilla", "brasa", "grill", "grillado", "grillada", "barbacoa"), "plancha"),
    **dict.fromkeys(("horno", "asado", "asada"), "horno"),
    **dict.fromkeys(("salteado", "salteada", "revuelto", "revuelta", "sarten", "pochado", "pochada"), "salteado"),
    **dict.fromkeys(("frito", "frita"), "frito"),
    **dict.fromkeys(("rebozado", "rebozada", "empanado", "empanada", "tempura"), "rebozado"),
    **dict.fromkeys(("guisado", "guisada", "estofado", "estofada"), "guisado"),
}
PREP_AFTER_A = {"romana": "rebozado"}
_LINKS = frozenset({"a", "al", "en"})


def parse_value(raw: str) -> float:
    """Una celda de la fuente: «1,5» -> 1.5; «-», «traces» o «< 0,2» (no medible) -> 0."""
    text = (raw or "").strip().replace(",", ".")
    if not text or text == "-" or text.startswith("<") or text.lower() == "traces":
        return 0.0
    return float(text)


def key(text: str) -> str:
    """Clave de comparación: minúsculas, sin tildes, singular y sin artículos ni «a», «al», «en»."""
    return " ".join(t for t in _base_key(text).split() if t not in _LINKS)


def prep_from_words(text: str) -> tuple[str, str | None]:
    """Separa la preparación del nombre: «pechuga de pollo a la plancha» -> («pechuga pollo», «plancha»)."""
    tokens = _base_key(text).split()
    prep = None
    kept: list[str] = []
    for i, token in enumerate(tokens):
        after_a = i > 0 and tokens[i - 1] in ("a", "al")
        found = PREP_WORDS.get(token) or (PREP_AFTER_A.get(token) if after_a else None)
        if found and prep is None:
            prep = found
            continue
        kept.append(token)
    base = " ".join(t for t in kept if t not in _LINKS)
    return (base, prep) if base else (key(text), None)


def compatible(wanted: str, available: str) -> bool:
    return wanted == available or {wanted, available} == {"plancha", "horno"}


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    food: str
    prep: str
    ref: str
    source: str
    kcal100: float
    protein100: float
    carbs100: float
    fat100: float
    fiber100: float
    alcohol100: float
    units: dict[str, float] = field(default_factory=dict)
    density: float = 1.0
    oil: bool = False
    default: bool = False
    aliases: tuple[str, ...] = ()
    liquid: bool = False  # tiene densidad propia: «vaso» y «taza» se miden en mililitros

    def per100(self) -> dict[str, float]:
        return {f"{n}100": getattr(self, f"{n}100") for n in NUTRIENTS}


def _read_row(row: dict[str, str]) -> dict[str, float]:
    values = {n: parse_value(row[n]) for n in NUTRIENTS if n in row}
    if "carbs_total" in row:
        # USDA publica los hidratos «por diferencia», con la fibra dentro; en la tabla van los disponibles, como
        # en CIQUAL y en las etiquetas europeas (la fibra cuenta aparte, a 2 kcal/g).
        values["carbs"] = max(0.0, parse_value(row["carbs_total"]) - values["fiber"])
    return values


def _read_source(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["code"]: _read_row(row) for row in csv.DictReader(handle, delimiter="\t")}


def _entry(spec: dict, values: dict[str, float], ref: str, source: str) -> Entry:
    return Entry(
        id=spec["id"],
        name=spec["name"],
        food=spec.get("food") or spec["name"],
        prep=spec.get("prep", "ninguna"),
        ref=ref,
        source=source,
        **{f"{n}100": values[n] for n in NUTRIENTS},
        units={k: float(v) for k, v in (spec.get("units") or {}).items()},
        density=float(spec.get("density", 1.0)),
        oil=bool(spec.get("oil", False)),
        default=bool(spec.get("default", False)),
        aliases=tuple(spec.get("aliases") or ()),
        liquid="density" in spec,
    )


class FoodTable:
    def __init__(self, entries: dict[str, Entry]):
        self.entries = entries
        self._exact: dict[str, Entry] = {}
        self._foods: dict[str, list[Entry]] = {}
        for entry in entries.values():
            for name in (entry.name, *entry.aliases):
                self._exact.setdefault(key(name), entry)
            self._foods.setdefault(key(entry.food), []).append(entry)

    @classmethod
    def load(cls, directory: Path = DATA_DIR) -> "FoodTable":
        sources = {name: _read_source(directory / filename) for name, filename in SOURCES.items()}
        entries: dict[str, Entry] = {}
        for spec in json.loads((directory / "alimentos.json").read_text(encoding="utf-8")):
            source, _, code = spec["ref"].partition(":")
            entries[spec["id"]] = _entry(spec, sources[source][code], spec["ref"], source)
        recipes_path = directory / "recetas.json"
        for spec in json.loads(recipes_path.read_text(encoding="utf-8")) if recipes_path.exists() else []:
            entries[spec["id"]] = _entry(spec, _recipe_values(spec, entries), f"receta:{spec['id']}", "receta")
        return cls(entries)

    def _pick(self, group: list[Entry], prep: str | None) -> Entry | None:
        if prep in (None, "ninguna"):
            # Sin «default» (alimentos que solo están en crudo) hace falta decir la preparación.
            defaults = [e for e in group if e.default]
            return defaults[0] if defaults else None
        exact = [e for e in group if e.prep == prep]
        if exact:
            return exact[0]
        near = [e for e in group if compatible(prep, e.prep)]
        return near[0] if near else None

    def match(self, food: str, prep: str | None = None) -> Entry | None:
        """La entrada de ese alimento con esa preparación, o None si no hay una coincidencia clara."""
        k = key(food)
        if not k:
            return None
        entry = self._exact.get(k)
        if entry is not None:
            if prep in (None, "ninguna") or compatible(prep, entry.prep):
                return entry
            return self._pick(self._foods.get(key(entry.food), []), prep)
        group = self._foods.get(k)
        if group:
            return self._pick(group, prep)
        base, found = prep_from_words(food)
        if found and base != k and (prep in (None, "ninguna") or compatible(prep, found)):
            return self.match(base, found)
        return None

    def match_name(self, text: str) -> Entry | None:
        """Como `match`, para un nombre que puede llevar la preparación dentro («huevos fritos»)."""
        return self.match(text)

    def search(self, query: str, limit: int = 8) -> list[Entry]:
        words = key(query).split()
        if not words or len("".join(words)) < 2:
            return []
        k = " ".join(words)
        scored = []
        for entry in self.entries.values():
            names = [key(n) for n in (entry.name, *entry.aliases)]
            if not any(all(w in n for w in words) for n in names):
                continue
            scored.append((0 if k in names else 1, 0 if entry.default else 1, len(entry.name), entry.id, entry))
        scored.sort(key=lambda row: row[:4])
        return [row[-1] for row in scored[:limit]]


def _recipe_values(spec: dict, entries: dict[str, Entry]) -> dict[str, float]:
    """Valores por 100 g del plato: suma de los ingredientes sobre el peso final (crudo × rendimiento)."""
    total_grams = sum(grams for _, grams in spec["ingredients"])
    cooked = total_grams * float(spec.get("yield", 1.0))
    sums = dict.fromkeys(NUTRIENTS, 0.0)
    for ingredient_id, grams in spec["ingredients"]:
        ingredient = entries[ingredient_id]
        for n in NUTRIENTS:
            sums[n] += getattr(ingredient, f"{n}100") * grams / 100
    return {n: sums[n] / cooked * 100 for n in NUTRIENTS}


@lru_cache(maxsize=1)
def table() -> FoodTable:
    return FoodTable.load()
