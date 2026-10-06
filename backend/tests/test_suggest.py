"""Ideas de la IA para cerrar el día: solo con el botón, con todos los límites, sin pasarse y sin alcohol."""

import json

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app import services
from app.ai import AiClient
from app.config import get_settings
from app.db import SessionLocal
from app.deps import get_ai_client
from app.main import app
from app.routers.suggest import fit_to


def per100(name, grams, kcal100, p, c, f, alcohol=0):
    return {
        "name": name,
        "qty": 1,
        "unit": "pieza",
        "grams": grams,
        "kcal100": kcal100,
        "protein100": p,
        "carbs100": c,
        "fat100": f,
        "alcohol100": alcohol,
    }


REPLY = {
    "ideas": [
        {
            "name": "Yogur griego con nueces",
            "items": [per100("yogur griego", 125, 120, 6, 4, 9), per100("nueces", 30, 654, 15, 14, 65)],
        },
        {"name": "Una caña", "items": [per100("cerveza", 200, 43, 0.4, 3.6, 0, alcohol=3.9)]},
        {"name": "Lata de atún", "items": [per100("atún", 56, 110, 25, 0, 1)]},
        {"name": "Plato enorme", "items": [per100("pasta", 600, 360, 12, 72, 1.5)]},
    ]
}


class Fake:
    calls = 0
    last = ""

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.last = json.loads(request.content)["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(REPLY)}}], "usage": {}})


@pytest.fixture(scope="module")
def ctx():
    fake = Fake()
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as client:
        reset_database()
        create_user("ana")
        login(client, "ana")
        client.put(
            "/api/profile",
            json=dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento"),
        )
        yield client, fake
    app.dependency_overrides.clear()


def test_ideas_sin_pasarse_y_sin_alcohol(ctx):
    client, fake = ctx
    r = client.post("/api/suggest/ai", json={"kcal": 250, "protein": 20, "carbs": 30, "fat": 10, "hour": 21})
    assert r.status_code == 200, r.text
    ideas = r.json()["ideas"]
    names = [i["name"] for i in ideas]
    assert "Una caña" not in names  # nada con alcohol
    assert "Plato enorme" not in names  # 2.160 kcal: recortarlo a 250 sería una ración ridícula
    assert all(i["kcal"] <= 250 for i in ideas)
    yogur = next(i for i in ideas if i["name"] == "Yogur griego con nueces")
    assert yogur["kcal"] <= 250 and yogur["items"][0]["grams"] < 125  # 346 kcal: ración recortada
    assert "como máximo" in fake.last and "250 kcal" in fake.last
    assert client.get("/api/stats").json()["ai"]["used_today"] == 1


def test_respeta_la_pausa_de_la_ia(ctx):
    client, fake = ctx
    with SessionLocal() as db:
        services.set_app_setting(db, "ai_paused", True)
        db.commit()
    calls = fake.calls
    r = client.post("/api/suggest/ai", json={"kcal": 250, "protein": 20, "carbs": 30, "fat": 10, "hour": 21})
    assert r.status_code == 503 and fake.calls == calls
    with SessionLocal() as db:
        services.set_app_setting(db, "ai_paused", False)
        db.commit()


def test_recortar_racion():
    items = [
        {
            "name": "x",
            "qty": 2,
            "unit": "pieza",
            "grams": 200,
            "kcal": 300,
            "protein": 20,
            "carbs": 10,
            "fat": 20,
            "fiber": None,
        }
    ]
    fitted = fit_to(items, 180)
    assert fitted is not None and fitted[0]["kcal"] <= 180 and fitted[0]["grams"] == 120
    assert fit_to(items, 50) is None
    assert fit_to(items, 300) == items


def test_preferencias_de_la_sugerencia(ctx):
    client, _ = ctx
    prefs = client.get("/api/prefs").json()
    assert prefs["suggest_enabled"] is True and prefs["suggest_hour"] == "21:00" and prefs["suggest_min_kcal"] is None
    assert client.get("/api/bootstrap").json()["suggest_min_kcal_default"] == 80
    saved = client.patch(
        "/api/prefs", json={"suggest_min_kcal": 120, "suggest_hour": "20:30", "suggest_hidden": ["dish:3"]}
    ).json()
    assert saved["suggest_min_kcal"] == 120 and saved["suggest_hidden"] == ["dish:3"]
    assert client.patch("/api/prefs", json={"suggest_hour": "25:00"}).status_code == 422
