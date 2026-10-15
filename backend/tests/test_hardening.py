"""Refuerzos de seguridad: bloqueo de cuentas provocado, SSRF en push, tamaño de las peticiones, cabeceras, imágenes
falsas y fórmulas en los CSV."""

import csv
import io

import pytest
from conftest import PASSWORD, create_user, login, reset_database
from fastapi.testclient import TestClient

from app import security
from app.main import app
from app.webpush import push_endpoint_allowed

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def client_from(ip: str) -> TestClient:
    return TestClient(app, client=(ip, 50000))


@pytest.fixture()
def fresh():
    reset_database()
    security.login_throttle._failures.clear()
    security.user_throttle._failures.clear()
    security.known_logins.clear()
    create_user("victima")
    yield


def _fail(ip: str, username: str = "victima") -> int:
    with client_from(ip) as c:
        return c.post("/api/auth/login", json={"username": username, "password": "no-es-la-clave"}).status_code


def _login(ip: str) -> int:
    with client_from(ip) as c:
        return c.post("/api/auth/login", json={"username": "victima", "password": PASSWORD}).status_code


def test_distributed_failures_do_not_lock_the_owner_out_of_a_known_connection(fresh):
    assert _login("10.0.0.1") == 200  # su conexión habitual
    for n in range(40):
        _fail(f"203.0.113.{n}")
    assert _login("10.0.0.1") == 200


def test_distributed_failures_only_slow_down_new_connections_for_a_few_minutes(fresh):
    for n in range(40):
        _fail(f"203.0.113.{n}")
    assert _login("198.51.100.7") == 429
    assert security.user_throttle.retry_after("user:victima") <= 300


def test_bruteforce_from_one_connection_is_still_blocked(fresh):
    for _ in range(5):
        assert _fail("192.0.2.9") == 401
    assert _fail("192.0.2.9") == 429
    assert _login("192.0.2.9") == 429


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc123",
        "https://updates.push.services.mozilla.com/wpush/v2/gAAAA",
        "https://web.push.apple.com/QGuQyavXutnMH",
        "https://wns2-par02p.notify.windows.com/w/?token=BQYAAA",
    ],
)
def test_real_push_services_are_allowed(endpoint):
    assert push_endpoint_allowed(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8000/admin",
        "https://localhost/x",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.5/push",
        "https://fcm.googleapis.com.evil.example/x",
        "https://evil.example/fcm.googleapis.com",
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://user@fcm.googleapis.com:8443/x",
    ],
)
def test_other_push_endpoints_are_rejected(endpoint):
    assert not push_endpoint_allowed(endpoint)


@pytest.fixture()
def user_client():
    reset_database()
    create_user("ana")
    with TestClient(app) as c:
        login(c, "ana")
        yield c


def test_push_subscription_to_an_internal_address_is_refused(user_client):
    body = {"endpoint": "https://127.0.0.1:8000/x", "keys": {"p256dh": "a" * 87, "auth": "b" * 22}}
    assert user_client.post("/api/push/subscribe", json=body).status_code == 422


def test_huge_json_body_is_refused_without_reading_it():
    with TestClient(app) as c:
        big = '{"username": "x", "password": "' + "a" * (2 * 1024 * 1024) + '"}'
        r = c.post("/api/auth/login", content=big, headers={"Content-Type": "application/json"})
        assert r.status_code == 413


def test_security_headers():
    with TestClient(app) as c:
        headers = c.get("/api/health").headers
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "payment=()" in headers["Permissions-Policy"]
    assert headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_a_file_that_is_not_an_image_is_refused(user_client):
    fake = b"<html><script>alert(1)</script></html>" + b" " * 2000
    r = user_client.post(
        "/api/photos",
        files={"image": ("a.png", fake, "image/png")},
        data={"date": "2026-10-01", "client_id": "foto-00001"},
    )
    assert r.status_code == 415


def test_image_type_is_taken_from_its_bytes(user_client):
    r = user_client.post(
        "/api/photos",
        files={"image": ("a.jpg", PNG, "image/jpeg")},
        data={"date": "2026-10-01", "client_id": "foto-00002"},
    )
    assert r.status_code == 201, r.text
    image = user_client.get(f"/api/photos/{r.json()['id']}/image")
    assert image.headers["content-type"] == "image/png"


def test_csv_exports_neutralise_formulas(user_client):
    item = {"name": "=HYPERLINK(\"http://evil\")", "qty": 1, "unit": "g", "grams": 100, "kcal": 100, "protein": 1,
            "carbs": 1, "fat": 1, "manual": True}  # fmt: skip
    body = {"client_id": "csv-0001", "date": "2026-10-01", "slot": "cena", "name": "@SUM(A1)", "text": "+1",
            "items": [item], "source": "manual", "dish_id": None}  # fmt: skip
    assert user_client.post("/api/meals", json=body).status_code == 201
    text = user_client.get("/api/export/meals.csv").content.decode("utf-8-sig")
    cells = [cell for row in csv.reader(io.StringIO(text), delimiter=";") for cell in row]
    assert "'@SUM(A1)" in cells
    assert not any(cell.startswith(("=", "+", "@")) for cell in cells)
