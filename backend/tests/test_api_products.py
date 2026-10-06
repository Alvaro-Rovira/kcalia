"""Productos de etiqueta: leer la foto, guardar, y que «dos yogures ligeros» multiplique lo guardado."""

import json

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.ai import AiClient
from app.config import get_settings
from app.deps import get_ai_client
from app.main import app

PROFILE = dict(
    sex="hombre", age=30, height_cm=180, weight_kg=80, activity="moderado", goal="mantenimiento", today="2026-09-21"
)
LABEL = {
    "is_label": True,
    "name": "Yogur desnatado ligero sabor limón",
    "short_name": "yogur ligero",
    "basis": "g",
    "kcal100": 44,
    "energy_kj100": 187,
    "protein100": 4.1,
    "carbs100": 6.5,
    "fat100": 0.1,
    "fiber100": None,
    "sugars100": 6.2,
    "salt100": 0.12,
    "serving_g": 125,
    "serving_label": "yogur",
    "per_serving": None,
    "confidence": 0.93,
    "notes": [],
}
MEAL = {
    "name": "Manzana",
    "confidence": 0.8,
    "assumptions": ["Manzana mediana de 150 g"],
    "clarification": None,
    "items": [
        {
            "name": "manzana",
            "qty": 1,
            "unit": "pieza",
            "grams": 150,
            "kcal100": 52,
            "protein100": 0.3,
            "carbs100": 14,
            "fat100": 0.2,
        }
    ],
}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000


class FakeAi:
    def __init__(self):
        self.requests: list[dict] = []
        self.replies: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        payload = self.replies.pop(0)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 1500, "completion_tokens": 150},
            },
        )


@pytest.fixture(scope="module")
def fake():
    return FakeAi()


