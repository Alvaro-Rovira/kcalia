"""Foto de una comida con la descripción de quien la comió: la IA recibe las dos y manda la descripción."""

import json

import httpx
import pytest
from conftest import create_user, login, reset_database
from fastapi.testclient import TestClient

from app.ai import AiClient
from app.config import get_settings
from app.deps import get_ai_client
from app.main import app

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
AI_MEAL = {
    "name": "Pechuga con arroz",
    "items": [
        {
            "name": "pechuga de pollo",
            "qty": 1,
            "unit": "pieza",
            "grams": 180,
            "kcal": 297,
            "protein": 55.8,
            "carbs": 0,
            "fat": 6.5,
        },
        {
            "name": "arroz blanco cocido",
            "qty": 1,
            "unit": "racion",
            "grams": 200,
            "kcal": 260,
            "protein": 5.4,
            "carbs": 56,
            "fat": 0.6,
        },
    ],
    "confidence": 0.6,
    "assumptions": ["Ración vista en la foto"],
    "clarification": None,
}
DESCRIPTION = (
    "Pechuga de pollo a la plancha con arroz blanco. Debajo del arroz había dos cucharadas de aceite de oliva "
    "y una salsa de yogur que no se ve en la foto. La pechuga era grande, de unos 200 gramos en crudo, y el arroz "
    "era una ración normal. De postre, aunque no sale, me tomé un yogur natural sin azúcar y un café con leche "
    "desnatada. Todo comido en casa, sin pan."
)


class FakeAi:
    def __init__(self):
        self.bodies: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(AI_MEAL)}}], "usage": {"prompt_tokens": 900}},
        )


@pytest.fixture()
def fake_ai():
    return FakeAi()


@pytest.fixture()
def client(fake_ai):
    ai = AiClient(get_settings(), http=httpx.Client(transport=httpx.MockTransport(fake_ai.handler)))
    app.dependency_overrides[get_ai_client] = lambda: ai
    with TestClient(app) as c:
        reset_database()
        create_user("alvaro", is_admin=True)
        login(c, "alvaro")
        yield c
    app.dependency_overrides.clear()


def send_photo(client, description: str):
    return client.post(
        "/api/meals/photo", files={"image": ("comida.jpg", JPEG, "image/jpeg")}, data={"note": description}
    )


def test_la_ia_recibe_la_foto_y_la_descripcion_completa(client, fake_ai):
    assert len(DESCRIPTION) > 300  # antes se cortaba en 300; cabe entera (600, como el cuadro de texto)
    r = send_photo(client, DESCRIPTION)
    assert r.status_code == 200, r.text
    assert len(fake_ai.bodies) == 1
    content = fake_ai.bodies[0]["messages"][-1]["content"]
    assert any(part["type"] == "image_url" for part in content)
    prompt = next(part["text"] for part in content if part["type"] == "text")
    assert DESCRIPTION in prompt
    assert "manda la descripción" in prompt  # lo que no se ve o no cuadra lo decide quien la comió


def test_sin_descripcion_solo_la_foto(client, fake_ai):
    assert send_photo(client, "").status_code == 200
    prompt = next(part["text"] for part in fake_ai.bodies[0]["messages"][-1]["content"] if part["type"] == "text")
    assert "Descripción" not in prompt


def test_la_comida_se_guarda_con_la_descripcion_y_se_recuerda(client, fake_ai):
    draft = send_photo(client, "pechuga con arroz").json()["draft"]
    assert draft["source"] == "photo" and draft["text"] == "pechuga con arroz"
    body = {
        "client_id": "foto-descripcion-1",
        "date": "2026-10-07",
        "slot": "comida",
        "name": draft["name"],
        "text": draft["text"],
        "items": draft["items"],
        "source": draft["source"],
    }
    assert client.post("/api/meals", json=body).status_code == 201
    calls = len(fake_ai.bodies)
    again = client.post("/api/meals/resolve", json={"text": "pechuga con arroz"}).json()
    assert again["status"] == "exact" and len(fake_ai.bodies) == calls  # la próxima vez, del historial y sin IA
