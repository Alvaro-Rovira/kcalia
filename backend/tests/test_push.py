"""Notificaciones: suscripción, envío simulado (nunca a un servicio real), limpieza de caducadas, recordatorios y
aviso al administrador de nuevas solicitudes."""

import os
from datetime import datetime

import httpx
import pytest
from conftest import PASSWORD, create_user, login, reset_database
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import push, reminders
from app.config import get_settings
from app.main import app
from app.webpush import _public_bytes, b64url, generate_vapid_keys

NOW = datetime(2026, 10, 7, 16, 10)  # miércoles


def browser_keys() -> dict:
    key = ec.generate_private_key(ec.SECP256R1())
    return {"p256dh": b64url(_public_bytes(key.public_key())), "auth": b64url(os.urandom(16))}


class FakePushService:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(410 if "caducada" in str(request.url) else 201)


@pytest.fixture()
def service():
    settings = get_settings()
    settings.vapid_private_key, settings.vapid_public_key = generate_vapid_keys()
    fake = FakePushService()
    push.set_http_client(httpx.Client(transport=httpx.MockTransport(fake.handler)))
    yield fake
    push.set_http_client(None)
    settings.vapid_private_key = settings.vapid_public_key = ""


@pytest.fixture()
def client(service):
    with TestClient(app) as c:
        reset_database()
        create_user("alvaro", is_admin=True)
        create_user("ana")
        login(c, "ana")
        c.put(
            "/api/profile",
            json=dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento"),
        )
        yield c


def subscribe(client, endpoint):
    response = client.post("/api/push/subscribe", json={"endpoint": endpoint, "keys": browser_keys()})
    assert response.status_code == 200, response.text
    return response.json()


def test_sin_claves_vapid_no_hay_notificaciones(client):
    settings = get_settings()
    saved = settings.vapid_public_key
    settings.vapid_public_key = ""
    try:
        assert client.get("/api/push").json()["configured"] is False
        assert (
            client.post(
                "/api/push/subscribe", json={"endpoint": "https://push.example/a", "keys": browser_keys()}
            ).status_code
            == 503
        )
    finally:
        settings.vapid_public_key = saved


def test_suscribirse_y_notificacion_de_prueba(client, service):
    status = client.get("/api/push").json()
    assert status["configured"] is True and status["public_key"] == get_settings().vapid_public_key
    assert subscribe(client, "https://push.example/wpush/ana-movil")["devices"] == 1
    assert client.post("/api/push/test").json() == {"sent": 1}
    request = service.requests[-1]
    assert request.headers["content-encoding"] == "aes128gcm" and int(request.headers["ttl"]) > 0
    assert request.headers["authorization"].startswith("vapid t=") and len(request.content) > 86


def test_las_suscripciones_caducadas_se_borran(client, service):
    subscribe(client, "https://push.example/wpush/ana-movil")
    subscribe(client, "https://push.example/wpush/caducada")
    assert client.post("/api/push/test").json() == {"sent": 1}
    assert client.get("/api/push").json()["devices"] == 1


def test_el_mismo_navegador_pasa_a_la_cuenta_que_se_suscribe(client):
    subscribe(client, "https://push.example/wpush/compartido")
    login(client, "alvaro")
    subscribe(client, "https://push.example/wpush/compartido")
    login(client, "ana")
    assert client.get("/api/push").json()["devices"] == 0


def test_recordatorio_de_comida_solo_si_falta_y_una_vez(client, service):
    subscribe(client, "https://push.example/wpush/ana-movil")
    assert reminders.run(NOW) == 0  # recordatorios apagados por defecto
    client.patch("/api/prefs", json={"reminders": True})
    assert reminders.run(NOW) == 1  # comida a las 16:00, dentro de la franja
    assert reminders.run(NOW) == 0  # ya enviado hoy
    # La cena ya está apuntada: a su hora no se avisa.
    client.post(
        "/api/meals",
        json={
            "client_id": "cid-cena-recordatorio",
            "date": NOW.date().isoformat(),
            "slot": "cena",
            "name": "Tortilla",
            "items": [{"name": "huevo", "grams": 110, "kcal": 157, "protein": 14, "carbs": 1, "fat": 10}],
            "source": "manual",
        },
    )
    assert reminders.run(NOW.replace(hour=22, minute=20)) == 0
    # Fuera de la franja (más de 45 minutos después) tampoco.
    assert reminders.run(NOW.replace(hour=11, minute=30)) == 0


def test_recordatorio_de_peso(client, service):
    subscribe(client, "https://push.example/wpush/ana-movil")
    client.patch("/api/prefs", json={"reminders": True, "weigh_reminder": "08:30", "weigh_days": [2]})
    morning = NOW.replace(hour=8, minute=40)
    assert reminders.run(morning) == 1
    client.patch("/api/prefs", json={"weigh_days": [0]})
    assert reminders.run(morning.replace(day=14)) == 0  # otro miércoles, pero ya no es día de pesarse


def test_aviso_al_admin_de_una_solicitud_nueva(client, service):
    login(client, "alvaro")
    subscribe(client, "https://push.example/wpush/admin")
    client.cookies.clear()
    before = len(service.requests)
    client.post("/api/auth/register", json={"username": "lucia", "password": PASSWORD})
    assert len(service.requests) == before + 1
    assert str(service.requests[-1].url) == "https://push.example/wpush/admin"
