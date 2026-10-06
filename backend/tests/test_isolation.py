"""Un usuario jamás puede leer ni modificar datos de otro, por ningún endpoint."""

import json

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient
from test_access import call, registered_routes

from app.ai import AiClient
from app.config import get_settings
from app.deps import get_ai_client
from app.main import app

MARK = "MARCADORDEANA"
PROFILE = dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento")
AI_MEAL = {
    "name": f"Lentejas {MARK}",
    "items": [
        {
            "name": f"lentejas {MARK.lower()}",
            "qty": 1,
            "unit": "plato",
            "grams": 330,
            "kcal100": 116,
            "protein100": 9,
            "carbs100": 20,
            "fat100": 0.4,
        }
    ],
    "confidence": 0.8,
    "assumptions": [],
    "clarification": None,
}
JPEG = b"\xff\xd8\xff\xe0" + b"1" * 1500


def reply(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(AI_MEAL)}}], "usage": {}})


@pytest.fixture(scope="module")
def ctx():
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(reply)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as client:
        reset_database()
        create_user("ana")
        create_user("beto")
        login(client, "ana")
        client.put("/api/profile", json={**PROFILE, "today": "2026-09-21"})
        draft = client.post("/api/meals/resolve", json={"text": f"plato de lentejas {MARK}"}).json()["draft"]
        meal = client.post(
            "/api/meals",
            json={
                "client_id": "cid-ana-0001",
                "date": "2026-09-21",
                "slot": "comida",
                "name": draft["name"],
                "text": draft["text"],
                "items": draft["items"],
                "source": "ai",
            },
        ).json()
        dish = client.get("/api/dishes").json()["dishes"][0]
        client.patch(f"/api/dishes/{dish['id']}", json={"favorite": True})
        product = client.post(
            "/api/products",
            data={
                "data": json.dumps(
                    {"name": f"Yogur {MARK}", "kcal100": 44, "protein100": 4, "carbs100": 6, "fat100": 0}
                )
            },
            files={"image": ("e.jpg", JPEG, "image/jpeg")},
        ).json()
        client.put("/api/weight", json={"date": "2026-09-22", "kg": 60.5})
        ids = {"meal": meal, "dish": dish, "product": product}
        login(client, "beto")
        client.put("/api/profile", json={**PROFILE, "sex": "hombre", "today": "2026-09-21"})
        yield client, ids
    app.dependency_overrides.clear()


def test_ninguna_lectura_de_beto_contiene_datos_de_ana(ctx):
    client, ids = ctx
    login(client, "beto")
    params = {
        "date": "2026-09-21",
        "client_id": ids["meal"]["client_id"],
        "dish_id": str(ids["dish"]["id"]),
        "product_id": str(ids["product"]["id"]),
    }
    checked = 0
    for path, methods in registered_routes():
        if "GET" not in methods or not path.startswith("/api") or path.startswith("/api/admin"):
            continue
        url = path
        for name, value in params.items():
            url = url.replace("{" + name + "}", value)
        query = "?date=2026-09-21&start=2026-09-01&end=2026-09-30"
        response = client.get(url + query)
        assert MARK.lower() not in response.text.lower(), url
        assert response.status_code != 500, url
        checked += 1
    assert checked >= 12


def test_beto_no_puede_tocar_nada_de_ana(ctx):
    client, ids = ctx
    login(client, "beto")
    cid, dish_id, product_id = ids["meal"]["client_id"], ids["dish"]["id"], ids["product"]["id"]
    assert client.patch(f"/api/meals/{cid}", json={"servings": 3}).status_code == 404
    assert client.delete(f"/api/meals/{cid}").status_code == 404
    assert client.post(f"/api/meals/{cid}/restore").status_code == 404
    assert client.patch(f"/api/dishes/{dish_id}", json={"name": "robado"}).status_code == 404
    client.delete(f"/api/dishes/{dish_id}")
    assert client.patch(f"/api/products/{product_id}", json={"name": "robado"}).status_code == 404
    assert client.get(f"/api/products/{product_id}/image").status_code == 404
    assert (
        client.put(f"/api/products/{product_id}/image", files={"image": ("x.jpg", JPEG, "image/jpeg")}).status_code
        == 404
    )
    client.delete(f"/api/products/{product_id}")
    client.delete("/api/weight/2026-09-22")
    # Reutilizar el client_id de Ana crea una comida de Beto, no devuelve la de ella.
    mine = client.post(
        "/api/meals",
        json={
            "client_id": cid,
            "date": "2026-09-21",
            "slot": "cena",
            "name": "Tortilla",
            "items": [{"name": "huevo", "grams": 110, "kcal": 157, "protein": 14, "carbs": 1, "fat": 10}],
            "source": "manual",
        },
    ).json()
    assert mine["name"] == "Tortilla" and mine["id"] != ids["meal"]["id"]
    assert client.post("/api/data/delete", json={"password": "contraseña-larga"}).json() == {"ok": True}

    # Todo lo de Ana sigue intacto.
    login(client, "ana")
    meals = client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"]
    assert [m["name"] for m in meals] == [f"Lentejas {MARK}"] and meals[0]["servings"] == 1
    dishes = client.get("/api/dishes").json()["dishes"]
    assert dishes[0]["id"] == dish_id and dishes[0]["favorite"] is True
    assert client.get(f"/api/products/{product_id}/image").content == JPEG
    assert client.get("/api/products").json()["products"][0]["name"] == f"Yogur {MARK}"
    assert [e["date"] for e in client.get("/api/weight").json()["entries"]] == ["2026-09-21", "2026-09-22"]
    assert client.get("/api/bootstrap").json()["profile"]["sex"] == "mujer"


def test_lo_que_beto_dice_se_resuelve_solo_con_su_historial(ctx):
    client, _ = ctx
    login(client, "beto")
    # El plato de Ana está en el historial de Ana, no en el de Beto: a él le toca la IA (o su propia caché).
    r = client.post("/api/meals/resolve", json={"text": f"plato de lentejas {MARK}"}).json()
    assert r["status"] == "ai"


def test_cada_uno_cuenta_su_propio_uso_de_ia(ctx):
    client, _ = ctx
    login(client, "ana")
    ana = client.get("/api/stats").json()["ai"]
    login(client, "beto")
    beto = client.get("/api/stats").json()["ai"]
    assert ana["used_today"] == 1 and beto["used_today"] == 1
    assert client.get("/api/export/json").json()["meals"] == []
    assert call(client, "GET", "/api/export/meals.csv").text.count("\n") == 1