@pytest.fixture(scope="module")
def client(fake):
    settings = get_settings()
    previous_limit = settings.ai_daily_limit
    settings.ai_daily_limit = 200  # el tope de 5 de la configuración de pruebas es para el test del límite
    ai = AiClient(settings, http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as c:
        reset_database()
        create_user("productos")
        login(c, "productos")
        c.put("/api/profile", json=PROFILE)
        yield c
    app.dependency_overrides.clear()
    settings.ai_daily_limit = previous_limit


def scan(client, fake, label):
    fake.replies.append(label)
    return client.post("/api/products/scan", files={"image": ("etiqueta.jpg", JPEG, "image/jpeg")}).json()


def save(client, draft, **extra):
    body = {
        k: draft[k]
        for k in ("name", "alias", "basis", "kcal100", "protein100", "carbs100", "fat100", "unit_label", "unit_grams")
    }
    return client.post(
        "/api/products",
        data={"data": json.dumps({**body, **extra})},
        files={"image": ("etiqueta.jpg", JPEG, "image/jpeg")},
    )


def test_requiere_sesion():
    with TestClient(app) as anonimo:
        assert anonimo.get("/api/products").status_code == 401
        assert anonimo.post("/api/products/scan", files={"image": ("a.jpg", JPEG, "image/jpeg")}).status_code == 401


def test_leer_etiqueta_devuelve_un_borrador_para_revisar(client, fake):
    result = scan(client, fake, LABEL)
    draft = result["draft"]
    assert result["status"] == "ok"
    assert (draft["name"], draft["alias"], draft["basis"]) == (
        "Yogur desnatado ligero sabor limón",
        "yogur ligero",
        "g",
    )
    assert (draft["kcal100"], draft["protein100"], draft["carbs100"], draft["fat100"]) == (44, 4.1, 6.5, 0.1)
    assert (draft["unit_label"], draft["unit_grams"]) == ("yogur", 125) and draft["missing"] == []
    # La foto va al modelo de visión en base64, con el prompt de etiquetas.
    sent = fake.requests[-1]
    assert "etiquetas nutricionales" in sent["messages"][0]["content"]
    assert sent["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # Nada se guarda hasta que el usuario lo confirme.
    assert client.get("/api/products").json()["products"] == []


def test_si_no_es_una_etiqueta_lo_dice(client, fake):
    result = scan(client, fake, {"is_label": False, "name": "", "confidence": 0.9})
    assert result["status"] == "clarify" and "tabla de información nutricional" in result["question"]


def test_solo_kj_y_solo_por_porcion_se_convierten_con_aviso(client, fake):
    kj = scan(client, fake, {**LABEL, "kcal100": None, "energy_kj100": 837})["draft"]
    assert kj["kcal100"] == 200 and any("kJ" in w for w in kj["warnings"])
    porcion = scan(
        client,
        fake,
        {
            **LABEL,
            "kcal100": None,
            "protein100": None,
            "carbs100": None,
            "fat100": None,
            "energy_kj100": None,
            "serving_g": 30,
            "per_serving": {"kcal": 120, "protein": 3, "carbs": 18, "fat": 4},
        },
    )["draft"]
    assert (porcion["kcal100"], porcion["protein100"], porcion["carbs100"], porcion["fat100"]) == (400, 10, 60, 13.33)
    assert any("por porción" in w for w in porcion["warnings"])


def test_cifras_que_no_cuadran_avisan_y_bajan_la_confianza(client, fake):
    draft = scan(client, fake, {**LABEL, "kcal100": 187})["draft"]  # los kJ copiados como kcal
    assert any("no cuadran" in w for w in draft["warnings"]) and draft["confidence"] <= 0.55


def test_cifras_imposibles_se_piden_corregir_al_modelo(client, fake):
    before = len(fake.requests)
    fake.replies += [{**LABEL, "kcal100": 3200}, LABEL]  # la segunda es la respuesta corregida
    result = client.post("/api/products/scan", files={"image": ("e.jpg", JPEG, "image/jpeg")}).json()
    assert result["status"] == "ok" and result["draft"]["kcal100"] == 44
    assert len(fake.requests) == before + 2
    assert "no cumple el esquema" in fake.requests[-1]["messages"][-1]["content"]


def test_guardar_producto_con_su_foto(client, fake):
    draft = scan(client, fake, LABEL)["draft"]
    created = save(client, draft)
    assert created.status_code == 201
    product = created.json()
    assert product["has_image"] is True and product["alias"] == "yogur ligero" and product["use_count"] == 0
    image = client.get(f"/api/products/{product['id']}/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg" and image.content == JPEG
    assert "private" in image.headers["cache-control"]
    assert [p["id"] for p in client.get("/api/products").json()["products"]] == [product["id"]]
    assert client.get("/api/bootstrap").json()["products"][0]["name"] == product["name"]


def test_producto_con_cifras_imposibles_se_rechaza(client):
    body = {"name": "Raro", "kcal100": 100, "protein100": 60, "carbs100": 40, "fat100": 30}
    response = client.post("/api/products", data={"data": json.dumps(body)})
    assert response.status_code == 422 and "cifras" in response.json()["detail"]


def test_dos_yogures_ligeros_multiplican_la_etiqueta_sin_ia(client, fake):
    calls = len(fake.requests)
    result = client.post("/api/meals/resolve", json={"text": "dos yogures ligeros"}).json()
    draft = result["draft"]
    assert result["status"] == "product" and draft["source"] == "product" and len(fake.requests) == calls
    assert draft["kcal"] == 110 and draft["protein"] == 10.3
    assert draft["items"][0]["grams"] == 250 and draft["items"][0]["product_id"] is not None
    assert "etiqueta que guardaste" in draft["assumptions"][0]


def test_si_solo_parte_del_texto_es_un_producto_la_ia_recibe_solo_el_resto(client, fake):
    fake.replies.append(MEAL)
    calls = len(fake.requests)
    result = client.post("/api/meals/resolve", json={"text": "dos yogures ligeros con una manzana"}).json()
    assert result["status"] == "ai" and len(fake.requests) == calls + 1
    prompt = fake.requests[-1]["messages"][1]["content"]
    assert "manzana" in prompt and "yogur" not in prompt
    draft = result["draft"]
    assert [i["name"] for i in draft["items"]] == ["Yogur desnatado ligero sabor limón", "manzana"]
    assert draft["items"][0]["product_id"] is not None and draft["items"][1].get("product_id") is None
    assert draft["kcal"] == pytest.approx(110 + 78, abs=0.2)


def test_guardar_comida_de_producto_cuenta_uso_y_ahorro_sin_ensuciar_el_historial(client):
    draft = client.post("/api/meals/resolve", json={"text": "un yogur ligero"}).json()["draft"]
    body = {
        "client_id": "producto-0001",
        "date": "2026-09-21",
        "slot": "merienda",
        "name": draft["name"],
        "text": "un yogur ligero",
        "items": draft["items"],
        "source": "product",
        "dish_id": None,
    }
    assert client.post("/api/meals", json=body).status_code == 201
    assert client.get("/api/stats").json()["ai"]["saved"]["saved_product"] == 1
    assert client.get("/api/products").json()["products"][0]["use_count"] == 1
    # Los productos son la memoria: no se duplican como comida del historial.
    assert client.get("/api/bootstrap").json()["dishes"] == []
    day = client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"][0]
    assert day["kcal"] == 55 and day["items"][0]["product_id"] is not None


def test_editar_el_producto_cambia_lo_que_sale_despues(client):
    product = client.get("/api/products").json()["products"][0]
    updated = client.patch(f"/api/products/{product['id']}", json={"kcal100": 50, "unit_grams": 100}).json()
    assert updated["kcal100"] == 50 and updated["unit_grams"] == 100
    assert client.post("/api/meals/resolve", json={"text": "dos yogures ligeros"}).json()["draft"]["kcal"] == 100
    assert client.patch(f"/api/products/{product['id']}", json={"protein100": 90, "carbs100": 20}).status_code == 422


def test_borrar_producto_y_su_foto(client):
    product = client.get("/api/products").json()["products"][0]
    assert client.delete(f"/api/products/{product['id']}").json() == {"ok": True}
    assert client.get(f"/api/products/{product['id']}/image").status_code == 404
    assert client.patch(f"/api/products/{product['id']}", json={"name": "x"}).status_code == 404
    assert client.get("/api/products").json()["products"] == []
    # Sin el producto, vuelve a ser una comida normal para la IA.


def test_la_lectura_de_etiquetas_cuenta_para_el_cupo_diario(client, fake):
    used = client.get("/api/stats").json()["ai"]["used_today"]
    assert used >= 6  # las lecturas anteriores (y la corrección) gastaron cupo
    from app import services, tenancy
    from app.db import SessionLocal

    with SessionLocal() as db, tenancy.unscoped(db):
        assert services.ai_calls_today(db, __import__("datetime").date.today(), ("vision",)) >= 5


def test_borrar_la_cuenta_borra_productos_y_fotos(client, fake):
    draft = scan(client, fake, LABEL)["draft"]
    product = save(client, draft).json()
    assert client.post("/api/account/delete", json={"password": "contraseña-larga"}).json() == {"ok": True}
    create_user("otra")
    login(client, "otra")
    assert client.get("/api/products").json()["products"] == []
    assert client.get(f"/api/products/{product['id']}/image").status_code == 404
