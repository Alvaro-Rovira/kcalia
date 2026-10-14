import pytest

from app.foodtable import table
from app.refine import OIL_NAME, eu_kcal, mentions_fat, official_share, refine

T = table()


def ai_item(
    name, grams, *, qty=1, unit="g", food=None, prep=None, kcal=100.0, protein=5.0, carbs=10.0, fat=3.0, **extra
):
    item = {"name": name, "qty": qty, "unit": unit, "grams": grams, "kcal": kcal, "protein": protein, "carbs": carbs}
    item.update(fat=fat, **extra)
    if food is not None:
        item["food"] = food
    if prep is not None:
        item["prep"] = prep
    return item


def expected(entry_id, grams):
    e = T.entries[entry_id]
    return {k: round(getattr(e, f"{k}100") * grams / 100, 1) for k in ("kcal", "protein", "carbs", "fat")}


def by_name(items, name):
    return next(i for i in items if i["name"] == name)


def test_eu_kcal_uses_the_european_factors():
    assert eu_kcal(10, 20, 5) == 10 * 4 + 20 * 4 + 5 * 9
    assert eu_kcal(0, 0, 0, fiber=10, alcohol=10) == 20 + 70


def test_count_units_take_the_edible_weight_from_the_table():
    items, _ = refine([ai_item("huevo cocido", 110, qty=2, unit="pieza", food="huevo", prep="cocido")], text="2 huevos")
    egg = items[0]
    assert egg["grams"] == 100
    assert {k: egg[k] for k in ("kcal", "protein", "carbs", "fat")} == expected("huevo-cocido", 100)
    assert egg["source"] == "tabla" and egg["ref"] == "ciqual:22010"


def test_millilitres_use_the_density():
    items, _ = refine(
        [ai_item("aceite de oliva", 20, qty=20, unit="ml", food="aceite de oliva")], text="20 ml de aceite"
    )
    assert items[0]["grams"] == pytest.approx(18.3)


def test_a_glass_of_milk_is_200_ml_times_its_density():
    items, _ = refine(
        [ai_item("leche semidesnatada", 200, unit="vaso", food="leche semidesnatada")], text="un vaso de leche"
    )
    assert items[0]["grams"] == pytest.approx(206)


def test_photo_keeps_the_weight_estimated_by_the_model():
    items, _ = refine([ai_item("huevo cocido", 110, qty=2, unit="pieza", food="huevo", prep="cocido")], photo=True)
    assert items[0]["grams"] == 110
    assert items[0]["kcal"] == expected("huevo-cocido", 110)["kcal"]


def test_unknown_food_keeps_the_model_macros_and_recomputes_energy():
    item = ai_item("cachopo", 300, food="cachopo", kcal=500, protein=40, carbs=30, fat=30, fiber=2)
    items, _ = refine([item], text="un cachopo")
    assert items[0]["source"] == "ia"
    assert items[0]["kcal"] == eu_kcal(40, 30, 30, fiber=2)
    assert "ref" not in items[0]


def test_grilled_food_without_fat_mentioned_gets_cooking_oil():
    items, notes = refine(
        [ai_item("pechuga de pollo a la plancha", 150, food="pechuga de pollo", prep="plancha")],
        text="150 g de pechuga a la plancha",
    )
    oil = by_name(items, OIL_NAME)
    assert oil["grams"] == 3 and oil["source"] == "tabla"
    assert oil["kcal"] == expected("aceite-oliva", 3)["kcal"]
    assert any("aceite" in note.lower() for note in notes)


def test_cooking_oil_is_clamped_per_ingredient_and_merged():
    items, _ = refine(
        [
            ai_item("pechuga de pollo a la plancha", 150, food="pechuga de pollo", prep="plancha"),
            ai_item("lomo de cerdo a la plancha", 600, food="lomo de cerdo", prep="plancha"),
        ],
        text="pollo y lomo a la plancha",
    )
    oils = [i for i in items if i["name"] == OIL_NAME]
    assert len(oils) == 1 and oils[0]["grams"] == 3 + 10


def test_fried_entries_already_include_their_fat():
    items, _ = refine(
        [
            ai_item("patatas fritas", 150, food="patata", prep="frito"),
            ai_item("aceite de oliva", 10, food="aceite de oliva"),
        ],
        text="patatas fritas",
    )
    assert [i["name"] for i in items] == ["patatas fritas"]
    assert items[0]["kcal"] == expected("patatas-fritas", 150)["kcal"]


def test_salad_dressing_proposed_by_the_model_is_kept():
    items, _ = refine(
        [ai_item("lechuga", 80, food="lechuga"), ai_item("aceite de oliva (aliño)", 10, food="aceite de oliva")],
        text="una ensalada de lechuga",
    )
    assert by_name(items, "aceite de oliva (aliño)")["kcal"] == expected("aceite-oliva", 10)["kcal"]
    assert OIL_NAME not in [i["name"] for i in items]


@pytest.mark.parametrize(
    "text",
    ["pechuga con AOVE", "pollo con un chorrito", "pollo con aceite de girasol", "pollo con mantequilla",
     "pollo con manteca", "pollo con margarina", "pollo a la plancha sin aceite"],
)  # fmt: skip
def test_any_mention_of_fat_leaves_the_fat_to_the_user(text):
    assert mentions_fat(text)
    items, _ = refine(
        [ai_item("pechuga de pollo a la plancha", 150, food="pechuga de pollo", prep="plancha")], text=text
    )
    assert OIL_NAME not in [i["name"] for i in items]


