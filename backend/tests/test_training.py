"""Registro de entrenamientos: catálogo, plantillas, sesiones y series (idempotentes), referencias y progresión."""

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.main import app
from app.workouts import CATALOG, TEMPLATES, estimated_1rm, estimated_kcal

PROFILE = dict(sex="hombre", age=30, height_cm=178, weight_kg=80, activity="moderado", goal="mantenimiento")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        reset_database()
        create_user("ana")
        create_user("beto")
        login(c, "ana")
        c.put("/api/profile", json=PROFILE)
        yield c


def workout(client, cid, day="2026-10-01", **extra):
    response = client.post("/api/workouts", json={"client_id": cid, "date": day, "name": "Empuje", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def add_set(client, workout_cid, cid, exercise, reps, weight, **extra):
    body = {"client_id": cid, "exercise": exercise, "reps": reps, "weight": weight, **extra}
    response = client.post(f"/api/workouts/{workout_cid}/sets", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_formulas():
    assert estimated_1rm(100, 1) == 100
    assert estimated_1rm(80, 8) == pytest.approx(101.3)
    assert estimated_1rm(50, 20) == estimated_1rm(50, 12)  # a partir de 12 repeticiones no sube más
    assert estimated_1rm(0, 10) == 0
    assert estimated_kcal(60, "moderada", 80) == 400
    assert estimated_kcal(45, "intensa", 70) == 315
    assert estimated_kcal(None, "suave", 80) == 0


def test_catalogo_y_plantillas_iniciales_una_sola_vez(client):
    first = client.get("/api/training").json()
    assert len(first["exercises"]) == len(CATALOG) and len(first["templates"]) == len(TEMPLATES)
    assert {t["name"] for t in first["templates"]} == {"Empuje", "Tirón", "Pierna", "Cuerpo completo"}
    plank = next(e for e in first["exercises"] if e["client_id"] == "ex-plancha")
    assert plank["unit"] == "seg"
    again = client.get("/api/training").json()
    assert len(again["exercises"]) == len(CATALOG)


def test_sesion_y_series_idempotentes(client):
    workout(client, "wk-0000001", started_at="2026-10-01T18:00:00Z")
    workout(client, "wk-0000001")  # reintento de la cola
    add_set(client, "wk-0000001", "set-000001", "ex-press-banca", 8, 80, rpe=8)
    add_set(client, "wk-0000001", "set-000001", "ex-press-banca", 8, 80)  # reintento
    data = add_set(client, "wk-0000001", "set-000002", "ex-press-banca", 6, 85, position=1)
    assert [s["weight"] for s in data["sets"]] == [80, 85] and data["volume"] == 80 * 8 + 85 * 6
    assert len([w for w in client.get("/api/training").json()["workouts"] if w["client_id"] == "wk-0000001"]) == 1
    patched = client.patch("/api/sets/set-000002", json={"reps": 7}).json()
    assert patched["sets"][1]["reps"] == 7
    ended = client.patch(
        "/api/workouts/wk-0000001", json={"ended_at": "2026-10-01T19:05:00Z", "intensity": "intensa"}
    ).json()
    assert ended["duration_min"] == 65 and ended["kcal"] == estimated_kcal(65, "intensa", 80)
    assert (
        client.post(
            "/api/workouts/no-existe-1/sets", json={"client_id": "set-x00001", "exercise": "ex-press-banca", "reps": 5}
        ).status_code
        == 404
    )
    assert add_set_status(client, "wk-0000001", "ex-inventado") == 404


def add_set_status(client, workout_cid, exercise):
    body = {"client_id": "set-zz00001", "exercise": exercise, "reps": 5, "weight": 10}
    return client.post(f"/api/workouts/{workout_cid}/sets", json=body).status_code


def test_ultima_vez_y_progresion(client):
    workout(client, "wk-0000002", day="2026-10-04")
    add_set(client, "wk-0000002", "set-000010", "ex-press-banca", 8, 82.5)
    add_set(client, "wk-0000002", "set-000011", "ex-press-banca", 8, 82.5, position=1)
    last = client.get("/api/training").json()["last"]["ex-press-banca"]
    assert last == {"date": "2026-10-04", "weight": 82.5, "reps": 8, "sets": 2}
    history = client.get("/api/exercises/ex-press-banca/history", params={"days": 3650}).json()["sessions"]
    assert [h["date"] for h in history] == ["2026-10-01", "2026-10-04"]
    assert history[0]["best_1rm"] == estimated_1rm(85, 7) and history[1]["volume"] == 82.5 * 16


def test_ejercicio_propio_creado_sin_conexion(client):
    created = client.post(
        "/api/exercises", json={"client_id": "ex-mio-0001", "name": "Press Arnold", "muscle": "hombros"}
    )
    again = client.post(
        "/api/exercises", json={"client_id": "ex-mio-0001", "name": "Press Arnold", "muscle": "hombros"}
    )
    assert created.json()["id"] == again.json()["id"] and created.json()["custom"] is True
    add_set(client, "wk-0000002", "set-000020", "ex-mio-0001", 10, 14)
    archived = client.patch("/api/exercises/ex-mio-0001", json={"archived": True}).json()
    assert archived["archived"] is True


def test_plantillas_editables(client):
    saved = client.put(
        "/api/templates",
        json={
            "client_id": "tpl-mia-0001",
            "name": "Torso",
            "exercises": [{"exercise": "ex-press-banca", "sets": 4, "reps": 6}],
        },
    ).json()
    assert saved["exercises"] == [{"exercise": "ex-press-banca", "sets": 4, "reps": 6}]
    renamed = client.put(
        "/api/templates", json={"client_id": "tpl-mia-0001", "name": "Torso A", "exercises": []}
    ).json()
    assert renamed["name"] == "Torso A" and renamed["exercises"] == []
    bad = client.put(
        "/api/templates",
        json={"client_id": "tpl-mia-0002", "name": "X", "exercises": [{"exercise": "ex-nada", "sets": 3, "reps": 5}]},
    )
    assert bad.status_code == 422
    client.delete("/api/templates/tpl-mia-0001")
    assert all(t["client_id"] != "tpl-mia-0001" for t in client.get("/api/training").json()["templates"])


def test_exportacion_y_otro_usuario(client):
    exported = client.get("/api/export/json").json()
    assert {w["client_id"] for w in exported["workouts"]} == {"wk-0000001", "wk-0000002"}
    assert any(e["client_id"] == "ex-mio-0001" for e in exported["exercises"])
    csv_text = client.get("/api/export/workouts.csv").text
    assert "2026-10-01;Empuje;Press de banca;1;8;80,0;8,0;65" in csv_text

    login(client, "beto")
    assert client.get("/api/training").json()["workouts"] == []
    assert client.patch("/api/workouts/wk-0000001", json={"name": "robado"}).status_code == 404
    assert client.patch("/api/sets/set-000001", json={"reps": 1}).status_code == 404
    assert (
        client.post(
            "/api/workouts/wk-0000001/sets", json={"client_id": "set-beto001", "exercise": "ex-press-banca", "reps": 5}
        ).status_code
        == 404
    )
    login(client, "ana")


def test_borrar_entreno_y_sus_series(client):
    assert client.delete("/api/workouts/wk-0000002").json() == {"ok": True}
    assert client.delete("/api/workouts/wk-0000002").json() == {"ok": True}
    assert client.delete("/api/sets/set-000010").json() == {"ok": True}  # ya no existe: no es un error
    assert [w["client_id"] for w in client.get("/api/training").json()["workouts"]] == ["wk-0000001"]
