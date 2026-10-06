"""Solicitudes de cuenta, inicio de sesión y límites de gasto de IA y voz."""

import json

import httpx
import pytest
from conftest import PASSWORD, create_user, login, reset_database
from fastapi.testclient import TestClient

from app import services
from app.ai import AiClient
from app.config import get_settings
from app.db import SessionLocal
from app.deps import get_ai_client
from app.main import app
from app.models import User
from app.security import Throttle, password_problem, username_problem

MEAL = {
    "name": "Manzana",
    "items": [
        {
            "name": "manzana",
            "qty": 1,
            "unit": "pieza",
            "grams": 150,
            "kcal100": 52,
            "protein100": 0.3,
            "carbs100": 14,
            "fat100": 0.2,
        }
    ],
    "confidence": 0.8,
    "assumptions": [],
    "clarification": None,
}


class Counter:
    calls = 0

    def handler(self, _: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(MEAL)}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
            },
        )


@pytest.fixture()
def client():
    fake = Counter()
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as c:
        reset_database()
        create_user("admin", is_admin=True)
        c.fake = fake  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()


def users() -> dict[str, str]:
    with SessionLocal() as db:
        return {u.username: u.status for u in db.query(User)}


def register(client, username, password=PASSWORD, **extra):
    client.cookies.clear()
    return client.post("/api/auth/register", json={"username": username, "password": password, **extra})


# ---------------------------------------------------------------- solicitudes


def test_solicitud_queda_pendiente_y_no_inicia_sesion(client):
    r = register(client, "lucia")
    assert r.status_code == 200 and r.json()["status"] == "received"
    assert users()["lucia"] == "pending"
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_usuario_repetido_recibe_la_misma_respuesta(client):
    first = register(client, "lucia").json()
    again = register(client, "LUCIA", "otra-clave-distinta-9").json()
    assert first == again
    assert list(users()).count("lucia") == 1 and "LUCIA" not in users()


def test_campo_trampa_no_crea_nada(client):
    r = register(client, "robot", website="http://spam.example")
    assert r.json()["status"] == "received"
    assert "robot" not in users()


def test_validacion_de_usuario_y_contrasena(client):
    assert register(client, "a b").status_code == 422
    assert register(client, "lu").status_code == 422
    assert "al menos" in register(client, "lucia", "corta").json()["detail"]
    assert register(client, "lucia", "1234567890").status_code == 422
    assert register(client, "lucia", "lucia-clave-2026").status_code == 422
    assert username_problem("álvaro") is not None and username_problem("alvaro.r_2") is None
    assert password_problem("ana", "aaaaaaaaaaaa") is not None
    assert password_problem("ana", "frase larga con 3 palabras") is None


def test_tope_de_solicitudes_pendientes(client):
    settings = get_settings()
    previous = settings.max_pending_accounts
    settings.max_pending_accounts = 2
    try:
        register(client, "uno-1")
        register(client, "dos-2")
        r = register(client, "tres-3")
        assert r.status_code == 503 and "muchas solicitudes" in r.json()["detail"]
        assert client.get("/api/auth/status").json()["signup"] == "full"
        assert "tres-3" not in users()
    finally:
        settings.max_pending_accounts = previous


def test_registro_cerrado(client):
    settings = get_settings()
    settings.allow_signup = False
    try:
        assert register(client, "lucia").status_code == 403
        assert client.get("/api/auth/status").json()["signup"] == "closed"
    finally:
        settings.allow_signup = True
    with SessionLocal() as db:
        services.set_app_setting(db, "signup_open", False)
        db.commit()
    assert register(client, "lucia").status_code == 403


def test_limite_de_solicitudes_por_conexion(client):
    for n in range(5):
        assert register(client, f"persona-{n}").status_code == 200
    assert register(client, "persona-6").status_code == 429


# ---------------------------------------------------------------- inicio de sesión