def test_no_fat_mentioned():
    assert not mentions_fat("tostada con tomate")
    assert not mentions_fat("dos huevos y una manzana")


def test_mentioned_oil_keeps_its_item_with_table_values():
    items, _ = refine(
        [
            ai_item("pechuga de pollo a la plancha", 150, food="pechuga de pollo", prep="plancha"),
            ai_item("aceite de oliva", 10, qty=1, unit="cda", food="aceite de oliva"),
        ],
        text="pechuga a la plancha con una cucharada de aceite",
    )
    oil = by_name(items, "aceite de oliva")
    assert oil["grams"] == 10 and oil["source"] == "tabla"
    assert OIL_NAME not in [i["name"] for i in items]


def test_label_and_manual_items_pass_untouched():
    label = {"name": "yogur ligero", "qty": 2, "unit": "pieza", "grams": 250, "kcal": 90, "protein": 10, "carbs": 9,
             "fat": 0.5, "product_id": 7}  # fmt: skip
    manual = {"name": "cosa", "qty": 50, "unit": "g", "grams": 50, "kcal": 77, "protein": 1, "carbs": 2, "fat": 3,
              "manual": True}  # fmt: skip
    items, _ = refine([label, manual], text="dos yogures ligeros")
    assert items[0] == {**label, "source": "etiqueta"}
    assert items[1] == {**manual, "source": "manual"}


def test_old_items_without_food_or_prep_are_matched_by_name():
    items, _ = refine([ai_item("arroz blanco cocido", 200, food=None)], text="200 g de arroz")
    assert items[0]["source"] == "tabla"
    assert items[0]["kcal"] == expected("arroz-blanco-cocido", 200)["kcal"]


def test_duplicates_are_merged():
    items, _ = refine(
        [ai_item("huevo cocido", 50, unit="pieza", food="huevo", prep="cocido"),
         ai_item("huevo cocido", 50, unit="pieza", food="huevo", prep="cocido")],
        text="huevo",
    )  # fmt: skip
    assert len(items) == 1 and items[0]["grams"] == 100 and items[0]["qty"] == 2


def test_official_share():
    items = [{"kcal": 300, "source": "tabla"}, {"kcal": 100, "source": "ia"}]
    assert official_share(items) == 0.75
    assert official_share([{"kcal": 50}]) == 0
    assert official_share([]) == 0


def test_canned_in_oil_is_not_cooking_fat():
    assert not mentions_fat("pollo a la plancha y una lata de atún en aceite")
    assert not mentions_fat("sardinas en aceite de oliva")


def test_unit_read_differently_by_the_model_keeps_its_weight():
    # «1 pieza» de nueces para la tabla es una nuez (5 g); si la IA pesó 30 g, entendía un puñado.
    items, _ = refine([ai_item("nueces", 30, qty=1, unit="pieza", food="nuez")], text="nueces")
    assert items[0]["grams"] == 30 and items[0]["source"] == "tabla"
    # Diferencias normales (huevo de 55 g frente a 50 g comestibles) sí se corrigen con la tabla.
    items, _ = refine([ai_item("huevo", 55, qty=1, unit="pieza", food="huevo")], text="un huevo")
    assert items[0]["grams"] == 50


def test_revalue_updates_saved_items_keeping_their_weight_and_structure():
    from app.refine import revalue

    old = [
        {"name": "huevo", "qty": 2, "unit": "pieza", "grams": 110, "kcal": 157.3, "protein": 13.9, "carbs": 0.8, "fat": 10.5},
        {"name": "aceite de oliva", "qty": 5, "unit": "g", "grams": 5, "kcal": 44.2, "protein": 0, "carbs": 0, "fat": 5},
        {"name": "cachopo", "qty": 1, "unit": "pieza", "grams": 300, "kcal": 500, "protein": 40, "carbs": 30, "fat": 30},
        {"name": "yogur ligero", "qty": 1, "unit": "pieza", "grams": 125, "kcal": 55, "protein": 5, "carbs": 7, "fat": 0.1,
         "product_id": 4},
    ]  # fmt: skip
    items = revalue(old)
    assert [i["name"] for i in items] == [
        "huevo",
        "aceite de oliva",
        "cachopo",
        "yogur ligero",
    ]  # nada se añade ni quita
    assert [i["grams"] for i in items] == [110, 5, 300, 125]  # los gramos guardados se respetan
    assert items[0]["kcal"] == expected("huevo-cocido", 110)["kcal"] and items[0]["source"] == "tabla"
    assert items[1]["kcal"] == expected("aceite-oliva", 5)["kcal"]
    assert items[2]["kcal"] == eu_kcal(40, 30, 30) and items[2]["source"] == "ia"
    assert items[3]["kcal"] == 55 and items[3]["source"] == "etiqueta"


def test_a_portion_the_model_chose_on_purpose_is_kept():
    # «Un bocadillo»: la IA usa «1 rebanada» grande de 80 g; la rebanada estándar de la tabla (40 g) no la sustituye.
    items, _ = refine([ai_item("pan de barra", 80, qty=1, unit="rebanada", food="pan blanco")], text="un bocadillo")
    assert items[0]["grams"] == 80 and items[0]["source"] == "tabla"
    # Pequeñas imprecisiones sobre tamaños estándar sí las corrige la tabla (manzana de 200 g -> pieza de 150 g).
    items, _ = refine([ai_item("manzana", 200, qty=1, unit="pieza", food="manzana")], text="una manzana")
    assert items[0]["grams"] == 150
