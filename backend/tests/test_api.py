"""Flujo completo de la API con una IA simulada: comprueba que la IA solo se llama cuando toca."""

import json

import httpx
import pytest
from conftest import reset_database
from fastapi.testclient import TestClient

from app.ai import AiClient
from app.config import get_settings
from app.deps import get_ai_client
from app.main import app

AI_MEAL = {
    "name": "Huevos con tostada",
    "items": [
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
    ],
    "confidence": 0.85,
    "assumptions": ["Huevos medianos de 55 g"],
    "clarification": None,
}
PROFILE = dict(
    sex="hombre", age=30, height_cm=180, weight_kg=80, activity="moderado", goal="definicion_ligera", today="2026-09-21"
)


class FakeAi:
    def __init__(self):
        self.calls = 0
        self.replies: list[str] = []
        self.bodies: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.bodies.append(json.loads(request.content))
        content = self.replies.pop(0) if self.replies else json.dumps(AI_MEAL)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 900, "completion_tokens": 120},
            },
        )


@pytest.fixture(scope="module")
def fake_ai():
    return FakeAi()


@pytest.fixture(scope="module")
def client(fake_ai):
    reset_database()
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(fake_ai.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def meal_body(draft, client_id, **extra):
    return {
        "client_id": client_id,
        "date": "2026-09-21",
        "slot": "desayuno",
        "name": draft["name"],
        "text": draft["text"],
        "items": draft["items"],
        "source": draft["source"],
        "dish_id": draft.get("dish_id"),
        **extra,
    }


def test_todo_requiere_sesion(client):
    assert client.get("/api/bootstrap").status_code == 401
    status = client.get("/api/auth/status").json()
    assert status["registered"] is False and status["authenticated"] is False and status["signup"] == "first"


def test_la_primera_cuenta_es_la_del_administrador(client):
    assert client.post("/api/auth/register", json={"username": "alvaro", "password": "corta"}).status_code == 422
    first = client.post("/api/auth/register", json={"username": "alvaro", "password": "contraseña-larga"})
    assert first.status_code == 200 and first.json()["status"] == "approved"
    status = client.get("/api/auth/status").json()
    assert status["is_admin"] is True and status["status"] == "approved" and status["signup"] == "open"
    # Las siguientes solo piden cuenta: quedan pendientes y no inician sesión.
    client.cookies.clear()
    other = client.post("/api/auth/register", json={"username": "otro", "password": "contraseña-larga"})
    assert other.status_code == 200 and other.json()["status"] == "received"
    assert client.get("/api/auth/status").json()["authenticated"] is False
    client.post("/api/auth/login", json={"username": "alvaro", "password": "contraseña-larga"})
    client.post("/api/auth/logout")
    assert client.get("/api/bootstrap").status_code == 401
    assert client.post("/api/auth/login", json={"username": "alvaro", "password": "incorrecta1"}).status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "ALVARO", "password": "contraseña-larga"}).status_code == 200
    )
    assert client.get("/api/auth/status").json()["authenticated"] is True


