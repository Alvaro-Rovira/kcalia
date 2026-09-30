"""Normalización de texto para comparar comidas sin IA.

El frontend tiene un espejo de este módulo (frontend/src/lib/textnorm.ts) para poder
resolver comidas del historial sin conexión. Ambos se prueban contra el mismo fichero
de casos (backend/tests/fixtures/normalize_cases.json): si cambias uno, cambia el otro.
"""

import re
import unicodedata

ARTICLES = frozenset({"el", "la", "los", "las", "un", "una", "uno", "unos", "unas", "de", "del"})

NUMBER_WORDS: dict[str, str] = {
    "medio": "0.5",
    "media": "0.5",
    "par": "2",
    "dos": "2",
    "tres": "3",
    "cuatro": "4",
    "cinco": "5",
    "seis": "6",
    "siete": "7",
    "ocho": "8",
    "nueve": "9",
    "diez": "10",
    "once": "11",
    "doce": "12",
}

_UNIT_GROUPS: dict[str, tuple[str, ...]] = {
    "g": ("g", "gr", "grs", "gramo", "gramos"),
    "kg": ("kg", "kilo", "kilos", "kilogramo", "kilogramos"),
    "ml": ("ml", "mililitro", "mililitros"),
    "cl": ("cl", "centilitro", "centilitros"),
    "l": ("l", "litro", "litros"),
    "cda": ("cda", "cdas", "cucharada", "cucharadas"),
    "cdta": ("cdta", "cdtas", "cucharadita", "cucharaditas"),
    "vaso": ("vaso", "vasos"),
    "taza": ("taza", "tazas"),
    "rebanada": ("rebanada", "rebanadas"),
    "loncha": ("loncha", "lonchas"),
    "lata": ("lata", "latas"),
    "puñado": ("puñado", "puñados"),
    "plato": ("plato", "platos"),
    "racion": ("racion", "raciones"),
    "pieza": ("pieza", "piezas", "unidad", "unidades", "ud", "uds"),
    "bol": ("bol", "boles", "cuenco", "cuencos"),
    "cazo": ("cazo", "cazos", "scoop", "scoops"),
}
UNITS: dict[str, str] = {alias: unit for unit, aliases in _UNIT_GROUPS.items() for alias in aliases}
MASS_UNITS = {"g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "cl": 10.0, "l": 1000.0}
DEFAULT_UNIT = "pieza"

_VULGAR = {"½": " 0.5 ", "¼": " 0.25 ", "¾": " 0.75 "}
_FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_DIGIT_LETTER = re.compile(r"(\d)([a-zñ])")
_LETTER_DIGIT = re.compile(r"([a-zñ])(\d)")
_NOT_ALLOWED = re.compile(r"[^a-z0-9ñ. ]")
_STRAY_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")
_SPLIT = re.compile(r"[,;+\n]|\s+(?:y|e|mas|más)\s+", re.IGNORECASE)


def strip_accents(text: str) -> str:
    """Quita tildes y diéresis pero conserva la ñ (piña ≠ pina)."""
    text = text.replace("ñ", "\x00").replace("Ñ", "\x00")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text.replace("\x00", "ñ")


def format_number(value: float) -> str:
    return f"{round(value, 3):.3f}".rstrip("0").rstrip(".")


def is_number(token: str) -> bool:
    return bool(_NUMBER.match(token))


def base_tokens(text: str) -> list[str]:
    """Minúsculas, sin tildes ni signos; números y unidades en forma canónica."""
    text = text.lower()
    for char, replacement in _VULGAR.items():
        text = text.replace(char, replacement)
    text = strip_accents(text)
    text = _FRACTION.sub(lambda m: format_number(int(m[1]) / int(m[2])) if int(m[2]) else m[0], text)
    text = _DECIMAL_COMMA.sub(".", text)
    text = _DIGIT_LETTER.sub(r"\1 \2", text)
    text = _LETTER_DIGIT.sub(r"\1 \2", text)
    text = _NOT_ALLOWED.sub(" ", text)
    text = _STRAY_DOT.sub(" ", text)
    tokens = []
    for token in text.split():
        if is_number(token):
            token = format_number(float(token))
        token = NUMBER_WORDS.get(token, token)
        tokens.append(UNITS.get(token, token))
    return tokens


def normalize(text: str) -> str:
    """Clave de comparación: "Un café con leche" y "café con leche" dan lo mismo."""
    tokens = [t for t in base_tokens(text) if t not in ARTICLES]
    out = []
    for i, token in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        # "1 huevo" equivale a "huevo"; "1 kg de arroz" no equivale a "kg de arroz".
        if token == "1" and nxt is not None and not is_number(nxt) and nxt not in _UNIT_GROUPS:
            continue
        out.append(token)
    return " ".join(out)


def numbers_in(norm: str) -> list[str]:
    return sorted(t for t in norm.split() if is_number(t))


def singular(token: str) -> str:
    """Singular aproximado. No pretende ser correcto, solo estable en ambos lados."""
    if len(token) <= 3 or is_number(token):
        return token
    if token.endswith("ces"):
        return token[:-3] + "z"
    if token.endswith("es") and token[-3] in "lrndjsz":
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def food_key(name: str) -> str:
    return " ".join(singular(t) for t in normalize(name).split())


def split_parts(text: str) -> list[str]:
    return [p.strip() for p in _SPLIT.split(text) if p and p.strip()]


def parse_part(part: str) -> tuple[float, str | None, str]:
    """ "200 g de arroz" -> (200, "g", "arroz"); "dos huevos" -> (2, None, "huevo")."""
    raw = base_tokens(part)
    qty: float | None = None
    if raw and raw[0] in ("un", "una", "uno"):
        qty = 1.0
        raw = raw[1:]
    tokens = [t for t in raw if t not in ARTICLES]
    unit: str | None = None
    if tokens and is_number(tokens[0]):
        qty = float(tokens[0])
        tokens = tokens[1:]
        if tokens and tokens[0] in _UNIT_GROUPS:
            unit = tokens[0]
            tokens = tokens[1:]
    elif len(tokens) >= 3 and is_number(tokens[-2]) and tokens[-1] in _UNIT_GROUPS:
        # "arroz 200 g"
        qty = float(tokens[-2])
        unit = tokens[-1]
        tokens = tokens[:-2]
    elif tokens and tokens[0] in _UNIT_GROUPS and len(tokens) > 1:
        # "un vaso de leche" -> cantidad implícita 1
        unit = tokens[0]
        tokens = tokens[1:]
    name = " ".join(singular(t) for t in tokens)
    return (qty if qty is not None else 1.0, unit, name)
