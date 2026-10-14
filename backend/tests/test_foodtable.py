import json

import pytest

from app.foodtable import FoodTable, parse_value, prep_from_words

CIQUAL = """code\tname\tkcal\tprotein\tcarbs\tfat\tfiber\talcohol
9104\tRiz blanc, cuit, sans sel ajouté\t129\t2,68\t28,1\t0,28\t0,4\t0
9100\tRiz blanc, cru\t353\t7,08\t78,4\t0,64\t1,04\t-
36018\tPoulet, filet sans peau grillé/poêlé\t153\t31,3\t0\t2,9\t< 0,5\t0
36015\tDinde, filet, grillé/poêlé\t136\t30,1\t0\t1,74\t-\t-
22004\tOeuf, dur\t134\t12,5\t0,46\t9\t0\ttraces
22030\tOeuf, au plat, frit, avec matière grasse\t197\t13,6\t0,8\t15,6\t0\t0
19024\tYaourt, lait entier, nature\t81\t3,7\t5,4\t3,9\t0\t0
19034\tYaourt à la grecque, nature\t122\t4,8\t3,8\t9,7\t0\t0
4006\tPomme de terre, sans peau, bouillie/cuite à l'eau\t80\t1,8\t17,4\t0,2\t1,6\t0
17270\tHuile d'olive vierge extra\t900\t0\t0\t100\t0\t0
"""

USDA = """code\tname\tkcal\tprotein\tcarbs_total\tfat\tfiber\talcohol
173180\tBeverages, Whey protein powder isolate\t359\t84.4\t6.3\t1.2\t0\t0
168411\tEdamame, frozen, prepared\t121\t11.91\t8.91\t5.2\t5.2\t
"""

FOODS = [
    {
        "id": "arroz-blanco-cocido",
        "name": "arroz blanco cocido",
        "food": "arroz blanco",
        "prep": "cocido",
        "ref": "ciqual:9104",
        "aliases": ["arroz", "arroz cocido", "arroz hervido"],
        "units": {"plato": 280},
        "default": True,
    },
    {
        "id": "arroz-blanco-crudo",
        "name": "arroz blanco crudo",
        "food": "arroz blanco",
        "prep": "crudo",
        "ref": "ciqual:9100",
        "aliases": ["arroz crudo", "arroz en seco"],
    },
    {
        "id": "pechuga-pollo-plancha",
        "name": "pechuga de pollo a la plancha",
        "food": "pechuga de pollo",
        "prep": "plancha",
        "ref": "ciqual:36018",
        "aliases": ["pollo", "pechuga"],
        "units": {"pieza": 150},
        "default": True,
    },
    {
        "id": "pechuga-pavo-plancha",
        "name": "pechuga de pavo a la plancha",
        "food": "pechuga de pavo",
        "prep": "plancha",
        "ref": "ciqual:36015",
        "default": True,
    },
    {
        "id": "huevo-cocido",
        "name": "huevo cocido",
        "food": "huevo",
        "prep": "cocido",
        "ref": "ciqual:22004",
        "aliases": ["huevo duro"],
        "units": {"pieza": 50},
        "default": True,
    },
    {
        "id": "huevo-frito",
        "name": "huevo frito",
        "food": "huevo",
        "prep": "frito",
        "ref": "ciqual:22030",
        "units": {"pieza": 50},
        "oil": True,
    },
    {
        "id": "yogur-natural",
        "name": "yogur natural",
        "food": "yogur",
        "prep": "ninguna",
        "ref": "ciqual:19024",
        "units": {"pieza": 125},
        "default": True,
    },
    {
        "id": "yogur-griego",
        "name": "yogur griego",
        "food": "yogur griego",
        "prep": "ninguna",
        "ref": "ciqual:19034",
        "units": {"pieza": 125},
        "default": True,
    },
    {
        "id": "patata-cocida",
        "name": "patata cocida",
        "food": "patata",
        "prep": "cocido",
        "ref": "ciqual:4006",
        "default": True,
    },
    {
        "id": "aceite-oliva",
        "name": "aceite de oliva",
        "food": "aceite de oliva",
        "prep": "ninguna",
        "ref": "ciqual:17270",
        "aliases": ["aceite", "aove"],
        "units": {"cda": 10},
        "density": 0.915,
        "default": True,
    },
    {
        "id": "whey",
        "name": "proteína whey",
        "food": "proteína whey",
        "prep": "ninguna",
        "ref": "usda:173180",
        "aliases": ["proteína en polvo"],
        "units": {"cazo": 30},
        "default": True,
    },
    {"id": "edamame", "name": "edamame", "food": "edamame", "prep": "cocido", "ref": "usda:168411", "default": True},
    {
        "id": "arroz-integral",
        "name": "arroz integral crudo",
        "food": "arroz integral",
        "prep": "crudo",
        "ref": "ciqual:9100",
    },
]

RECIPES = [
    {
        "id": "patata-con-aceite",
        "name": "patata con aceite",
        "food": "patata con aceite",
        "prep": "ninguna",
        "source": "receta de prueba",
        "yield": 0.8,
        "ingredients": [["patata-cocida", 100], ["aceite-oliva", 100]],
        "default": True,
    },
]


@pytest.fixture()
def ft(tmp_path):
    (tmp_path / "ciqual_2025.tsv").write_text(CIQUAL)
    (tmp_path / "usda_fdc.tsv").write_text(USDA)
    (tmp_path / "alimentos.json").write_text(json.dumps(FOODS, ensure_ascii=False))
    (tmp_path / "recetas.json").write_text(json.dumps(RECIPES, ensure_ascii=False))
    return FoodTable.load(tmp_path)


