"""Errores 500 en producción: el administrador se entera (push como mucho cada 15 min y lista en el panel)."""

import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app import notify, push, services
from app.main import app


@pytest.fixture()
def sent(monkeypatch):
    notify.reset_errors()
    messages: list[dict] = []
    monkeypatch.setattr(push, "send_to_user", lambda db, user_id, payload: messages.append(payload) or 1)
    yield messages
    notify.reset_errors()


def test_avisa_como_mucho_una_vez_cada_cuarto_de_hora(sent):
    reset_database()
    create_user("admin", is_admin=True)
    now = [1000.0]
    clock = lambda: now[0]  # noqa: E731
    assert notify.server_error("GET", "/api/stats", RuntimeError("x"), clock=clock) is True
    now[0] += 60
    assert notify.server_error("POST", "/api/meals", KeyError("y"), clock=clock) is False
    assert notify.server_error("POST", "/api/meals", KeyError("y"), clock=clock) is False
    now[0] += notify.ERROR_ALERT_EVERY
    assert notify.server_error("GET", "/api/days", ValueError("z"), clock=clock) is True
    assert len(sent) == 2
    assert "RuntimeError" in sent[0]["body"] and "/api/stats" in sent[0]["body"]
    assert "2 más" in sent[1]["body"]  # los que se callaron entre medias
    assert [e["path"] for e in notify.recent_errors()] == ["/api/days", "/api/meals", "/api/meals", "/api/stats"]


def test_el_mensaje_no_lleva_datos_de_nadie(sent):
    reset_database()
    create_user("admin", is_admin=True)
    notify.server_error("POST", "/api/meals", ValueError("pechuga de ana 150 g"), clock=lambda: 1.0)
    assert "pechuga" not in sent[0]["body"] and "ana" not in str(notify.recent_errors())


def test_un_500_real_queda_en_el_panel_solo_para_el_administrador(sent, monkeypatch):
    reset_database()
    create_user("admin", is_admin=True)
    create_user("ana")

    def boom(*_args, **_kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(services, "compute_week", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        login(client, "ana")
        profile = dict(sex="mujer", age=34, height_cm=165, weight_kg=61, activity="ligero", goal="mantenimiento")
        client.put("/api/profile", json=profile)
        assert client.get("/api/summary/week").status_code == 500
        assert client.get("/api/admin/overview").status_code == 403
        login(client, "admin")
        errors = client.get("/api/admin/overview").json()["errors"]
    assert errors["recent"][0]["path"] == "/api/summary/week" and errors["recent"][0]["error"] == "RuntimeError"
    assert len(sent) == 1
