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


BEER = {
    "name": "cerveza (caña)",
    "qty": 200,
    "unit": "ml",
    "grams": 200,
    "kcal": 69.3,
    "protein": 0.8,
    "carbs": 7.2,
    "fat": 0,
    "alcohol": 7.9,
}
BREAD = {
    "name": "pan integral",
    "qty": 60,
    "unit": "g",
    "grams": 60,
    "kcal": 150,
    "protein": 6,
    "carbs": 25,
    "fat": 2,
    "fiber": 4.2,
}
OLD = {
    "name": "tortilla",
    "qty": 1,
    "unit": "pieza",
    "grams": 150,
    "kcal": 285,
    "protein": 9.8,
    "carbs": 18,
    "fat": 19.5,
}


def add(client, cid, items, **extra):
    body = {
        "client_id": cid,
        "date": "2026-10-05",
        "slot": "cena",
        "name": "Cena",
        "items": items,
        "source": "manual",
        **extra,
    }
    response = client.post("/api/meals", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_fibra_y_alcohol_en_comidas_dia_y_semana(client):
    beer = add(client, "cid-cerveza1", [BEER], source="drink", servings=2)
    assert beer["alcohol"] == pytest.approx(15.8) and beer["kcal"] == pytest.approx(138.6)
    dinner = add(client, "cid-cena-001", [BREAD, OLD])
    assert dinner["fiber"] == 4.2 and dinner["alcohol"] == 0  # lo que no trae el dato cuenta como 0
    day = client.get("/api/days", params={"start": "2026-10-05", "end": "2026-10-05"}).json()["days"][0]
    assert day["fiber"] == 4.2 and day["alcohol"] == pytest.approx(15.8)
    week = client.get("/api/summary/week", params={"start": "2026-10-05"}).json()
    assert week["alcohol"]["grams"] == pytest.approx(15.8) and week["alcohol"]["kcal"] == 111
    assert week["alcohol"]["days"] == 1 and week["avg_fiber"] == 4.2
    patched = client.patch("/api/meals/cid-cena-001", json={"servings": 2}).json()
    assert patched["fiber"] == 8.4
    csv_text = client.get("/api/export/meals.csv").text
    assert "fibra_g;alcohol_g" in csv_text.splitlines()[0] and "15,8" in csv_text


JPEG = b"\xff\xd8\xff\xe0" + b"7" * 3000


def test_medidas_por_dia_idempotentes(client):
    client.put("/api/measurements", json={"date": "2026-09-01", "waist": 82.5, "hip": 98})
    client.put("/api/measurements", json={"date": "2026-09-01", "waist": 82, "hip": 98})  # mismo día: se corrige
    entries = client.put("/api/measurements", json={"date": "2026-09-15", "waist": 80.5, "arm": 33}).json()["entries"]
    assert [(e["date"], e["waist"]) for e in entries] == [("2026-09-01", 82), ("2026-09-15", 80.5)]
    assert entries[1]["chest"] is None
    assert client.put("/api/measurements", json={"date": "2026-09-20", "waist": 10}).status_code == 422
    # Sin ninguna medida, el día desaparece.
    assert len(client.put("/api/measurements", json={"date": "2026-09-15"}).json()["entries"]) == 1
    exported = client.get("/api/export/json").json()
    assert exported["measurements"] == [
        {"date": "2026-09-01", "waist": 82, "chest": None, "arm": None, "hip": 98, "thigh": None}
    ]
    assert "fotos" not in exported and "photos" not in exported
    assert "2026-09-01;82,0;;;98,0;" in client.get("/api/export/measurements.csv").text


def test_fotos_de_progreso(client):
    first = client.post(
        "/api/photos",
        data={"date": "2026-09-01", "client_id": "foto-0001"},
        files={"image": ("a.jpg", JPEG, "image/jpeg")},
    )
    assert first.status_code == 201
    again = client.post(
        "/api/photos",
        data={"date": "2026-09-01", "client_id": "foto-0001"},
        files={"image": ("a.jpg", JPEG, "image/jpeg")},
    )
    assert again.json()["id"] == first.json()["id"]  # reintento sin duplicar
    client.post(
        "/api/photos",
        data={"date": "2026-10-01", "client_id": "foto-0002"},
        files={"image": ("b.jpg", JPEG, "image/jpeg")},
    )
    photos = client.get("/api/photos").json()["photos"]
    assert [p["date"] for p in photos] == ["2026-10-01", "2026-09-01"]
    assert "data" not in photos[0] and photos[0]["size"] == len(JPEG)
    assert client.get(f"/api/photos/{photos[1]['id']}/image").content == JPEG
    bad = client.post(
        "/api/photos",
        data={"date": "2026-10-01", "client_id": "foto-0003"},
        files={"image": ("x.gif", b"GIF89a", "image/gif")},
    )
    assert bad.status_code == 415
    assert client.delete(f"/api/photos/{photos[0]['id']}").json() == {"ok": True}
    assert len(client.get("/api/photos").json()["photos"]) == 1


def test_fotos_y_medidas_de_otro_usuario_no_se_ven(client):
    create_user("beto")
    photo_id = client.get("/api/photos").json()["photos"][0]["id"]
    login(client, "beto")
    assert client.get("/api/photos").json()["photos"] == []
    assert client.get(f"/api/photos/{photo_id}/image").status_code == 404
    client.delete(f"/api/photos/{photo_id}")
    assert client.get("/api/measurements").json()["entries"] == []
    login(client, "ana")
    assert len(client.get("/api/photos").json()["photos"]) == 1
