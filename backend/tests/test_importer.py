"""Importar datos: CSV de MyFitnessPal, Yazio o genérico con mapeo, duplicados, idempotencia y JSON de Kcalia."""

import json

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.importer import parse_date, parse_number
from app.main import app

MFP = (
    "Date,Meal,Calories,Fat (g),Saturated Fat,Carbohydrates (g),Fiber,Sugar,Protein (g),Note\n"
    "2026-09-01,Breakfast,350,12,3,40,5,10,20,\n"
    "2026-09-01,Lunch,700,25,8,70,9,5,45,\n"
    "2026-09-01,Snacks,150,5,1,20,2,15,6,\n"
    "2026-09-01,Snacks,150,5,1,20,2,15,6,\n"
)
YAZIO_ES = (
    "Fecha;Comida;Nombre;Energía (kcal);Proteínas (g);Carbohidratos (g);Grasas (g)\n"
    "02/09/2026;Cena;Tortilla de patatas;380,5;12,2;30;22,1\n"
    "03/09/2026;Desayuno;Café con leche;92;6,6;9,6;3,2\n"
)


def upload(client, path, content, **form):
    return client.post(path, files={"file": ("datos.csv", content.encode(), "text/csv")}, data=form)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        reset_database()
        create_user("ana")
        create_user("beto")
        login(c, "ana")
        c.put(
            "/api/profile",
            json=dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento"),
        )
        yield c


def test_numeros_y_fechas():
    assert parse_number("1.234,5") == 1234.5 and parse_number("1,234.5") == 1234.5 and parse_number("12,5 g") == 12.5
    assert parse_number("") is None and parse_number("n/a") is None
    assert parse_date("2026-09-03") == parse_date("03/09/2026") == "2026-09-03"
    assert parse_date("09/03/2026", month_first=True) == "2026-09-03"
    assert parse_date("ayer") is None


def test_myfitnesspal_vista_previa_e_importacion_idempotente(client):
    preview = upload(client, "/api/import/csv/preview", MFP).json()
    assert preview["format"] == "myfitnesspal" and preview["rows"] == 4 and preview["new"] == 4
    assert preview["mapping"]["slot"] == "Meal" and preview["mapping"]["protein"] == "Protein (g)"
    assert preview["sample"][0] == {
        "date": "2026-09-01",
        "slot": "desayuno",
        "name": "Breakfast (MyFitnessPal)",
        "kcal": 350,
        "protein": 20,
        "carbs": 40,
        "fat": 12,
    }
    first = upload(client, "/api/import/csv", MFP).json()
    assert first["created"] == 4  # las dos meriendas iguales son dos comidas distintas
    again = upload(client, "/api/import/csv", MFP).json()
    assert again["created"] == 0 and again["already"] == 4
    day = client.get("/api/days", params={"start": "2026-09-01", "end": "2026-09-01"}).json()["days"][0]
    assert day["kcal"] == 1350 and day["meals"] == 4 and day["fiber"] == 18
    meals = client.get("/api/meals", params={"date": "2026-09-01"}).json()["meals"]
    assert {m["source"] for m in meals} == {"import"}


def test_yazio_en_espanol_con_coma_decimal(client):
    preview = upload(client, "/api/import/csv/preview", YAZIO_ES).json()
    assert preview["mapping"]["name"] == "Nombre" and preview["mapping"]["kcal"] == "Energía (kcal)"
    assert preview["sample"][0]["slot"] == "cena" and preview["sample"][0]["kcal"] == 380.5
    assert upload(client, "/api/import/csv", YAZIO_ES).json()["created"] == 2
    assert client.get("/api/meals", params={"date": "2026-09-02"}).json()["meals"][0]["name"] == "Tortilla de patatas"


def test_formato_generico_con_mapeo_manual(client):
    csv_text = "Día,Qué,Valor energético,Prot\n2026-09-05,Lentejas,450,24\n2026-09-05,,,\n2099-01-01,Futuro,100,1\n"
    preview = upload(client, "/api/import/csv/preview", csv_text).json()
    assert preview["format"] == "generico" and preview["valid"] == 0
    assert "calorías" in preview["errors"][0]["message"]
    mapping = json.dumps({"date": "Día", "name": "Qué", "kcal": "Valor energético", "protein": "Prot"})
    preview = upload(client, "/api/import/csv/preview", csv_text, mapping=mapping).json()
    assert preview["valid"] == 1 and preview["error_count"] == 1  # la fila vacía se ignora; la futura, error
    assert upload(client, "/api/import/csv", csv_text, mapping=mapping).json()["created"] == 1


def test_posibles_duplicados_de_lo_ya_apuntado(client):
    client.post(
        "/api/meals",
        json={
            "client_id": "cid-a-mano-1",
            "date": "2026-09-01",
            "slot": "desayuno",
            "name": "Avena",
            "source": "manual",
            "items": [{"name": "avena", "grams": 90, "kcal": 350, "protein": 20, "carbs": 40, "fat": 12}],
        },
    )
    preview = upload(client, "/api/import/csv/preview", MFP).json()
    assert preview["duplicates"] == 1 and preview["new"] == 3
    result = upload(client, "/api/import/csv", MFP).json()
    assert result["created"] == 3 and result["skipped_duplicates"] == 1
    assert upload(client, "/api/import/csv", MFP, skip_duplicates="false").json()["created"] == 1


def test_json_de_kcalia_a_otra_cuenta_sin_duplicar(client):
    upload(client, "/api/import/csv", MFP)
    client.put("/api/weight", json={"date": "2026-09-02", "kg": 60.5})
    client.post("/api/water", json={"client_id": "agua-imp-01", "date": "2026-09-02", "ml": 500})
    client.put("/api/measurements", json={"date": "2026-09-02", "waist": 70})
    client.get("/api/training")
    exported = client.get("/api/export/json").content

    login(client, "beto")
    result = client.post("/api/import/json", files={"file": ("kcalia.json", exported, "application/json")}).json()[
        "created"
    ]
    assert result["comidas"] == 4 and result["pesos"] >= 1 and result["agua"] == 1 and result["medidas"] == 1
    assert result["perfil"] == 1 and result["objetivos"] == 1 and result["ejercicios"] >= 40
    again = client.post("/api/import/json", files={"file": ("kcalia.json", exported, "application/json")}).json()[
        "created"
    ]
    assert again == {}
    assert (
        client.get("/api/days", params={"start": "2026-09-01", "end": "2026-09-01"}).json()["days"][0]["kcal"] == 1350
    )
    bad = client.post("/api/import/json", files={"file": ("x.json", b'{"app": "Otra"}', "application/json")})
    assert bad.status_code == 422 and "Kcalia" in bad.json()["detail"]
    assert (
        client.post("/api/import/json", files={"file": ("x.json", b"no es json", "application/json")}).status_code
        == 422
    )
