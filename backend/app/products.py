"""Productos envasados del usuario: emparejar lo que escribe con una etiqueta guardada y multiplicar.

El frontend tiene un espejo de este módulo (frontend/src/lib/products.ts). Los dos se prueban contra el mismo
fichero de casos (backend/tests/fixtures/product_cases.json): si cambias uno, cambia el otro.
"""

import math
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .matching import canonical_unit
from .textnorm import MASS_UNITS, UNITS, VOLUME_UNITS, is_number, normalize, parse_part, singular, split_parts

TOKEN_SIMILARITY = 85  # tolera plurales raros y erratas ("yogurt")
GENERIC_UNITS = {None, "pieza", "racion"}  # «dos yogures», «una ración»: cuentan como unidades del producto
_STOPWORDS = {"con"}
_UNIT_WORDS = set(UNITS) | set(UNITS.values())
_WITH = re.compile(r"\s+con\s+", re.IGNORECASE)


@dataclass(frozen=True)
class ProductInfo:
    id: int
    name: str
    alias: str
    basis: str
    kcal100: float
    protein100: float
    carbs100: float
    fat100: float
    unit_label: str
    unit_grams: float | None


def round1(value: float) -> float:
    """Redondeo a un decimal igual que Math.round de JavaScript, para que servidor y móvil coincidan."""
    return math.floor(value * 10 + 0.5) / 10


def tokens(text: str) -> frozenset[str]:
    return frozenset(
        singular(t)
        for t in normalize(text).split()
        if t and not is_number(t) and t not in _UNIT_WORDS and t not in _STOPWORDS
    )


def _same(a: str, b: str) -> bool:
    return a == b or fuzz.ratio(a, b) >= TOKEN_SIMILARITY


def _covered(wanted: frozenset[str], pool: frozenset[str]) -> bool:
    return all(any(_same(w, p) for p in pool) for w in wanted)


def _equal(a: frozenset[str], b: frozenset[str]) -> bool:
    return bool(a) and bool(b) and _covered(a, b) and _covered(b, a)


def _label_tokens(product: ProductInfo) -> frozenset[str]:
    return tokens(product.unit_label) if product.unit_label else frozenset()


def match_product(wanted: frozenset[str], products: list[ProductInfo]) -> ProductInfo | None:
    """El producto al que se refiere lo escrito, o None.

    Hay que nombrar TODO el alias («yogur ligero»); lo que sobre tiene que ser del nombre del producto («de
    limón»). Así «yogur» solo no se confunde con «yogur ligero», ni «yogur natural» con «yogur griego natural».
    `products` va ordenado por uso: al empatar gana el primero.
    """
    if not wanted:
        return None
    best: ProductInfo | None = None
    best_key: tuple[int, int] = (-1, -1)
    for product in products:
        name = tokens(product.name)
        alias = tokens(product.alias) or name
        pool = alias | name
        if not pool:
            continue
        # «una tarrina de queso batido»: la unidad del propio producto no cuenta como palabra del nombre.
        candidates = [wanted]
        without_unit = wanted - _label_tokens(product)
        if without_unit and without_unit != wanted:
            candidates.append(without_unit)
        for words in candidates:
            exact = _equal(words, alias) or _equal(words, name)
            if not exact and not (_covered(alias, words) and _covered(words, pool)):
                continue
            key = (1 if exact else 0, len(alias))  # lo exacto gana; después, el alias más específico
            if key > best_key:
                best, best_key = product, key
            break
    return best


def item_for(product: ProductInfo, qty: float, unit: str | None) -> dict | None:
    """El ingrediente para «qty unit» de este producto, o None si no se puede saber cuánto pesa."""
    if qty <= 0:
        return None
    if unit in MASS_UNITS:
        grams = qty * MASS_UNITS[unit]
    elif unit in VOLUME_UNITS:
        grams = qty * VOLUME_UNITS[unit]  # ml ≈ g: valen los mismos valores por 100
    elif product.unit_grams and (unit in GENERIC_UNITS or unit == canonical_unit(product.unit_label)):
        grams = qty * product.unit_grams
    else:
        return None
    if grams <= 0 or grams > 5000:
        return None
    factor = grams / 100
    return {
        "name": product.name,
        "qty": qty,
        "unit": unit or "pieza",
        "grams": round1(grams),
        "kcal": round1(product.kcal100 * factor),
        "protein": round1(product.protein100 * factor),
        "carbs": round1(product.carbs100 * factor),
        "fat": round1(product.fat100 * factor),
        "product_id": product.id,
    }


def _try(piece: str, products: list[ProductInfo]) -> dict | None:
    qty, unit, name = parse_part(piece)
    product = match_product(tokens(name), products) if name else None
    return item_for(product, qty, unit) if product else None


@dataclass
class Resolution:
    items: list[dict]  # los ingredientes que salen de productos guardados
    rest: list[str]  # lo que no es de ningún producto: sigue su camino (caché, IA)


def resolve_text(text: str, products: list[ProductInfo]) -> Resolution:
    """Separa lo que es de un producto guardado de lo que no, y calcula lo primero.

    «dos yogures ligeros con una manzana» -> 2 × yogur ligero (de la etiqueta) y «una manzana» para lo demás.
    Un «con» solo parte la frase si algún lado es un producto: «café con leche» se queda entero.
    """
    items: list[dict] = []
    rest: list[str] = []
    if not products:
        return Resolution([], [text.strip()] if text.strip() else [])
    for fragment in split_parts(text):
        whole = _try(fragment, products)
        if whole:
            items.append(whole)
            continue
        pieces = [p.strip() for p in _WITH.split(fragment) if p.strip()]
        found = [_try(piece, products) for piece in pieces] if len(pieces) > 1 else [None]
        if not any(found):
            rest.append(fragment)
            continue
        pending: list[str] = []
        for piece, item in zip(pieces, found, strict=True):
            if item:
                items.append(item)
                if pending:
                    rest.append(" con ".join(pending))
                    pending = []
            else:
                pending.append(piece)
        if pending:
            rest.append(" con ".join(pending))
    return Resolution(items, rest)
