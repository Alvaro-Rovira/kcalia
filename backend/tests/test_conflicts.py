"""Escrituras simultáneas: si dos peticiones crean lo mismo a la vez, la segunda choca con un UNIQUE de SQLite. Antes
era un 500 (y la comida no se guardaba); ahora la petición se repite y ve lo que creó la otra."""

import pytest
from conftest import create_user, login, reset_database
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app import services
from app.conflicts import RetryOnConflict
from app.main import app


def _conflict() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed: dishes.user_id, dishes.norm"))


def _app(failures: int) -> tuple[FastAPI, list[int]]:
    calls: list[int] = []
    demo = FastAPI()

    @demo.post("/eco")
    async def echo(request: Request):
        calls.append(1)
        if len(calls) <= failures:
            raise _conflict()
        return {"body": (await request.body()).decode(), "intento": len(calls)}

    @demo.get("/lee")
    def read():
        calls.append(1)
        raise _conflict()

    demo.add_middleware(RetryOnConflict)
    return demo, calls


def test_un_choque_se_repite_con_el_mismo_cuerpo():
    demo, calls = _app(failures=1)
    with TestClient(demo) as client:
        response = client.post("/eco", content=b'{"a": 1}', headers={"Content-Type": "application/json"})
    assert response.status_code == 200 and response.json() == {"body": '{"a": 1}', "intento": 2}


def test_si_choca_siempre_acaba_en_error_sin_bucle():
    demo, calls = _app(failures=99)
    with TestClient(demo, raise_server_exceptions=False) as client:
        assert client.post("/eco", content=b"{}").status_code == 500
    assert len(calls) == 3


def test_las_lecturas_no_se_repiten():
    demo, calls = _app(failures=99)
    with TestClient(demo, raise_server_exceptions=False) as client:
        assert client.get("/lee").status_code == 500
    assert len(calls) == 1


@pytest.fixture()
def client():
    reset_database()
    create_user("ana")
    with TestClient(app) as c:
        login(c, "ana")
        profile = dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento")
        c.put("/api/profile", json=profile)
        yield c


def test_guardar_una_comida_sobrevive_a_otra_que_crea_el_mismo_plato_a_la_vez(client, monkeypatch):
    real = services.upsert_dish
    collided: list[int] = []

    def racing_upsert(*args, **kwargs):
        if not collided:  # primera vez: otra petición acaba de crear el mismo plato
            collided.append(1)
            raise _conflict()
        return real(*args, **kwargs)

    monkeypatch.setattr(services, "upsert_dish", racing_upsert)
    item = {"name": "pan", "qty": 1, "unit": "g", "grams": 40, "kcal": 100, "protein": 3, "carbs": 20, "fat": 1,
            "manual": True}  # fmt: skip
    body = {"client_id": "carrera-0001", "date": "2026-10-16", "slot": "snack", "name": "pan", "text": "pan",
            "items": [item], "source": "manual", "dish_id": None}  # fmt: skip
    assert client.post("/api/meals", json=body).status_code == 201
    meals = client.get("/api/meals", params={"date": "2026-10-16"}).json()["meals"]
    assert [m["client_id"] for m in meals] == ["carrera-0001"]
