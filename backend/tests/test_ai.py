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


def test_la_transcripcion_no_lleva_texto_guia():
    """Whisper copiaba la guía cuando el audio no era claro: registraba comida que nadie dijo."""
    import httpx

    from app.ai import transcribe
    from app.config import Settings

    sent: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.content
        sent["url"] = str(request.url).encode()
        return httpx.Response(200, json={"text": " un plato de lentejas "})

    settings = Settings(_env_file=None, stt_base_url="http://voz.example/v1", stt_model="small")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert transcribe(settings, b"audio", "a.webm", "audio/webm", http=client) == "un plato de lentejas"
    assert sent["url"] == b"http://voz.example/v1/audio/transcriptions"
    assert b'name="language"' in sent["body"] and b'name="file"' in sent["body"]
    assert b'name="prompt"' not in sent["body"]


def test_transcripcion_vacia_o_con_error_da_mensaje_claro():
    import httpx

    from app.ai import AiError, transcribe
    from app.config import Settings

    settings = Settings(_env_file=None, stt_base_url="http://voz.example/v1")
    for response, code in (
        (httpx.Response(200, json={"text": "  "}), "stt_empty"),
        (httpx.Response(422, json={}), "stt_error"),
    ):
        client = httpx.Client(transport=httpx.MockTransport(lambda _, r=response: r))
        with pytest.raises(AiError) as caught:
            transcribe(settings, b"audio", "a.webm", "audio/webm", http=client)
        assert caught.value.code == code


def _client(responses, sleeps):
    import httpx

    from app.ai import AiClient
    from app.config import Settings

    queue = list(responses)
    settings = Settings(_env_file=None, ai_api_key="k", ai_model="modelo")
    http = httpx.Client(transport=httpx.MockTransport(lambda request: queue.pop(0)))
    return AiClient(settings, http=http, sleep=sleeps.append)


def _ok():
    import httpx

    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(VALID)}}], "usage": {}})


def _limit(seconds="1", body=None):
    import httpx

    return httpx.Response(
        429,
        headers={"retry-after": seconds},
        json=body or {"error": {"message": "Organization Rate limit exceeded", "type": "rate_limit_reached_error"}},
    )


def test_un_429_corto_se_reintenta_una_vez_y_sale_bien():
    sleeps: list[float] = []
    meal, _ = _client([_limit("1"), _ok()], sleeps).analyze_text("un yogur")
    assert meal.name == "Yogur" and sleeps == [1.0]


def test_dos_429_seguidos_explican_el_limite_por_minuto():
    from app.ai import AiError

    sleeps: list[float] = []
    with pytest.raises(AiError) as caught:
        _client([_limit("1"), _limit("1")], sleeps).analyze_text("un yogur")
    assert caught.value.code == "rate" and caught.value.status == 503
    assert "por minuto" in caught.value.message and sleeps == [1.0]


def test_una_espera_larga_no_se_bloquea_esperando():
    from app.ai import AiError

    sleeps: list[float] = []
    with pytest.raises(AiError) as caught:
        _client([_limit("40")], sleeps).analyze_text("un yogur")
    assert caught.value.code == "rate" and sleeps == []


def test_429_por_saldo_agotado_se_distingue_del_limite_de_ritmo():
    from app.ai import AiError

    body = {"error": {"message": "Your account balance is insufficient", "type": "exceeded_current_quota_error"}}
    with pytest.raises(AiError) as caught:
        _client([_limit("1", body), _limit("1", body)], []).analyze_text("un yogur")
    assert caught.value.code == "quota" and "saldo" in caught.value.message
