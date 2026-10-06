"""Registro diario: ingredientes a mano, copiar comidas y días, y orden por momento del día."""

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.main import app

EGG = {
    "name": "huevo",
    "qty": 2,
    "unit": "pieza",
    "grams": 110,
    "kcal": 157.3,
    "protein": 13.9,
    "carbs": 0.8,
    "fat": 10.5,
}
MANUAL = {
    "name": "queso fresco batido",
    "qty": 250,
    "unit": "g",
    "grams": 250,
    "kcal": 115,
    "protein": 20,
    "carbs": 8.8,
    "fat": 0.5,
    "manual": True,
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        reset_database()
        create_user("ana")
        login(c, "ana")
        c.put(
            "/api/profile",
            json=dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento"),
        )
        yield c


def meal(client, cid, items, **extra):
    body = {
        "client_id": cid,
        "date": "2026-10-01",
        "slot": "desayuno",
        "name": "Desayuno",
        "items": items,
        "source": "manual",
        **extra,
    }
    response = client.post("/api/meals", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_ingrediente_a_mano_se_aprende_en_la_cache(client):
    saved = meal(client, "cid-manual-1", [EGG, MANUAL])
    assert saved["kcal"] == pytest.approx(272.3)
    foods = {f["name"]: f for f in client.get("/api/foods").json()["foods"]}
    assert foods["queso fresco batido"]["kcal100"] == 46 and foods["queso fresco batido"]["protein100"] == 8
    assert "huevo" not in foods  # sin marcar como manual, una comida a mano no enseña nada
    # Ya en el arranque, para autocompletar sin red.
    assert any(f["name"] == "queso fresco batido" for f in client.get("/api/bootstrap").json()["foods"])
    # Y la caché resuelve «200 g de queso fresco batido» sin IA.
    r = client.post("/api/meals/resolve", json={"text": "200 g de queso fresco batido"}).json()
    assert r["status"] == "cache" and r["draft"]["kcal"] == 92


def test_editar_una_comida_anadiendo_un_ingrediente_tambien_aprende(client):
    meal(client, "cid-manual-2", [EGG])
    extra = {
        **MANUAL,
        "name": "pan de centeno",
        "grams": 60,
        "qty": 60,
        "kcal": 150,
        "protein": 5,
        "carbs": 28,
        "fat": 1.2,
    }
    patched = client.patch("/api/meals/cid-manual-2", json={"items": [EGG, extra]}).json()
    assert patched["kcal"] == pytest.approx(307.3)
    assert any(f["name"] == "pan de centeno" for f in client.get("/api/foods").json()["foods"])


def test_lo_de_un_producto_no_se_aprende_como_ingrediente(client):
    meal(client, "cid-manual-3", [{**MANUAL, "name": "yogur de marca", "product_id": 999}])
    assert not any(f["name"] == "yogur de marca" for f in client.get("/api/foods").json()["foods"])


def test_uso_por_momento_del_dia(client):
    from datetime import date

    today = date.today().isoformat()
    cafe = {
        "name": "café con leche",
        "qty": 1,
        "unit": "taza",
        "grams": 200,
        "kcal": 92,
        "protein": 6.6,
        "carbs": 9.6,
        "fat": 3.2,
    }
    first = meal(client, "cid-slot-1", [cafe], name="Café con leche", text="café con leche", date=today, source="ai")
    for n, slot in enumerate(("desayuno", "desayuno", "merienda"), start=2):
        meal(
            client,
            f"cid-slot-{n}",
            [cafe],
            name="Café con leche",
            text="café con leche",
            date=today,
            slot=slot,
            source="recent",
            dish_id=first["dish_id"],
        )
    dish = next(d for d in client.get("/api/dishes").json()["dishes"] if d["id"] == first["dish_id"])
    assert dish["slot_counts"] == {"desayuno": 3, "merienda": 1}
    boot = next(d for d in client.get("/api/bootstrap").json()["dishes"] if d["id"] == first["dish_id"])
    assert boot["slot_counts"] == dish["slot_counts"]
