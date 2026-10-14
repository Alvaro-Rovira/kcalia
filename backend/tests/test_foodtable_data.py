"""Comprobaciones de la tabla real (`app/data/`): que ninguna cifra se pierda ni se cuele mal."""

import csv
import json
from collections import defaultdict

import pytest

from app.foodtable import DATA_DIR, PREPS, FoodTable, key, parse_value

ALLOWED_UNITS = {
    "pieza", "rebanada", "loncha", "lata", "puñado", "plato", "racion", "bol", "cazo", "cda", "cdta", "vaso", "taza",
}  # fmt: skip

# Alimentos que deben estar sí o sí: las referencias que tenía el prompt y las comidas del banco de pruebas.
REQUIRED = [
    "huevo", "clara de huevo", "pan blanco", "pan integral", "pan de molde", "arroz blanco cocido", "arroz crudo",
    "pasta cocida", "pasta cruda", "patata cocida", "patatas fritas", "copos de avena", "pechuga de pollo a la plancha",
    "pechuga de pollo cruda", "muslo de pollo asado", "ternera a la plancha", "lomo de cerdo a la plancha",
    "carne picada", "salmon a la plancha", "merluza", "atun al natural", "atun en aceite", "jamon serrano",
    "jamon cocido", "pavo en lonchas", "chorizo", "queso curado", "queso fresco batido 0", "mozzarella",
    "leche entera", "leche semidesnatada", "leche desnatada", "bebida de avena", "yogur natural", "yogur griego",
    "yogur proteico", "aceite de oliva", "mantequilla", "aguacate", "lentejas", "garbanzos", "alubias", "platano",
    "manzana", "naranja", "fresas", "tomate", "lechuga", "brocoli", "zanahoria", "nueces", "almendras",
    "crema de cacahuete", "proteina whey", "azucar", "miel", "chocolate negro", "galletas maria", "tortilla de patatas",
    "paella", "lentejas con chorizo", "pizza margarita", "croquetas", "cerveza", "vino tinto", "refresco de cola",
    "zumo de naranja", "cafe con leche", "cortado", "patatas fritas de bolsa", "hamburguesa",
]  # fmt: skip


@pytest.fixture(scope="module")
def ft():
    return FoodTable.load(DATA_DIR)


@pytest.fixture(scope="module")
def specs():
    foods = json.loads((DATA_DIR / "alimentos.json").read_text(encoding="utf-8"))
    recipes = json.loads((DATA_DIR / "recetas.json").read_text(encoding="utf-8"))
    return foods, recipes


def _codes(filename: str) -> dict[str, dict]:
    with (DATA_DIR / filename).open(newline="", encoding="utf-8") as handle:
        return {row["code"]: row for row in csv.DictReader(handle, delimiter="\t")}


def test_every_reference_exists_in_its_source_extract(specs):
    sources = {"ciqual": _codes("ciqual_2025.tsv"), "usda": _codes("usda_fdc.tsv")}
    foods, _ = specs
    missing = [f["id"] for f in foods if f["ref"].partition(":")[2] not in sources[f["ref"].partition(":")[0]]]
    assert missing == []


def test_extract_rows_with_energy_cover_every_used_code(specs):
    ciqual = _codes("ciqual_2025.tsv")
    foods, _ = specs
    used = [f["ref"][7:] for f in foods if f["ref"].startswith("ciqual:")]
    without_energy = sorted(
        {code for code in used if parse_value(ciqual[code]["kcal"]) == 0 and ciqual[code]["kcal"] != "0"}
    )
    assert without_energy == [], "filas sin energía en CIQUAL: no sirven como valor oficial"


def test_ids_are_unique(specs):
    foods, recipes = specs
    ids = [f["id"] for f in foods] + [r["id"] for r in recipes]
    assert len(ids) == len(set(ids))


def test_no_name_or_alias_points_to_two_entries(ft):
    owners: dict[str, set[str]] = defaultdict(set)
    for entry in ft.entries.values():
        for name in (entry.name, *entry.aliases):
            owners[key(name)].add(entry.id)
    clashes = {k: sorted(v) for k, v in owners.items() if len(v) > 1}
    assert clashes == {}


def test_every_food_has_at_most_one_default(ft):
    # Sin «default» (pez espada, solo en crudo) el alimento necesita que se diga la preparación.
    groups: dict[str, list] = defaultdict(list)
    for entry in ft.entries.values():
        groups[key(entry.food)].append(entry)
    wrong = {food: [e.id for e in group if e.default] for food, group in groups.items()}
    assert {food: ids for food, ids in wrong.items() if len(ids) > 1} == {}


def test_preparations_and_units_are_known(ft):
    assert {e.id: e.prep for e in ft.entries.values() if e.prep not in PREPS} == {}
    bad_units = {
        e.id: sorted(set(e.units) - ALLOWED_UNITS) for e in ft.entries.values() if set(e.units) - ALLOWED_UNITS
    }
    assert bad_units == {}
    assert {e.id: e.units for e in ft.entries.values() if any(g <= 0 for g in e.units.values())} == {}
    assert {e.id: e.density for e in ft.entries.values() if not 0.3 <= e.density <= 1.6} == {}


def test_macros_fit_in_100_grams(ft):
    over = {
        e.id: round(e.protein100 + e.carbs100 + e.fat100 + e.alcohol100, 1)
        for e in ft.entries.values()
        if e.protein100 + e.carbs100 + e.fat100 + e.alcohol100 > 105
    }
    assert over == {}


def test_energy_agrees_with_the_eu_factors(ft):
    """Detecta una fila mal leída: la energía oficial y la de 4/4/9/2/7 casi coinciden (ácidos orgánicos y polioles
    explican lo que falta en fruta, vinagre o chicles, de ahí el margen)."""
    off = {}
    organic_acids = {"limon", "lima", "vinagre", "vinagre-balsamico"}  # ácido cítrico y acético: 3 kcal/g en la UE
    for e in ft.entries.values():
        if e.id in organic_acids:
            continue
        eu = 4 * e.protein100 + 4 * e.carbs100 + 9 * e.fat100 + 2 * e.fiber100 + 7 * e.alcohol100
        if abs(e.kcal100 - eu) > max(12, 0.15 * e.kcal100):
            off[e.id] = (round(e.kcal100), round(eu))
    assert off == {}


@pytest.mark.parametrize("name", REQUIRED)
def test_required_foods_are_present(ft, name):
    assert ft.match(name) is not None, name


def test_table_size(ft):
    assert len(ft.entries) >= 450


def test_usda_rows_carry_every_value():
    empty = {code: row["name"] for code, row in _codes("usda_fdc.tsv").items() if not row["kcal"] or not row["protein"]}
    assert empty == {}


def test_search_prefers_names_over_aliases(ft):
    # «Fiambre de pollo» tiene el alias «pechuga de pollo en lonchas», pero quien busca «pechuga pollo» quiere la pechuga.
    assert ft.search("pechuga pollo")[0].id == "pechuga-pollo-plancha"
