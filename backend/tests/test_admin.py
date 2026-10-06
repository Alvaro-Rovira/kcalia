"""Panel de administración: solo el admin, flujo completo de una solicitud, bloqueos, límites y auditoría."""

import json

import httpx
import pytest
from conftest import PASSWORD, create_user, login, reset_database
from fastapi.testclient import TestClient

from app.ai import AiClient
from app.config import get_settings
from app.deps import get_ai_client
from app.main import app

MEAL = {
    "name": "Pera",
    "items": [
        {
            "name": "pera",
            "qty": 1,
            "unit": "pieza",
            "grams": 160,
            "kcal100": 57,
            "protein100": 0.4,
            "carbs100": 15,
            "fat100": 0.1,
        }
    ],
    "confidence": 0.8,
    "assumptions": [],
    "clarification": None,
}


def reply(_: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(MEAL)}}],
            "usage": {"prompt_tokens": 2000, "completion_tokens": 100},
        },
    )


@pytest.fixture()
def client():
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(reply)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as c:
        reset_database()
        create_user("alvaro", is_admin=True)
        yield c
    app.dependency_overrides.clear()


def user_by_name(client, name):
    return next(u for u in client.get("/api/admin/users").json()["users"] if u["username"] == name)


def test_solicitar_aprobar_y_usar(client):
    client.cookies.clear()
    assert (
        client.post("/api/auth/register", json={"username": "lucia", "password": PASSWORD}).json()["status"]
        == "received"
    )
    login(client, "lucia")
    assert client.post("/api/meals/resolve", json={"text": "una pera"}).status_code == 403

    login(client, "alvaro")
    overview = client.get("/api/admin/overview").json()
    assert overview["pending"] == 1
    users = client.get("/api/admin/users").json()["users"]
    assert users[0]["username"] == "lucia" and users[0]["status"] == "pending"  # pendientes, primero
    assert client.post(f"/api/admin/users/{users[0]['id']}/approve").json() == {"ok": True}
    assert client.get("/api/admin/overview").json()["pending"] == 0

    login(client, "lucia")
    r = client.post("/api/meals/resolve", json={"text": "una pera"})
    assert r.status_code == 200 and r.json()["status"] == "ai"
    login(client, "alvaro")
    lucia = user_by_name(client, "lucia")
    assert lucia["today"]["ai"] == 1 and lucia["today"]["prompt_tokens"] == 2000
    assert lucia["today"]["cost"] == pytest.approx(2000 / 1e6 * 0.95 + 100 / 1e6 * 4.0)
    assert client.get("/api/admin/overview").json()["today"]["ai"] == 1


def test_bloqueo_inmediato_y_desbloqueo(client):
    lucia_id = create_user("lucia")
    login(client, "lucia")
    assert client.get("/api/stats").status_code == 200
    cookie = dict(client.cookies)

    login(client, "alvaro")
    client.post(f"/api/admin/users/{lucia_id}/suspend")
    client.cookies.clear()
    client.cookies.update(cookie)  # la sesión que Lucía ya tenía abierta
    blocked = client.get("/api/stats")
    assert blocked.status_code == 403 and blocked.json()["code"] == "account_suspended"
    assert client.get("/api/auth/status").json()["status"] == "suspended"

    login(client, "alvaro")
    client.post(f"/api/admin/users/{lucia_id}/unsuspend")
    client.cookies.clear()
    client.cookies.update(cookie)
    assert client.get("/api/stats").status_code == 200


def test_cerrar_todas_sus_sesiones(client):
    lucia_id = create_user("lucia")
    login(client, "lucia")
    cookie = dict(client.cookies)
    login(client, "alvaro")
    assert client.post(f"/api/admin/users/{lucia_id}/logout-all").json()["closed"] == 1
    client.cookies.clear()
    client.cookies.update(cookie)
    assert client.get("/api/stats").status_code == 401


