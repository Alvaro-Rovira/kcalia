import json

import pytest

from app.ai import AiMeal, check_consistency, extract_json, parse_meal

VALID = {
    "name": "Yogur",
    "items": [
        {
            "name": "Yogur Griego ",
            "qty": 1,
            "unit": "pieza",
            "grams": 125,
            "kcal": 150,
            "protein": 7.5,
            "carbs": 5,
            "fat": 11.25,
        }
    ],
    "confidence": 0.9,
    "assumptions": [],
    "clarification": None,
}


def test_extrae_json_con_texto_alrededor():
    assert extract_json('Claro:\n```json\n{"a": 1}\n```\n¡Listo!') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("sin json")


def test_valida_y_limpia():
    meal = parse_meal(json.dumps(VALID))
    assert meal.items[0].name == "yogur griego"
    assert meal.items[0].fat == 11.2 or meal.items[0].fat == 11.3


@pytest.mark.parametrize("patch", [{"grams": 0}, {"kcal": -5}, {"protein": 9999}, {"name": ""}])
def test_rechaza_valores_imposibles(patch):
    broken = {**VALID, "items": [{**VALID["items"][0], **patch}]}
    with pytest.raises(ValueError):
        parse_meal(json.dumps(broken))


def test_rechaza_vacio_sin_aclaracion():
    with pytest.raises(ValueError):
        parse_meal(json.dumps({**VALID, "items": []}))
    assert parse_meal(json.dumps({**VALID, "items": [], "clarification": "¿Qué era?"})).clarification == "¿Qué era?"


def test_corrige_calorias_incoherentes_con_los_macros():
    meal = AiMeal.model_validate({**VALID, "items": [{**VALID["items"][0], "kcal": 40}]})
    fixed = check_consistency(meal)
    assert fixed.items[0].kcal == pytest.approx(4 * 7.5 + 4 * 5 + 9 * 11.2, abs=1)
    assert fixed.confidence <= 0.6


def test_el_alcohol_puede_superar_los_macros():
    beer = {
        "name": "cerveza",
        "qty": 330,
        "unit": "ml",
        "grams": 330,
        "kcal": 142,
        "protein": 1.3,
        "carbs": 11.9,
        "fat": 0,
    }
    meal = check_consistency(AiMeal.model_validate({**VALID, "items": [beer]}))
    assert meal.items[0].kcal == 142 and meal.confidence == 0.9


def test_las_fotos_pueden_usar_otro_proveedor():
    import httpx

    from app.ai import AiClient
    from app.config import Settings

    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((str(request.url), request.headers["authorization"], body["model"]))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID)}}], "usage": {}})

    settings = Settings(
        _env_file=None,
        ai_base_url="https://texto.example/v1",
        ai_api_key="clave-texto",
        ai_model="modelo-texto",
        ai_vision_base_url="https://fotos.example/v1",
        ai_vision_api_key="clave-fotos",
        ai_vision_model="modelo-fotos",
    )
    client = AiClient(settings, http=httpx.Client(transport=httpx.MockTransport(handler)))
    client.analyze_text("un yogur")
    client.analyze_photo(b"\xff\xd8\xff", "image/jpeg")
    assert seen[0] == ("https://texto.example/v1/chat/completions", "Bearer clave-texto", "modelo-texto")
    assert seen[1] == ("https://fotos.example/v1/chat/completions", "Bearer clave-fotos", "modelo-fotos")


def test_las_fotos_heredan_la_configuracion_del_texto():
    from app.config import Settings

    settings = Settings(_env_file=None, ai_base_url="https://a.example/v1", ai_api_key="k", ai_model="m")
    assert (settings.vision_base_url, settings.vision_api_key, settings.vision_model) == (
        "https://a.example/v1",
        "k",
        "m",
    )
