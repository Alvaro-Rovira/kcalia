import json
from pathlib import Path

import pytest

from app.products import ProductInfo, item_for, match_product, resolve_text, round1, tokens

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "product_cases.json").read_text())
PRODUCTS = [
    ProductInfo(
        p["id"],
        p["name"],
        p["alias"],
        p["basis"],
        p["kcal100"],
        p["protein100"],
        p["carbs100"],
        p["fat100"],
        p["unit_label"],
        p["unit_grams"],
    )
    for p in FIXTURE["products"]
]


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=[c["text"] for c in FIXTURE["cases"]])
def test_resolver_texto_con_productos_guardados(case):
    result = resolve_text(case["text"], PRODUCTS)
    got = [{k: item[k] for k in ("product_id", "grams", "kcal", "protein", "carbs", "fat")} for item in result.items]
    assert got == case["items"]
    assert result.rest == case["rest"]


def test_sin_productos_todo_es_resto():
    result = resolve_text("dos yogures ligeros", [])
    assert result.items == [] and result.rest == ["dos yogures ligeros"]


def test_tokens_ignoran_articulos_numeros_unidades_y_con():
    assert tokens("Dos YOGURES ligeros con 200 g") == tokens("yogur ligero")
    assert tokens("un vaso de leche") == {"leche"}


def test_gana_el_nombre_exacto_sobre_el_parcial():
    assert match_product(tokens("yogur ligero"), PRODUCTS).id == 1
    assert match_product(tokens("yogur griego"), PRODUCTS).id == 5


def test_un_nombre_demasiado_generico_no_se_empareja():
    assert match_product(tokens("yogur"), PRODUCTS) is None


def test_al_empatar_gana_el_primero_de_la_lista_ordenada_por_uso():
    a = ProductInfo(10, "Barrita choco", "barrita", "g", 400, 10, 50, 15, "", None)
    b = ProductInfo(11, "Barrita fresa", "barrita", "g", 380, 9, 55, 12, "", None)
    assert match_product(tokens("barrita"), [b, a]).id == 11
    assert match_product(tokens("barrita"), [a, b]).id == 10


def test_ml_y_gramos_valen_igual_para_las_cuentas():
    leche = PRODUCTS[1]
    assert item_for(leche, 250, "ml")["grams"] == 250
    assert item_for(leche, 1, "l")["kcal"] == 460
    assert item_for(leche, 1, "cl")["grams"] == 10


def test_unidad_desconocida_no_se_adivina():
    yogur = PRODUCTS[0]
    assert item_for(yogur, 2, "cda") is None
    assert item_for(PRODUCTS[5], 2, None) is None  # sin peso por unidad guardado
    assert item_for(yogur, 0, None) is None
    assert item_for(yogur, 9999, "g") is None


def test_la_unidad_propia_del_producto_vale():
    assert item_for(PRODUCTS[3], 2, "tarrina") is None  # "tarrina" no es una unidad conocida: se guarda como genérica
    assert item_for(PRODUCTS[3], 2, None)["grams"] == 500


def test_redondeo_como_javascript():
    assert [round1(x) for x in (0.25, 0.35, 2.45, 143.75, 1.05)] == [0.3, 0.4, 2.5, 143.8, 1.1]