def test_rechazar_y_eliminar(client):
    pending_id = create_user("pendiente", status="pending")
    active_id = create_user("activa")
    login(client, "activa")
    client.put("/api/weight", json={"date": "2026-09-30", "kg": 70})
    login(client, "alvaro")
    assert client.post(f"/api/admin/users/{active_id}/reject").status_code == 409  # solo pendientes
    assert client.post(f"/api/admin/users/{pending_id}/reject").json() == {"ok": True}
    assert client.post(f"/api/admin/users/{active_id}/delete", json={"confirm": "otra"}).status_code == 422
    assert client.post(f"/api/admin/users/{active_id}/delete", json={"confirm": "activa"}).json() == {"ok": True}
    names = [u["username"] for u in client.get("/api/admin/users").json()["users"]]
    assert names == ["alvaro"]
    from app import tenancy
    from app.db import SessionLocal
    from app.models import Weight

    with SessionLocal() as db, tenancy.unscoped(db):
        assert db.query(Weight).count() == 0  # sus datos se fueron con la cuenta


def test_el_admin_no_puede_bloquearse_ni_borrarse(client):
    login(client, "alvaro")
    me = user_by_name(client, "alvaro")
    assert client.post(f"/api/admin/users/{me['id']}/suspend").status_code == 409
    assert client.post(f"/api/admin/users/{me['id']}/delete", json={"confirm": "alvaro"}).status_code == 409
    assert client.post(f"/api/admin/users/{me['id']}/reject").status_code == 409
    assert user_by_name(client, "alvaro")["status"] == "approved"


def test_limites_por_usuario_desde_el_panel(client):
    lucia_id = create_user("lucia")
    login(client, "alvaro")
    r = client.patch(f"/api/admin/users/{lucia_id}/limits", json={"ai_daily_limit": 1, "stt_daily_limit": 0}).json()
    assert r["limits"] == {"ai": 1, "stt": 0}
    login(client, "lucia")
    assert client.post("/api/meals/resolve", json={"text": "una pera"}).status_code == 200
    assert client.post("/api/meals/resolve", json={"text": "dos peras"}).status_code == 429
    audio = client.post("/api/transcribe", files={"audio": ("a.webm", b"0" * 2000, "audio/webm")})
    assert audio.status_code == 429
    login(client, "alvaro")
    client.patch(f"/api/admin/users/{lucia_id}/limits", json={"ai_daily_limit": None})
    assert user_by_name(client, "lucia")["limits"]["ai"] == get_settings().ai_user_daily_limit


def test_pausar_ia_y_cerrar_registro(client):
    login(client, "alvaro")
    assert client.patch("/api/admin/settings", json={"ai_paused": True, "signup_open": False}).json() == {
        "ai_paused": True,
        "signup_open": False,
    }
    assert client.post("/api/meals/resolve", json={"text": "una pera"}).json()["code"] == "paused"
    client.cookies.clear()
    assert client.post("/api/auth/register", json={"username": "lucia", "password": PASSWORD}).status_code == 403
    login(client, "alvaro")
    assert client.get("/api/admin/overview").json()["signup"]["state"] == "closed"


def test_auditoria_de_cada_accion(client):
    lucia_id = create_user("lucia", status="pending")
    login(client, "alvaro")
    client.post(f"/api/admin/users/{lucia_id}/approve")
    client.patch(f"/api/admin/users/{lucia_id}/limits", json={"ai_daily_limit": 3})
    client.post(f"/api/admin/users/{lucia_id}/suspend")
    client.patch("/api/admin/settings", json={"ai_paused": True})
    entries = client.get("/api/admin/audit").json()["entries"]
    assert [e["action"] for e in entries] == ["settings", "suspend", "limits", "approve"]
    assert all(e["admin"] == "alvaro" for e in entries)
    assert entries[2]["target"] == "lucia" and entries[2]["details"] == {"ai_daily_limit": 3}
    # Un usuario normal no ve nada de esto.
    login(client, "lucia")
    assert client.get("/api/admin/audit").status_code == 403
