"""Códigos de barras con Open Food Facts simulado: nunca se llama al servicio real."""

import json

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.barcode import USER_AGENT, normalize_code, to_draft
from app.main import app
from app.routers.products import barcode_limit, get_barcode_http

CODE = "8410000123456"
MISSING = "8410000999990"
YOGUR = {
    "code": CODE,
    "product_name_es": "Yogur natural",
    "brands": "Marca Blanca,Otra",
    "quantity": "4 x 125 g",
    "serving_size": "1 yogur (125 g)",
    "serving_quantity": "125",
    "nutriments": {
        "energy-kcal_100g": 61,
        "proteins_100g": 3.5,
        "carbohydrates_100g": 4.7,
        "fat_100g": 3.3,
        "sugars_100g": 4.7,
        "salt_100g": 0.13,
    },
}


class FakeOff:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectTimeout("sin respuesta")
        if CODE in request.url.path:
            return httpx.Response(200, json={"status": 1, "product": YOGUR})
        return httpx.Response(404, json={"status": 0, "status_verbose": "product not found"})


@pytest.fixture()
def off():
    return FakeOff()


@pytest.fixture()
def client(off):
    app.dependency_overrides[get_barcode_http] = lambda: httpx.Client(transport=httpx.MockTransport(off.handler))
    with TestClient(app) as c:
        reset_database()
        barcode_limit._events.clear()
        create_user("ana")
        create_user("beto")
        login(c, "ana")
        yield c
    app.dependency_overrides.clear()


def test_normalizar_codigos():
    assert normalize_code(" 8410000123456 ") == CODE
    assert normalize_code("8410000123457") is None  # dígito de control mal
    assert normalize_code("036000291452") == "0036000291452"  # UPC-A -> EAN-13
    assert normalize_code("abc") is None and normalize_code("12345") is None
    assert normalize_code("96385074") == "96385074"


def test_de_open_food_facts_al_borrador():
    draft = to_draft(YOGUR, CODE)
    assert draft["name"] == "Yogur natural (Marca Blanca)" and draft["alias"] == "yogur natural"
    assert (draft["kcal100"], draft["protein100"], draft["carbs100"], draft["fat100"]) == (61, 3.5, 4.7, 3.3)
    assert draft["unit_label"] == "yogur" and draft["unit_grams"] == 125 and draft["basis"] == "g"
    assert draft["missing"] == [] and draft["barcode"] == CODE
    assert "Open Food Facts" in draft["warnings"][0]


def test_datos_incompletos_o_imposibles():
    bebida = {
        "product_name": "Refresco",
        "quantity": "330 ml",
        "nutriments": {"energy_100g": 180, "carbohydrates_100g": 10.6},
    }
    draft = to_draft(bebida, CODE)
    assert draft["basis"] == "ml" and draft["kcal100"] == 43  # de los kJ
    assert set(draft["missing"]) == {"protein100", "fat100"}
    assert any("Faltan datos" in w for w in draft["warnings"])
    raro = to_draft({"nutriments": {"energy-kcal_100g": 4000, "proteins_100g": 80, "fat_100g": 60}}, CODE)
    assert raro["kcal100"] is None and raro["protein100"] is None and raro["name"] == ""


def test_buscar_encontrado_y_cache(client, off):
    r = client.get(f"/api/products/barcode/{CODE}").json()
    assert r["status"] == "found" and r["draft"]["kcal100"] == 61 and r["code"] == CODE
    request = off.requests[0]
    assert request.headers["user-agent"] == USER_AGENT
    assert "fields=" in str(request.url)
    # La segunda vez sale de la caché local: Open Food Facts no se vuelve a consultar.
    client.get(f"/api/products/barcode/{CODE}")
    assert len(off.requests) == 1


def test_no_encontrado_tambien_se_recuerda(client, off):
    assert client.get(f"/api/products/barcode/{MISSING}").json() == {"status": "not_found", "code": MISSING}
    client.get(f"/api/products/barcode/{MISSING}")
    assert len(off.requests) == 1


def test_sin_respuesta_de_open_food_facts(client, off):
    off.down = True
    assert client.get(f"/api/products/barcode/{CODE}").json() == {"status": "unavailable", "code": CODE}


def test_codigo_invalido(client):
    assert client.get("/api/products/barcode/8410000123457").status_code == 422


def test_guardar_con_codigo_y_volver_a_escanearlo(client, off):
    draft = client.get(f"/api/products/barcode/{CODE}").json()["draft"]
    body = {
        k: draft[k]
        for k in (
            "name",
            "alias",
            "basis",
            "kcal100",
            "protein100",
            "carbs100",
            "fat100",
            "unit_label",
            "unit_grams",
            "barcode",
        )
    }
    saved = client.post("/api/products", data={"data": json.dumps(body)})
    assert saved.status_code == 201 and saved.json()["barcode"] == CODE
    again = client.get(f"/api/products/barcode/{CODE}").json()
    assert again["status"] == "saved" and again["product"]["id"] == saved.json()["id"]
    assert client.post("/api/products", data={"data": json.dumps(body)}).status_code == 409
    # Otra persona con el mismo código no ve el producto de Ana: a ella le sale de Open Food Facts.
    login(client, "beto")
    assert client.get(f"/api/products/barcode/{CODE}").json()["status"] == "found"
    assert client.post("/api/products", data={"data": json.dumps(body)}).status_code == 201


def test_limite_diario_de_consultas(client, off):
    barcode_limit.limit = 1
    try:
        assert client.get(f"/api/products/barcode/{MISSING}").status_code == 200
        assert client.get("/api/products/barcode/96385074").status_code == 429
        # Lo que ya está en caché no cuenta.
        assert client.get(f"/api/products/barcode/{MISSING}").status_code == 200
    finally:
        barcode_limit.limit = 150
