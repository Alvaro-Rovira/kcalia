import pytest

from app.matching import FoodInfo, learn_foods, resolve_from_foods, totals

AI_ITEMS = [
    {
        "name": "huevo",
        "qty": 2,
        "unit": "pieza",
        "grams": 110,
        "kcal": 157.3,
        "protein": 13.9,
        "carbs": 0.8,
        "fat": 10.5,
    },
    {
        "name": "pan integral",
        "qty": 1,
        "unit": "rebanada",
        "grams": 40,
        "kcal": 100,
        "protein": 4,
        "carbs": 16.8,
        "fat": 1.4,
    },
    {"name": "aceite de oliva", "qty": 10, "unit": "g", "grams": 10, "kcal": 88.4, "protein": 0, "carbs": 0, "fat": 10},
]
TEXT = "dos huevos, una tostada de pan integral y 10 g de aceite de oliva"


def cache_from(text, items):
    store = {}
    for u in learn_foods(text, items):
        store[u.key] = FoodInfo(u.name, u.kcal100, u.protein100, u.carbs100, u.fat100, u.unit_grams)
    return store


def test_aprende_macros_por_100_g():
    cache = cache_from(TEXT, AI_ITEMS)
    assert cache["huevo"].kcal100 == pytest.approx(143, abs=0.1)
    assert cache["aceite oliva"].fat100 == pytest.approx(100)


def test_aprende_gramos_por_unidad_y_alias_del_usuario():
    cache = cache_from(TEXT, AI_ITEMS)
    assert cache["huevo"].unit_grams["pieza"] == 55
    # La IA lo llamó "pan integral"; el usuario, "tostada de pan integral".
    assert cache["tostada pan integral"].unit_grams["pieza"] == 40
    assert cache["pan integral"].unit_grams["rebanada"] == 40


def test_resuelve_sin_ia_con_otras_cantidades():
    cache = cache_from(TEXT, AI_ITEMS)
    items = resolve_from_foods("3 huevos y 2 tostadas de pan integral", cache.get)
    assert items is not None
    assert [i["grams"] for i in items] == [165, 80]
    assert totals(items)["kcal"] == pytest.approx(143 * 1.65 + 250 * 0.8, abs=1)


def test_resuelve_gramos_explicitos():
    cache = cache_from(TEXT, AI_ITEMS)
    items = resolve_from_foods("25 g de aceite de oliva", cache.get)
    assert items[0]["kcal"] == pytest.approx(221, abs=0.5)


def test_todo_o_nada_si_falta_un_ingrediente():
    cache = cache_from(TEXT, AI_ITEMS)
    assert resolve_from_foods("2 huevos y un plátano", cache.get) is None


def test_no_resuelve_unidad_desconocida():
    cache = cache_from(TEXT, AI_ITEMS)
    # Se sabe cuánto pesa una rebanada de pan integral, no un bol.
    assert resolve_from_foods("un bol de pan integral", cache.get) is None


def test_liquidos_necesitan_densidad_aprendida():
    items = [
        {
            "name": "leche entera",
            "qty": 200,
            "unit": "ml",
            "grams": 206,
            "kcal": 131.8,
            "protein": 6.6,
            "carbs": 9.7,
            "fat": 7.4,
        }
    ]
    cache = cache_from("200 ml de leche entera", items)
    assert cache["leche entera"].unit_grams["ml"] == pytest.approx(1.03)
    resolved = resolve_from_foods("medio litro de leche entera", cache.get)
    assert resolved[0]["grams"] == pytest.approx(515)
    assert resolve_from_foods("medio litro de aceite de oliva", cache_from(TEXT, AI_ITEMS).get) is None


def test_sin_alias_si_no_hay_correspondencia_uno_a_uno():
    # Un solo trozo de texto y dos ingredientes: no se puede saber cuál es cuál.
    items = [
        {"name": "café", "qty": 60, "unit": "ml", "grams": 60, "kcal": 1, "protein": 0.1, "carbs": 0, "fat": 0},
        {
            "name": "leche entera",
            "qty": 140,
            "unit": "ml",
            "grams": 144,
            "kcal": 92,
            "protein": 4.6,
            "carbs": 6.8,
            "fat": 5.2,
        },
    ]
    cache = cache_from("café con leche", items)
    assert set(cache) == {"cafe", "leche entera"}


def test_sin_alias_si_los_nombres_no_se_parecen():
    items = [
        {
            "name": "merluza",
            "qty": 1,
            "unit": "racion",
            "grams": 160,
            "kcal": 144,
            "protein": 28.8,
            "carbs": 0,
            "fat": 2.9,
        }
    ]
    assert set(cache_from("lo de ayer", items)) == {"merluza"}


def test_totals_con_raciones():
    assert totals(AI_ITEMS, 2)["kcal"] == pytest.approx((157.3 + 100 + 88.4) * 2, abs=0.1)
    assert totals([])["kcal"] == 0
