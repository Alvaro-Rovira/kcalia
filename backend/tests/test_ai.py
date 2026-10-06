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


def _item(**extra):
    base = {
        "name": "huevo",
        "qty": 2,
        "unit": "pieza",
        "grams": 110,
        "kcal100": 143,
        "protein100": 12.6,
        "carbs100": 0.7,
        "fat100": 9.5,
    }
    return {**base, **extra}


def _meal(*items):
    return json.dumps(
        {"name": "Huevos", "items": list(items), "confidence": 0.9, "assumptions": [], "clarification": None}
    )


def test_los_totales_los_calcula_el_codigo_a_partir_de_los_valores_por_100_g():
    """Regresión: con la clave real, dos huevos salieron como 314 kcal (el modelo escaló dos veces)."""
    meal = parse_meal(_meal(_item()))
    egg = meal.items[0]
    assert (egg.kcal, egg.protein, egg.carbs, egg.fat) == (157.3, 13.9, 0.8, 10.5)


def test_un_modelo_que_devuelve_totales_sigue_funcionando():
    legacy = {
        "name": "yogur",
        "qty": 1,
        "unit": "pieza",
        "grams": 125,
        "kcal": 150,
        "protein": 7.5,
        "carbs": 5,
        "fat": 11.3,
    }
    assert parse_meal(_meal(legacy)).items[0].kcal == 150


@pytest.mark.parametrize(
    "bad",
    [
        {"kcal100": 1400},  # son kcal del total, no por 100 g
        {"protein100": 60, "carbs100": 40, "fat100": 30},  # suman más de 100 g
        {"kcal100": -3},
        {"grams": 0},
    ],
)
def test_valores_por_100_g_imposibles_se_rechazan_para_pedir_correccion(bad):
    with pytest.raises(ValueError):
        parse_meal(_meal(_item(**bad)))


def test_un_alimento_repetido_se_junta_en_uno():
    oil = {
        "name": "aceite de oliva",
        "qty": 5,
        "unit": "g",
        "grams": 5,
        "kcal100": 884,
        "protein100": 0,
        "carbs100": 0,
        "fat100": 100,
    }
    other = {**oil, "qty": 3, "grams": 3}
    merged = parse_meal(_meal(_item(), oil, other))
    assert [i.name for i in merged.items] == ["huevo", "aceite de oliva"]
    aceite = merged.items[1]
    assert (aceite.grams, aceite.qty, aceite.kcal, aceite.fat) == (8, 8, 70.7, 8)


def test_juntar_con_unidades_distintas_deja_los_gramos():
    a = {
        "name": "aceite de oliva",
        "qty": 1,
        "unit": "cda",
        "grams": 10,
        "kcal100": 884,
        "protein100": 0,
        "carbs100": 0,
        "fat100": 100,
    }
    b = {**a, "qty": 5, "unit": "g", "grams": 5}
    oil = parse_meal(_meal(a, b)).items[0]
    assert (oil.unit, oil.grams, oil.qty) == ("g", 15, 15)


def test_fibra_y_alcohol_opcionales_y_compatibles_con_respuestas_antiguas():
    # Sin los campos nuevos (respuestas y cachés de antes): siguen valiendo y quedan vacíos.
    egg = parse_meal(_meal(_item())).items[0]
    assert egg.fiber is None and egg.alcohol is None
    lentils = _item(
        name="lentejas", grams=300, kcal100=116, protein100=9, carbs100=20, fat100=0.4, fiber100=7.9, alcohol100=0
    )
    item = parse_meal(_meal(lentils)).items[0]
    assert item.fiber == pytest.approx(23.7) and item.alcohol is None


def test_cerveza_con_alcohol_no_se_corrige():
    beer = _item(
        name="cerveza",
        qty=200,
        unit="ml",
        grams=200,
        kcal100=43,
        protein100=0.4,
        carbs100=3.6,
        fat100=0,
        alcohol100=3.9,
    )
    meal = parse_meal(_meal(beer))
    assert meal.items[0].alcohol == pytest.approx(7.8) and meal.items[0].kcal == 86
    assert meal.confidence == 0.9  # 4·0,4 + 4·3,6 + 7·3,9 = 43: coherente, sin ajustes


@pytest.mark.parametrize("bad", [{"alcohol100": 70}, {"fiber100": -1}, {"fiber100": "mucha"}])
def test_fibra_o_alcohol_imposibles_se_rechazan(bad):
    with pytest.raises(ValueError):
        parse_meal(_meal(_item(**bad)))
