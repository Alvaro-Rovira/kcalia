"""Planificador semanal: comidas planificadas, lista de la compra y huecos rellenados por la IA (simulada)."""

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

LENTILS = {
    "name": "lentejas",
    "qty": 1,
    "unit": "plato",
    "grams": 330,
    "kcal": 383,
    "protein": 30,
    "carbs": 66,
    "fat": 1.3,
    "fiber": 26,
}
PLAN_REPLY = {
    "meals": [
        {
            "date": "2026-10-06",
            "slot": "cena",
            "name": "Tortilla francesa con ensalada",
            "items": [
                {
                    "name": "huevo",
                    "qty": 2,
                    "unit": "pieza",
                    "grams": 110,
                    "kcal100": 143,
                    "protein100": 12.6,
                    "carbs100": 0.7,
                    "fat100": 9.5,
                },
                {
                    "name": "lechuga",
                    "qty": 100,
                    "unit": "g",
                    "grams": 100,
                    "kcal100": 15,
                    "protein100": 1.4,
                    "carbs100": 2.9,
                    "fat100": 0.2,
                },
            ],
        },
        {
            "date": "2026-10-09",
            "slot": "comida",
            "name": "No pedido",
            "items": [
                {
                    "name": "x",
                    "qty": 1,
                    "unit": "g",
                    "grams": 10,
                    "kcal100": 100,
                    "protein100": 1,
                    "carbs100": 1,
                    "fat100": 1,
                }
            ],
        },
    ]
}


class Fake:
    calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(PLAN_REPLY)}}], "usage": {}})


@pytest.fixture(scope="module")
def ctx():
    fake = Fake()
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as client:
        reset_database()
        create_user("ana")
        create_user("beto")
        login(client, "ana")
        client.put(
            "/api/profile",
            json=dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento"),
        )
        yield client, fake
    app.dependency_overrides.clear()


def plan(client, cid, day="2026-10-06", slot="comida", items=(LENTILS,), **extra):
    response = client.put(
        "/api/plan",
        json={"client_id": cid, "date": day, "slot": slot, "name": "Lentejas", "items": list(items), **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_planificar_editar_y_borrar(ctx):
    client, _ = ctx
    first = plan(client, "plan-00000001")
    assert first["kcal"] == 383 and first["fiber"] == 26
    plan(client, "plan-00000001", servings=1.5)  # mismo client_id: se actualiza, no se duplica
    plan(client, "plan-00000002", day="2026-10-08", slot="cena")
    week = client.get("/api/plan", params={"start": "2026-10-07"}).json()
    assert week["start"] == "2026-10-05" and week["end"] == "2026-10-11"
    assert [(e["date"], e["servings"]) for e in week["entries"]] == [("2026-10-06", 1.5), ("2026-10-08", 1.0)]
    assert week["entries"][0]["kcal"] == pytest.approx(574.5)
    assert set(week["targets"]) == {f"2026-10-{d:02d}" for d in range(5, 12)}
    assert client.delete("/api/plan/plan-00000002").json() == {"ok": True}
    assert len(client.get("/api/plan", params={"start": "2026-10-05"}).json()["entries"]) == 1


def test_lista_de_la_compra_marcable(ctx):
    client, _ = ctx
    client.put("/api/plan/checks", json={"week_start": "2026-10-07", "key": "lenteja", "checked": True})
    assert client.get("/api/plan", params={"start": "2026-10-05"}).json()["checks"] == {"lenteja": True}
    client.put("/api/plan/checks", json={"week_start": "2026-10-05", "key": "lenteja", "checked": False})
    assert client.get("/api/plan", params={"start": "2026-10-05"}).json()["checks"] == {"lenteja": False}
    exported = client.get("/api/export/json").json()
    assert exported["meal_plans"][0]["client_id"] == "plan-00000001"
    assert exported["shopping_checks"] == [{"week_start": "2026-10-05", "key": "lenteja", "checked": False}]


def test_rellenar_huecos_con_la_ia(ctx):
    client, fake = ctx
    r = client.post("/api/plan/fill", json={"start": "2026-10-05", "slots": [{"date": "2026-10-06", "slot": "cena"}]})
    assert r.status_code == 200, r.text
    suggestions = r.json()["suggestions"]
    assert [s["name"] for s in suggestions] == ["Tortilla francesa con ensalada"]  # lo no pedido se descarta
    assert suggestions[0]["kcal"] == pytest.approx(172.3)
    assert fake.calls == 1
    assert client.get("/api/stats").json()["ai"]["used_today"] == 1  # gasta cupo como cualquier consulta
    bad = client.post("/api/plan/fill", json={"start": "2026-10-05", "slots": [{"date": "2026-11-01", "slot": "cena"}]})
    assert bad.status_code == 422
    with SessionLocal() as db:
        services.set_app_setting(db, "ai_paused", True)
        db.commit()
    paused = client.post(
        "/api/plan/fill", json={"start": "2026-10-05", "slots": [{"date": "2026-10-06", "slot": "cena"}]}
    )
    assert paused.status_code == 503 and fake.calls == 1
    with SessionLocal() as db:
        services.set_app_setting(db, "ai_paused", False)
        db.commit()


def test_el_plan_es_de_cada_uno(ctx):
    client, _ = ctx
    login(client, "beto")
    assert client.get("/api/plan", params={"start": "2026-10-05"}).json()["entries"] == []
    client.delete("/api/plan/plan-00000001")
    login(client, "ana")
    assert len(client.get("/api/plan", params={"start": "2026-10-05"}).json()["entries"]) == 1
