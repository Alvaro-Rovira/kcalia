"""Códigos de barras: validación y consulta a Open Food Facts (base de datos colaborativa y abierta).

La consulta sale siempre del servidor, con un User-Agent identificable, tiempo de espera corto y caché local
(también de los códigos que no existen), para no castigar su API ni depender de ella. El resultado es un borrador
con la misma forma que la lectura de una etiqueta: el usuario lo revisa antes de guardar.
"""

import logging
import re
from datetime import timedelta

import httpx

from .config import get_settings
from .models import BarcodeCache, utcnow

log = logging.getLogger("kcalia.barcode")

OFF_PATH = "/api/v2/product/{code}"
OFF_FIELDS = (
    "code,product_name,product_name_es,generic_name_es,brands,quantity,serving_size,serving_quantity,"
    "nutriments,nutrition_data_per"
)
# Solo ASCII: las cabeceras HTTP no admiten tildes.
USER_AGENT = "Kcalia/1.0 (personal nutrition app; https://github.com/Alvaro-Rovira/kcalia)"
TIMEOUT = 6.0
FOUND_TTL = timedelta(days=30)
MISSING_TTL = timedelta(days=3)
KCAL_PER_KJ = 4.184
SOURCE_NOTE = "Datos de Open Food Facts, una base colaborativa: compáralos con el envase antes de guardar."

_ML = re.compile(r"\d\s*(ml|cl|l)\b", re.IGNORECASE)
_UNIT = re.compile(r"^\s*1\s+([a-záéíóúñü]+)", re.IGNORECASE)


def normalize_code(raw: str) -> str | None:
    """Solo dígitos; UPC-A (12) pasa a EAN-13 con un cero delante. None si no es un código de producto válido."""
    code = re.sub(r"\D", "", raw or "")
    if len(code) == 12:
        code = "0" + code
    if len(code) not in (8, 13, 14):
        return None
    if len(code) == 8:
        # EAN-8 o UPC-E: el dígito de control de UPC-E se calcula sobre el código expandido; se acepta tal cual.
        return code
    return code if gtin_check(code) else None


def gtin_check(code: str) -> bool:
    digits = [int(c) for c in code]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == digits[-1]


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def to_draft(product: dict, code: str) -> dict:
    """De la ficha de Open Food Facts al borrador que se revisa (mismas claves que la lectura de una etiqueta)."""
    nutriments = product.get("nutriments") or {}
    warnings = [SOURCE_NOTE]

    def per100(key: str) -> float | None:
        return _number(nutriments.get(f"{key}_100g"))

    values = {
        "kcal100": per100("energy-kcal"),
        "protein100": per100("proteins"),
        "carbs100": per100("carbohydrates"),
        "fat100": per100("fat"),
    }
    if values["kcal100"] is None:
        kj = per100("energy-kj") or per100("energy")
        if kj:
            values["kcal100"] = round(kj / KCAL_PER_KJ)
            warnings.append("Las calorías se han calculado a partir de los kJ.")
    if values["kcal100"] is not None and values["kcal100"] > 950:
        values["kcal100"] = None
        warnings.append("Las calorías de Open Food Facts no son posibles por 100 g: escríbelas tú.")
    if sum(v or 0 for k, v in values.items() if k != "kcal100") > 105:
        for key in ("protein100", "carbs100", "fat100"):
            values[key] = None
        warnings.append("Los macros de Open Food Facts suman más de 100 g por 100 g: escríbelos tú.")

    name = (
        product.get("product_name_es") or product.get("product_name") or product.get("generic_name_es") or ""
    ).strip()
    brand = (product.get("brands") or "").split(",")[0].strip()
    serving_g = _number(product.get("serving_quantity"))
    unit_grams = round(serving_g, 2) if serving_g and 0 < serving_g <= 5000 else None
    unit = _UNIT.match(product.get("serving_size") or "")
    unit_label = unit.group(1).lower() if unit else ("porción" if unit_grams else "")
    basis = "ml" if _ML.search(product.get("quantity") or "") else "g"

    missing = [key for key, value in values.items() if value is None]
    if missing:
        warnings.append("Faltan datos en Open Food Facts: complétalos con la etiqueta (o haz una foto).")
    if not name:
        warnings.append("Open Food Facts no tiene el nombre del producto: ponle uno.")

    def clean(value):
        return None if value is None else round(float(value), 2)

    return {
        "name": (f"{name} ({brand})" if name and brand and brand.lower() not in name.lower() else name)[:120],
        "alias": name.lower()[:60],
        "basis": basis,
        **{key: clean(value) for key, value in values.items()},
        "fiber100": clean(per100("fiber")),
        "sugars100": clean(per100("sugars")),
        "salt100": clean(per100("salt")),
        "unit_label": unit_label[:30],
        "unit_grams": unit_grams,
        "confidence": 0.75 if not missing else 0.5,
        "warnings": warnings,
        "missing": missing,
        "barcode": code,
    }


class LookupError_(Exception):
    """Open Food Facts no ha respondido (sin red, caído o lento)."""


def fetch_off(code: str, http: httpx.Client | None = None) -> dict | None:
    """La ficha del producto, o None si Open Food Facts no lo tiene. LookupError_ si no responde."""
    client = http or httpx.Client(timeout=TIMEOUT)
    try:
        response = client.get(
            get_settings().off_base_url.rstrip("/") + OFF_PATH.format(code=code),
            params={"fields": OFF_FIELDS},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
    except httpx.HTTPError as exc:
        raise LookupError_(str(exc)) from exc
    finally:
        if http is None:
            client.close()
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        log.warning("Open Food Facts respondió %s para %s", response.status_code, code)
        raise LookupError_(f"HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise LookupError_("respuesta no JSON") from exc
    if not data.get("product") or data.get("status") in (0, "failure"):
        return None
    return data["product"]


def lookup(db, code: str, http: httpx.Client | None = None) -> dict:
    """{"status": "found", "draft": ...} o {"status": "not_found"} usando la caché si está fresca."""
    cached = db.get(BarcodeCache, code)
    now = utcnow()
    if cached is not None and now - cached.fetched_at < (FOUND_TTL if cached.found else MISSING_TTL):
        return {"status": "found", "draft": to_draft(cached.data, code)} if cached.found else {"status": "not_found"}
    product = fetch_off(code, http)
    if cached is None:
        cached = BarcodeCache(code=code)
        db.add(cached)
    cached.found = product is not None
    cached.data = product or {}
    cached.fetched_at = now
    db.commit()
    return {"status": "found", "draft": to_draft(product, code)} if product else {"status": "not_found"}