def test_peticion_desde_otro_origen_rechazada(client):
    r = client.post("/api/auth/logout", headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403


def test_onboarding_calcula_objetivos_y_anota_el_peso(client):
    preview = client.post("/api/plan/preview", json={k: v for k, v in PROFILE.items() if k != "today"}).json()
    saved = client.put("/api/profile", json=PROFILE).json()
    assert saved["targets"]["kcal"] == preview["kcal"] == 2350
    assert saved["targets"]["custom"] is False
    weights = client.get("/api/weight").json()["entries"]
    assert weights == [{"date": "2026-09-21", "kg": 80.0, "avg": 80.0}]


def test_primera_vez_llama_a_la_ia(client, fake_ai):
    r = client.post("/api/meals/resolve", json={"text": "Dos huevos y una tostada de pan integral"}).json()
    assert r["status"] == "ai" and fake_ai.calls == 1
    assert r["draft"]["kcal"] == pytest.approx(257.3)
    body = fake_ai.bodies[-1]
    assert body["model"] == "kimi-k2.6"
    assert body["thinking"] == {"type": "disabled"} and "temperature" not in body
    assert body["response_format"] == {"type": "json_object"}
    created = client.post("/api/meals", json=meal_body(r["draft"], "cid-0000001"))
    assert created.status_code == 201


def test_coincidencia_exacta_no_llama_a_la_ia(client, fake_ai):
    r = client.post("/api/meals/resolve", json={"text": "2 huevos, tostada de pan integral"}).json()
    assert r["status"] == "fuzzy" or r["status"] == "exact"
    r = client.post("/api/meals/resolve", json={"text": "dos huevos y UNA tostada de pan integral!"}).json()
    assert r["status"] == "exact" and fake_ai.calls == 1
    client.post("/api/meals", json=meal_body(r["draft"], "cid-0000002"))


def test_coincidencia_aproximada_pregunta_y_aprende_el_alias(client, fake_ai):
    text = "dos huevos y una tostada de pan intgral"
    r = client.post("/api/meals/resolve", json={"text": text}).json()
    assert r["status"] == "fuzzy" and fake_ai.calls == 1
    candidate = r["candidates"][0]
    assert candidate["score"] >= 0.85
    client.post("/api/meals", json=meal_body(candidate, "cid-0000003"))
    # La próxima vez esa forma de escribirlo ya es exacta.
    assert client.post("/api/meals/resolve", json={"text": text}).json()["status"] == "exact"


def test_cache_de_ingredientes_resuelve_otras_cantidades(client, fake_ai):
    r = client.post("/api/meals/resolve", json={"text": "3 huevos"}).json()
    assert r["status"] == "cache" and fake_ai.calls == 1
    assert r["draft"]["items"][0]["grams"] == 165
    client.post("/api/meals", json=meal_body(r["draft"], "cid-0000004", slot="cena"))


def test_cola_offline_idempotente(client):
    r = client.post("/api/meals/resolve", json={"text": "3 huevos"}).json()
    first = client.post("/api/meals", json=meal_body(r["draft"], "cid-0000005")).json()
    again = client.post("/api/meals", json=meal_body(r["draft"], "cid-0000005")).json()
    assert first["id"] == again["id"]
    assert len(client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"]) == 5


def test_raciones_editar_borrar_y_deshacer(client):
    meals = client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"]
    meal = meals[0]
    doubled = client.patch(f"/api/meals/{meal['client_id']}", json={"servings": 2}).json()
    assert doubled["kcal"] == pytest.approx(meal["kcal"] * 2, abs=0.2)
    client.patch(f"/api/meals/{meal['client_id']}", json={"servings": 1})
    assert client.delete(f"/api/meals/{meal['client_id']}").json() == {"ok": True}
    assert len(client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"]) == 4
    client.post(f"/api/meals/{meal['client_id']}/restore")
    assert len(client.get("/api/meals", params={"date": "2026-09-21"}).json()["meals"]) == 5


def test_json_invalido_reintenta_una_vez(client, fake_ai):
    before = fake_ai.calls
    fake_ai.replies = ["esto no es json", "```json\n" + json.dumps({**AI_MEAL, "name": "Paella"}) + "\n```"]
    r = client.post("/api/meals/resolve", json={"text": "un plato de paella"}).json()
    assert r["status"] == "ai" and r["draft"]["name"] == "Paella"
    assert fake_ai.calls == before + 2
    assert "no cumple el esquema" in fake_ai.bodies[-1]["messages"][-1]["content"]


def test_pide_aclaracion_si_falta_informacion(client, fake_ai):
    fake_ai.replies = [
        json.dumps(
            {
                "name": "",
                "items": [],
                "confidence": 0,
                "assumptions": [],
                "clarification": "¿Qué has comido exactamente?",
            }
        )
    ]
    r = client.post("/api/meals/resolve", json={"text": "lo de siempre"}).json()
    assert r == {"status": "clarify", "question": "¿Qué has comido exactamente?"}


def test_limite_diario_de_ia(client, fake_ai):
    calls = fake_ai.calls
    r = client.post("/api/meals/resolve", json={"text": "una ensalada césar"})
    assert r.status_code == 200  # quinta llamada del día: aún entra
    r = client.post("/api/meals/resolve", json={"text": "un bocadillo de calamares"})
    assert r.status_code == 429 and r.json()["code"] == "limit"
    assert fake_ai.calls == calls + 1
    # El historial sigue funcionando con el límite agotado.
    assert client.post("/api/meals/resolve", json={"text": "3 huevos"}).json()["status"] in ("exact", "cache")


def test_contador_de_ahorro_racha_y_logros(client):
    stats = client.get("/api/stats").json()
    # "3 huevos" salió de la caché la primera vez y del historial la segunda.
    assert stats["ai"]["saved"] == {
        "saved_exact": 2,
        "saved_fuzzy": 1,
        "saved_cache": 1,
        "saved_quick": 0,
        "saved_product": 0,
    }
    assert stats["ai"]["saved_total"] == 4
    assert stats["ai"]["used_today"] == 5 and stats["ai"]["limit"] == 5
    unlocked = {a["key"] for a in stats["achievements"] if a["unlocked_at"]}
    assert {"primera_comida", "primer_peso"} <= unlocked


def test_resumen_semanal_y_dias(client):
    week = client.get("/api/summary/week", params={"start": "2026-09-23"}).json()
    assert week["week_start"] == "2026-09-21"
    assert week["logged_days"] == 1
    days = client.get("/api/days", params={"start": "2026-09-01", "end": "2026-09-30"}).json()["days"]
    assert len(days) == 1 and days[0]["meals"] == 5
    history = client.get("/api/summary/history").json()["summaries"]
    assert [s["week_start"] for s in history] == ["2026-09-21"]


def test_peso_sugiere_recalcular(client):
    r = client.put("/api/weight", json={"date": "2026-09-28", "kg": 78.5}).json()
    assert r["recalc"]["from_kg"] == 80 and r["recalc"]["to_kg"] == 78.5
    assert r["recalc"]["kcal"] < 2350
    targets = client.post("/api/targets/recalculate").json()["targets"]
    assert targets["kcal"] == r["recalc"]["kcal"]
    assert client.get("/api/weight").json()["recalc"] is None


def test_objetivos_a_mano_con_avisos(client):
    r = client.put("/api/targets", json={"kcal": 1300, "protein": 150, "carbs": 100, "fat": 40}).json()
    assert r["targets"]["custom"] is True
    assert r["warnings"][0]["code"] == "minimo_calorico"


def test_exportar(client):
    data = client.get("/api/export/json").json()
    assert len(data["meals"]) == 5 and len(data["weights"]) == 2
    csv_text = client.get("/api/export/meals.csv").text
    assert csv_text.splitlines()[0].lstrip("﻿").startswith("fecha;momento;comida")
    assert len(csv_text.strip().splitlines()) == 6


def test_el_administrador_no_puede_borrar_su_cuenta(client):
    assert client.post("/api/account/delete", json={"password": "mala"}).status_code == 403
    r = client.post("/api/account/delete", json={"password": "contraseña-larga"})
    assert r.status_code == 409 and "make-admin" in r.json()["detail"]
    assert client.get("/api/auth/status").json()["is_admin"] is True
