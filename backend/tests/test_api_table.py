"""Sin IA con la tabla oficial: comidas sencillas con cantidades salen exactas y gratis."""

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.ai import AiClient
from app.config import get_settings
from app.db import SessionLocal
from app.deps import get_ai_client
from app.foodtable import table
from app.main import app
from app.models import Food, User
from app.refine import OIL_NAME
from app.tenancy import as_user

T = table().entries


class NoAi:
    calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(500, json={"error": "no debería llamarse"})


@pytest.fixture(scope="module")
def no_ai():
    return NoAi()


@pytest.fixture(scope="module")
def client(no_ai):
    reset_database()
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(no_ai.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    create_user("ana")
    with TestClient(app) as c:
        login(c, "ana")
        yield c
    app.dependency_overrides.clear()


def kcal(entry_id, grams):
    return round(T[entry_id].kcal100 * grams / 100, 1)


def resolve(client, text):
    return client.post("/api/meals/resolve", json={"text": text}).json()


def test_simple_meal_with_quantities_resolves_from_the_table(client, no_ai):
    r = resolve(client, "200 g de arroz y 150 g de pollo a la plancha")
    assert r["status"] == "cache" and no_ai.calls == 0
    items = {i["name"]: i for i in r["draft"]["items"]}
    assert items["arroz blanco cocido"]["kcal"] == kcal("arroz-blanco-cocido", 200)
    assert items["pollo a la plancha"]["kcal"] == kcal("pollo-plancha", 150)
    assert items[OIL_NAME]["grams"] == 3
    assert {i["source"] for i in r["draft"]["items"]} == {"tabla"}
    assert r["draft"]["official_share"] == 1


def test_count_units_and_fried_food_without_ai(client, no_ai):
    r = resolve(client, "2 huevos fritos y una tostada")
    assert r["status"] == "cache" and no_ai.calls == 0
    names = [i["name"] for i in r["draft"]["items"]]
    assert OIL_NAME not in names  # lo frito ya lleva su grasa
    assert r["draft"]["kcal"] == pytest.approx(kcal("huevo-frito", 92) + kcal("tostada-pan", 40), abs=0.2)


def _set_food(username: str, **values) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username).one()
        with as_user(db, user.id):
            db.add(Food(**values))
            db.commit()


def test_user_corrected_food_beats_the_table(client):
    _set_food("ana", name="arroz", norm="arroz", kcal100=100, protein100=2, carbs100=22, fat100=0.5, source="usuario")
    r = resolve(client, "100 g de arroz")
    assert r["draft"]["items"][0]["kcal"] == 100 and r["draft"]["items"][0]["source"] == "usuario"


def test_cache_learned_from_the_ai_loses_to_the_table(client):
    _set_food("ana", name="lentejas", norm="lenteja", kcal100=200, protein100=9, carbs100=20, fat100=8, source="ia")
    r = resolve(client, "100 g de lentejas")
    assert r["draft"]["items"][0]["kcal"] == kcal("lentejas-cocidas", 100)


def test_table_search_for_manual_ingredients(client):
    found = client.get("/api/foods/table", params={"q": "pechuga pollo"}).json()["foods"]
    assert found[0]["ref"].startswith("ciqual:")
    assert {"name", "kcal100", "protein100", "carbs100", "fat100", "fiber100", "unit_grams", "source"} <= set(found[0])
    assert client.get("/api/foods/table", params={"q": "x"}).json()["foods"] == []


def test_history_meals_saved_with_old_ai_values_come_back_with_official_values(client):
    old = {"name": "huevo", "qty": 2, "unit": "pieza", "grams": 110, "kcal": 157.3, "protein": 13.9, "carbs": 0.8,
           "fat": 10.5}  # fmt: skip
    body = {"client_id": "hist-0001", "date": "2026-10-01", "slot": "cena", "name": "Huevos", "text": "mis huevos de la cena",
            "items": [old], "source": "ai", "dish_id": None}  # fmt: skip
    assert client.post("/api/meals", json=body).status_code == 201
    r = resolve(client, "mis huevos de la cena")
    assert r["status"] == "exact"
    assert r["draft"]["items"][0]["grams"] == 110 and r["draft"]["kcal"] == kcal("huevo-cocido", 110)
    dish = next(d for d in client.get("/api/dishes").json()["dishes"] if d["text"] == "mis huevos de la cena")
    assert dish["kcal"] == kcal("huevo-cocido", 110) and dish["items"][0]["source"] == "tabla"
