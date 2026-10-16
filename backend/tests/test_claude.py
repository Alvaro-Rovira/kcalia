"""Proveedor Claude (SDK oficial de Anthropic): parámetros, salida JSON con esquema, fotos, claves y errores.

Se simula el cliente del SDK; la llamada real se mide con `python -m app.bench --model claude-haiku-5-5`.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.ai import (
    LABEL_SCHEMA,
    MEAL_SCHEMA,
    PLAN_SCHEMA,
    SUGGEST_SCHEMA,
    AiClient,
    AiError,
    claude_message,
)
from app.config import Settings

ITEM = {"name": "huevo cocido", "food": "huevo", "prep": "cocido", "qty": 2, "unit": "pieza", "grams": 100,
        "kcal100": 134, "protein100": 12.5, "carbs100": 0.5, "fat100": 9, "fiber100": 0, "alcohol100": 0}  # fmt: skip
MEAL = {"name": "Huevos", "items": [ITEM], "confidence": 0.9, "assumptions": [], "clarification": None}


def reply(payload, *, stop="end_turn", text=None):
    content = [
        SimpleNamespace(type="thinking", thinking="", signature="firma"),
        SimpleNamespace(type="text", text=text if text is not None else json.dumps(payload)),
    ]
    return SimpleNamespace(
        content=content, stop_reason=stop, usage=SimpleNamespace(input_tokens=3000, output_tokens=150)
    )


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.replies.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make(replies, **settings):
    base = {"ai_model": "claude-haiku-5-5", "anthropic_api_key": "sk-ant-prueba", "ai_api_key": "clave-kimi"}
    fake = SimpleNamespace(messages=FakeMessages(replies))
    client = AiClient(Settings(_env_file=None, **{**base, **settings}), claude=fake)
    return client, fake.messages


def test_text_meal_goes_to_claude_with_the_json_schema_and_no_sampling_params():
    client, api = make([reply(MEAL)])
    meal, usage = client.analyze_text("2 huevos cocidos")
    call = api.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"].startswith("Eres un dietista-nutricionista")
    assert call["messages"] == [{"role": "user", "content": "Comida: 2 huevos cocidos"}]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": MEAL_SCHEMA}
    assert call["thinking"] == {"type": "disabled"}  # sin AI_EFFORT: igual que Kimi, sin razonamiento
    assert "temperature" not in call and "top_p" not in call
    assert meal.items[0].kcal == 134 and meal.items[0].grams == 100  # el código hace la cuenta por 100 g
    assert usage == {"calls": 1, "prompt_tokens": 3000, "completion_tokens": 150}


def test_effort_turns_on_adaptive_thinking_with_room_for_it():
    client, api = make([reply(MEAL)], ai_effort="low")
    client.analyze_text("2 huevos")
    call = api.calls[0]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["effort"] == "low"
    assert call["max_tokens"] >= 8000


def test_photo_becomes_a_base64_image_block():
    client, api = make([reply(MEAL)])
    client.analyze_photo(b"\x89PNG\r\n\x1a\nimagen", "image/png", note="dos huevos")
    content = api.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64" and content[0]["source"]["media_type"] == "image/png"
    assert content[1]["type"] == "text" and "dos huevos" in content[1]["text"]


def test_claude_message_keeps_plain_text_and_converts_data_uris():
    assert claude_message({"role": "user", "content": "hola"}) == {"role": "user", "content": "hola"}
    converted = claude_message(
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}}]}
    )
    assert converted["content"][0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"},
    }


def test_vision_model_can_be_claude_while_text_stays_on_kimi():
    client, api = make([reply(MEAL)], ai_model="kimi-k2.6", ai_vision_model="claude-haiku-5-5")
    client.analyze_photo(b"\xff\xd8\xffimagen", "image/jpeg")
    assert api.calls[0]["model"] == "claude-haiku-5-5"


def test_uses_the_anthropic_key_and_says_so_when_it_is_missing():
    client, _ = make([], anthropic_api_key="")
    assert not client.configured
    with pytest.raises(AiError) as error:
        client.analyze_text("2 huevos")
    assert error.value.code == "no_key"
    client, _ = make([reply(MEAL)])
    assert client.configured


def test_invalid_answer_gets_one_correction_turn_ending_in_a_user_message():
    bad = {**MEAL, "items": [{**ITEM, "kcal100": 1340}]}  # kcal del total en vez de por 100 g
    client, api = make([reply(bad), reply(MEAL)])
    meal, usage = client.analyze_text("2 huevos")
    assert meal.items[0].kcal == 134 and usage["calls"] == 2
    retry = api.calls[1]["messages"]
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    assert "no cumple el esquema" in retry[-1]["content"]


def test_refusal_is_reported_without_retrying():
    client, api = make([reply(None, stop="refusal", text="")])
    with pytest.raises(AiError) as error:
        client.analyze_text("2 huevos")
    assert error.value.code == "refused" and len(api.calls) == 1


def _status_error(cls, status: int, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request, json={"error": {"message": message}})
    return cls(message, response=response, body={"error": {"message": message}})


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"), "auth"),
        (_status_error(anthropic.RateLimitError, 429, "rate limited"), "rate"),
        (_status_error(anthropic.BadRequestError, 400, "Your credit balance is too low"), "quota"),
        (_status_error(anthropic.InternalServerError, 529, "overloaded"), "upstream"),
        (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), "timeout"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "network"),
    ],
)
def test_sdk_errors_become_the_usual_messages(error, code):
    client, _ = make([error])
    with pytest.raises(AiError) as raised:
        client.analyze_text("2 huevos")
    assert raised.value.code == code


def _check_strict(schema: dict, path: str = "$") -> None:
    """Lo que exige la salida estructurada: objetos cerrados, todo obligatorio y sin límites numéricos."""
    for option in schema.get("anyOf", []):
        _check_strict(option, path)
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, path
        assert sorted(schema["required"]) == sorted(schema["properties"]), path
        for name, sub in schema["properties"].items():
            _check_strict(sub, f"{path}.{name}")
    if schema.get("type") == "array":
        _check_strict(schema["items"], f"{path}[]")
    for banned in ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
        assert banned not in schema, f"{path}: {banned}"


@pytest.mark.parametrize("schema", [MEAL_SCHEMA, LABEL_SCHEMA, PLAN_SCHEMA, SUGGEST_SCHEMA])
def test_schemas_follow_the_structured_output_rules(schema):
    _check_strict(schema)


def test_label_plan_and_suggestions_also_use_their_schemas():
    label = {"is_label": True, "name": "Yogur", "short_name": "yogur", "basis": "g", "kcal100": 60,
             "energy_kj100": None, "protein100": 4, "carbs100": 6, "fat100": 2, "fiber100": None, "sugars100": 6,
             "salt100": 0.1, "serving_g": 125, "serving_label": "yogur", "per_serving": None, "confidence": 0.9,
             "notes": []}  # fmt: skip
    plan = {"meals": [{"date": "2026-10-16", "slot": "cena", "name": "Huevos", "items": [ITEM]}]}
    ideas = {"ideas": [{"name": "Huevos", "items": [ITEM]}]}
    client, api = make([reply(label), reply(plan), reply(ideas)])
    client.analyze_label(b"\xff\xd8\xffimagen", "image/jpeg")
    client.suggest_plan("rellena la cena")
    client.suggest_close("me quedan 300 kcal")
    schemas = [call["output_config"]["format"]["schema"] for call in api.calls]
    assert schemas == [LABEL_SCHEMA, PLAN_SCHEMA, SUGGEST_SCHEMA]
