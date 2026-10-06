"""Seguimiento: agua, preferencias, fibra y alcohol, medidas y fotos de progreso."""

import pytest
from conftest import PASSWORD, create_user, login, reset_database
from fastapi.testclient import TestClient

from app.main import app

PROFILE = dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        reset_database()
        create_user("ana")
        login(c, "ana")
        c.put("/api/profile", json=PROFILE)
        yield c


def test_objetivo_de_agua_automatico_y_a_mano(client):
    # 61 kg × 35 ml = 2.135 ml -> redondeado a 250: 2.250 ml.
    assert client.get("/api/water", params={"date": "2026-10-01"}).json()["goal_ml"] == 2250
    assert client.get("/api/bootstrap").json()["water_goal_ml"] == 2250
    assert client.patch("/api/prefs", json={"water_goal_ml": 3000}).json()["water_goal_ml"] == 3000
    assert client.get("/api/water", params={"date": "2026-10-01"}).json()["goal_ml"] == 3000
    assert client.patch("/api/prefs", json={"water_goal_ml": None}).json()["water_goal_ml"] is None
    assert client.patch("/api/prefs", json={"water_goal_ml": 100}).status_code == 422
    assert client.patch("/api/prefs", json={"campo_raro": 1}).status_code == 422


def test_sumar_agua_es_idempotente_y_se_puede_deshacer(client):
    first = client.post("/api/water", json={"client_id": "agua-0001", "date": "2026-10-01", "ml": 250})
    assert first.status_code == 201 and first.json()["total_ml"] == 250
    client.post("/api/water", json={"client_id": "agua-0001", "date": "2026-10-01", "ml": 250})  # reintento
    day = client.post("/api/water", json={"client_id": "agua-0002", "date": "2026-10-01", "ml": 500}).json()
    assert day["total_ml"] == 750 and [e["ml"] for e in day["entries"]] == [250, 500]
    assert client.delete("/api/water/agua-0002").json()["total_ml"] == 250
    assert client.delete("/api/water/agua-0002").json() == {"ok": True}
    assert client.post("/api/water", json={"client_id": "agua-0003", "date": "2026-10-01", "ml": 0}).status_code == 422


def test_historial_y_exportacion_del_agua(client):
    client.post("/api/water", json={"client_id": "agua-0010", "date": "2026-10-02", "ml": 1500})
    days = client.get("/api/water/days", params={"start": "2026-09-28", "end": "2026-10-04"}).json()
    assert days["days"] == [{"date": "2026-10-01", "ml": 250}, {"date": "2026-10-02", "ml": 1500}]
    exported = client.get("/api/export/json").json()
    assert {w["client_id"] for w in exported["water"]} == {"agua-0001", "agua-0010"}
    assert "water_goal_ml" in exported["prefs"]
    csv_text = client.get("/api/export/water.csv").text
    assert "2026-10-02;1500" in csv_text


def test_borrar_datos_se_lleva_el_agua(client):
    assert client.post("/api/data/delete", json={"password": PASSWORD}).json() == {"ok": True}
    client.put("/api/profile", json=PROFILE)
    assert client.get("/api/water", params={"date": "2026-10-02"}).json()["total_ml"] == 0
