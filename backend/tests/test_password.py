"""Cambio de contraseña y freno de las confirmaciones con contraseña (borrar datos, borrar cuenta, cambiarla)."""

import pytest
from conftest import PASSWORD, create_user, login, reset_database
from fastapi.testclient import TestClient

from app.main import app

NEW = "otra-clave-bien-larga"


@pytest.fixture()
def two_devices():
    reset_database()
    create_user("ana")
    phone, laptop = TestClient(app), TestClient(app)
    with phone, laptop:
        login(phone, "ana")
        login(laptop, "ana")
        yield phone, laptop


def change(client, current, new):
    return client.post("/api/account/password", json={"current_password": current, "new_password": new})


def test_cambiar_la_contrasena_cierra_las_demas_sesiones(two_devices):
    phone, laptop = two_devices
    assert change(phone, PASSWORD, NEW).status_code == 200
    assert phone.get("/api/bootstrap").status_code == 200  # la sesión desde la que se cambia sigue abierta
    assert laptop.get("/api/bootstrap").status_code == 401  # las demás se cierran
    with TestClient(app) as other:
        assert other.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 401
        assert other.post("/api/auth/login", json={"username": "ana", "password": NEW}).status_code == 200


def test_hace_falta_la_contrasena_actual(two_devices):
    phone, _ = two_devices
    assert change(phone, "no-es-la-mia", NEW).status_code == 403
    with TestClient(app) as other:
        assert other.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize("weak", ["corta", "1234567890", "ana-ana-ana-ana", PASSWORD])
def test_la_nueva_debe_ser_buena_y_distinta(two_devices, weak):
    phone, _ = two_devices
    response = change(phone, PASSWORD, weak)
    assert response.status_code == 422 and response.json()["detail"]


def test_las_confirmaciones_con_contrasena_tienen_freno(two_devices):
    # Con una sesión robada no se puede probar contraseñas sin límite (aquí, con «borrar mis datos»).
    phone, _ = two_devices
    for _ in range(5):
        assert phone.post("/api/data/delete", json={"password": "probando"}).status_code == 403
    assert phone.post("/api/data/delete", json={"password": "probando"}).status_code == 429
    assert change(phone, PASSWORD, NEW).status_code == 429  # el freno es por cuenta, valga la ruta que valga