def test_mensaje_generico_y_espera_creciente(client):
    create_user("lucia")
    unknown = client.post("/api/auth/login", json={"username": "nadie", "password": "x"})
    wrong = client.post("/api/auth/login", json={"username": "lucia", "password": "x"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    for _ in range(4):
        client.post("/api/auth/login", json={"username": "lucia", "password": "mala"})
    blocked = client.post("/api/auth/login", json={"username": "lucia", "password": PASSWORD})
    assert blocked.status_code == 429  # ni siquiera con la buena, hasta que pase la espera


def test_la_espera_crece_y_un_acierto_la_borra():
    now = [1000.0]
    throttle = Throttle(free=2, base=10, cap=100, clock=lambda: now[0])
    throttle.fail("k")
    throttle.fail("k")
    assert throttle.retry_after("k") == 10
    throttle.fail("k")
    assert throttle.retry_after("k") == 20
    now[0] += 20
    assert throttle.retry_after("k") == 0
    for _ in range(10):
        throttle.fail("k")
    assert throttle.retry_after("k") == 100  # con tope
    throttle.reset("k")
    assert throttle.retry_after("k") == 0


def test_cuenta_bloqueada_deja_de_funcionar_en_la_siguiente_peticion(client):
    create_user("lucia")
    login(client, "lucia")
    assert client.get("/api/stats").status_code == 200
    with SessionLocal() as db:
        db.query(User).filter_by(username="lucia").update({"status": "suspended"})
        db.commit()
    assert client.get("/api/stats").status_code == 403


# ---------------------------------------------------------------- límites de gasto


def resolve(client, text):
    return client.post("/api/meals/resolve", json={"text": text, "force_ai": True})


def test_limite_por_usuario(client):
    create_user("lucia")
    with SessionLocal() as db:
        db.query(User).filter_by(username="lucia").update({"ai_daily_limit": 2})
        db.commit()
    login(client, "lucia")
    assert resolve(client, "una manzana").status_code == 200
    assert resolve(client, "dos manzanas").status_code == 200
    r = resolve(client, "tres manzanas")
    assert r.status_code == 429 and r.json()["code"] == "limit"
    assert client.fake.calls == 2  # type: ignore[attr-defined]


def test_limite_global_no_bloquea_al_admin(client):
    # La configuración de pruebas fija AI_DAILY_LIMIT=5 (global) y el límite por usuario es 20.
    for name in ("u-uno", "u-dos"):
        create_user(name)
    login(client, "u-uno")
    for n in range(5):
        assert resolve(client, f"manzana {n}").status_code == 200
    login(client, "u-dos")
    r = resolve(client, "una pera")
    assert r.status_code == 429 and r.json()["code"] == "global_limit"
    login(client, "admin")
    assert resolve(client, "una pera").status_code == 200


def test_pausa_de_la_ia_para_todos(client):
    create_user("lucia")
    with SessionLocal() as db:
        services.set_app_setting(db, "ai_paused", True)
        db.commit()
    for name in ("lucia", "admin"):
        login(client, name)
        r = resolve(client, "una manzana")
        assert r.status_code == 503 and r.json()["code"] == "paused"
        audio = client.post("/api/transcribe", files={"audio": ("a.webm", b"0" * 2000, "audio/webm")})
        assert audio.status_code == 503
    assert client.fake.calls == 0  # type: ignore[attr-defined]
    # Lo que no gasta IA sigue funcionando.
    assert client.get("/api/stats").status_code == 200


def test_limite_de_voz_por_usuario(client, monkeypatch):
    from app.routers import meals

    monkeypatch.setattr(meals, "transcribe", lambda *a, **k: "una manzana")
    create_user("lucia")
    with SessionLocal() as db:
        db.query(User).filter_by(username="lucia").update({"stt_daily_limit": 1})
        db.commit()
    login(client, "lucia")
    audio = {"audio": ("a.webm", b"0" * 2000, "audio/webm")}
    assert client.post("/api/transcribe", files=audio).json() == {"text": "una manzana"}
    r = client.post("/api/transcribe", files=audio)
    assert r.status_code == 429 and r.json()["code"] == "limit"
