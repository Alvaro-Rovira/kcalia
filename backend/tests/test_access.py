"""Control de acceso de TODAS las rutas registradas en la app.

Si alguien añade una ruta y queda accesible sin una cuenta aprobada, esta prueba falla. Las únicas rutas públicas
permitidas son health, login, registro, la sesión actual y cerrar sesión.
"""

import re

import pytest
from conftest import create_user, login, reset_database
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.deps import PUBLIC_API_PATHS
from app.main import app

ALLOWED_PUBLIC = {"/api/health", "/api/auth/login", "/api/auth/register", "/api/auth/status", "/api/auth/logout"}
SAMPLE_PARAMS = {"date": "2026-09-21", "client_id": "cid-000000001", "rest": "no-existe"}


def registered_routes():
    """(ruta, métodos) de todo lo registrado, también dentro de los routers incluidos."""
    for route in app.routes:
        if isinstance(route, APIRoute):
            yield route.path, route.methods
        elif hasattr(route, "effective_route_contexts"):  # routers incluidos (FastAPI ≥ 0.140)
            for context in route.effective_route_contexts():
                if isinstance(context.original_route, APIRoute):
                    yield context.path, context.original_route.methods


def api_routes() -> list[tuple[str, str]]:
    """(método, URL de ejemplo) de cada ruta /api, con los parámetros de ruta rellenos."""
    found = set()
    for path, methods in registered_routes():
        if not path.startswith("/api"):
            continue
        url = re.sub(r"\{(\w+)(:[^}]*)?\}", lambda m: SAMPLE_PARAMS.get(m.group(1), "1"), path)
        for method in methods:
            found.add((method, url))
    return sorted(found)


ROUTES = api_routes()
PROTECTED = [(m, u) for m, u in ROUTES if u not in ALLOWED_PUBLIC]


def call(client: TestClient, method: str, url: str):
    if method in ("POST", "PUT", "PATCH"):
        return client.request(method, url, json={})
    return client.request(method, url)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        reset_database()
        create_user("admin", is_admin=True)
        create_user("pendiente", status="pending")
        create_user("bloqueada", status="suspended")
        create_user("normal")
        yield c


def test_solo_son_publicas_las_rutas_permitidas():
    assert PUBLIC_API_PATHS == ALLOWED_PUBLIC
    paths = {url for _, url in ROUTES}
    assert ALLOWED_PUBLIC <= paths
    assert len(PROTECTED) > 40  # si esto baja de golpe, la enumeración de rutas ha dejado de funcionar


@pytest.mark.parametrize(("method", "url"), PROTECTED, ids=[f"{m} {u}" for m, u in PROTECTED])
def test_ruta_protegida_rechaza_anonimo_pendiente_y_bloqueado(client, method, url):
    client.cookies.clear()
    assert call(client, method, url).status_code == 401, "anónimo"
    for username, code in (("pendiente", "account_pending"), ("bloqueada", "account_suspended")):
        login(client, username)
        response = call(client, method, url)
        assert response.status_code == 403, username
        if method != "HEAD":
            assert response.json()["code"] == code


ADMIN_ROUTES = [(m, u) for m, u in PROTECTED if u.startswith("/api/admin")]


@pytest.mark.parametrize(("method", "url"), ADMIN_ROUTES, ids=[f"{m} {u}" for m, u in ADMIN_ROUTES])
def test_administracion_solo_para_el_admin(client, method, url):
    login(client, "normal")
    assert call(client, method, url).status_code == 403


def test_cuenta_pendiente_solo_ve_su_estado_y_puede_salir(client):
    login(client, "pendiente")
    status = client.get("/api/auth/status").json()
    assert status["authenticated"] is True and status["status"] == "pending"
    assert client.get("/api/bootstrap").status_code == 403
    assert client.post("/api/meals/resolve", json={"text": "dos huevos"}).status_code == 403
    assert client.post("/api/transcribe", files={"audio": ("a.webm", b"0" * 2000, "audio/webm")}).status_code == 403
    assert client.post("/api/products/scan", files={"image": ("e.jpg", b"0" * 2000, "image/jpeg")}).status_code == 403
    assert client.post("/api/auth/logout").json() == {"ok": True}
    assert client.get("/api/auth/status").json()["authenticated"] is False