@pytest.mark.parametrize(
    ("raw", "value"),
    [("1,5", 1.5), ("129", 129.0), ("-", 0.0), ("", 0.0), ("< 0,2", 0.0), ("traces", 0.0), ("84.4", 84.4)],
)
def test_parse_value_reads_source_cells_literally(raw, value):
    assert parse_value(raw) == value


def test_values_come_unaltered_from_the_source_row(ft):
    rice = ft.entries["arroz-blanco-cocido"]
    assert (rice.kcal100, rice.protein100, rice.carbs100, rice.fat100, rice.fiber100) == (129, 2.68, 28.1, 0.28, 0.4)
    assert rice.source == "ciqual" and rice.ref == "ciqual:9104"
    assert ft.entries["whey"].protein100 == 84.4 and ft.entries["whey"].source == "usda"


def test_usda_carbohydrates_by_difference_exclude_fiber(ft):
    # USDA publica los hidratos «por diferencia», con la fibra dentro; la tabla guarda los disponibles.
    edamame = ft.entries["edamame"]
    assert edamame.carbs100 == pytest.approx(8.91 - 5.2)
    assert edamame.fiber100 == 5.2 and edamame.alcohol100 == 0


def test_food_without_preparation_uses_the_default_entry(ft):
    assert ft.match("arroz").id == "arroz-blanco-cocido"
    assert ft.match("arroz blanco", "ninguna").id == "arroz-blanco-cocido"


def test_explicit_preparation_picks_that_entry(ft):
    assert ft.match("arroz", "crudo").id == "arroz-blanco-crudo"
    assert ft.match("huevo", "frito").id == "huevo-frito"


def test_grill_and_oven_are_interchangeable(ft):
    assert ft.match("pechuga de pollo", "horno").id == "pechuga-pollo-plancha"


def test_missing_preparation_never_falls_back_to_another_one(ft):
    # Mejor el valor de la IA que el oficial de otra preparación.
    assert ft.match("huevo", "plancha") is None
    assert ft.match("patata", "frito") is None
    assert ft.match("pechuga de pollo", "crudo") is None


def test_food_only_known_raw_needs_an_explicit_preparation(ft):
    # El arroz blanco tiene «default»; un alimento del que solo hay entrada en crudo y sin «default» no se supone
    # crudo si no se dice: cocinado pesa y aporta otra cosa.
    assert ft.match("pechuga de pollo", "crudo") is None
    assert ft.match("arroz integral") is None
    assert ft.match("arroz integral", "crudo").id == "arroz-integral"


def test_matching_is_strict_between_similar_foods(ft):
    assert ft.match("pechuga de pavo").id == "pechuga-pavo-plancha"
    assert ft.match("yogur").id == "yogur-natural"
    assert ft.match("yogur griego").id == "yogur-griego"
    assert ft.match("pechuga de pato") is None
    assert ft.match("arroz con leche") is None


def test_match_tolerates_plurals_accents_and_case(ft):
    assert ft.match("Huevos").id == "huevo-cocido"
    assert ft.match("proteina en polvo").id == "whey"
    assert ft.match("AOVE").id == "aceite-oliva"


def test_match_name_splits_the_preparation_from_the_name(ft):
    assert ft.match_name("huevos fritos").id == "huevo-frito"
    assert ft.match_name("pechuga de pollo a la plancha").id == "pechuga-pollo-plancha"
    assert ft.match_name("arroz blanco cocido").id == "arroz-blanco-cocido"
    assert ft.match_name("huevo duro").id == "huevo-cocido"
    assert ft.match_name("huevo a la plancha") is None


def test_match_accepts_the_preparation_inside_the_food_text(ft):
    assert ft.match("huevo frito").id == "huevo-frito"
    assert ft.match("pollo asado").id == "pechuga-pollo-plancha"


def test_recipe_values_are_the_sum_of_ingredients_over_the_cooked_weight(ft):
    dish = ft.entries["patata-con-aceite"]
    assert dish.source == "receta" and dish.ref == "receta:patata-con-aceite"
    assert dish.kcal100 == pytest.approx((80 + 900) / 160 * 100)
    assert dish.fat100 == pytest.approx((0.2 + 100) / 160 * 100)


def test_entry_defaults(ft):
    rice = ft.entries["arroz-blanco-crudo"]
    assert rice.density == 1.0 and rice.units == {} and rice.oil is False and rice.default is False
    assert ft.entries["huevo-frito"].oil is True


def test_search_finds_entries_containing_every_word(ft):
    ids = [e.id for e in ft.search("pollo")]
    assert ids[0] == "pechuga-pollo-plancha"
    assert [e.id for e in ft.search("yogur gri")] == ["yogur-griego"]
    assert ft.search("x") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lomo a la brasa", ("lomo", "plancha")),
        ("pechuga de pollo a la plancha", ("pechuga pollo", "plancha")),
        ("huevos revueltos", ("huevo", "salteado")),
        ("brócoli al vapor", ("brocoli", "cocido")),
        ("patatas hervidas", ("patata", "cocido")),
        ("pollo asado", ("pollo", "horno")),
        ("filete empanado", ("filete", "rebozado")),
        ("calamares a la romana", ("calamar", "rebozado")),
        ("ternera guisada", ("ternera", "guisado")),
        ("salmón crudo", ("salmon", "crudo")),
        ("pan", ("pan", None)),
    ],
)
def test_prep_from_words(text, expected):
    assert prep_from_words(text) == expected


def test_entries_with_density_are_liquids(ft):
    assert ft.entries["aceite-oliva"].liquid is True
    assert ft.entries["arroz-blanco-cocido"].liquid is False
