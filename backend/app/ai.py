"""Cliente de IA compatible con OpenAI: texto y foto -> desglose nutricional validado."""

import base64
import json
import logging
import re
import time

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from .config import Settings

log = logging.getLogger("kcalia.ai")

UNIT_ENUM = "g|ml|pieza|cda|cdta|vaso|taza|rebanada|loncha|lata|puñado|plato|racion|bol|cazo"
MAX_OUTPUT_TOKENS = 1500

SYSTEM_PROMPT = f"""Eres un dietista-nutricionista español. Conviertes la descripción de una comida en su \
desglose nutricional. Respondes SOLO con un objeto JSON válido, sin texto alrededor ni bloques de código.

ESQUEMA (todos los campos obligatorios):
{{
  "name": string,            // título corto de la comida, máx. 60 caracteres, sin cantidades
  "items": [                 // un elemento por ingrediente, EN EL MISMO ORDEN en que aparecen en el texto
    {{
      "name": string,        // alimento en minúsculas y singular, con la preparación si cambia los macros ("arroz blanco cocido")
      "qty": number,         // cantidad en la unidad indicada
      "unit": string,        // una de: {UNIT_ENUM}
      "grams": number,       // peso total comestible en gramos (para líquidos, ml ≈ g)
      "kcal": number,
      "protein": number,     // gramos
      "carbs": number,       // gramos de hidratos disponibles
      "fat": number          // gramos
    }}
  ],
  "confidence": number,      // 0 a 1: 0.9+ si hay cantidades explícitas, 0.6-0.8 si has estimado raciones, <0.5 si es muy ambiguo
  "assumptions": [string],   // suposiciones que has hecho, frases cortas en español ("Huevos medianos de 55 g")
  "clarification": string|null  // pregunta breve SOLO si falta información crítica; si no, null
}}

REGLAS
- Fuente de valores: BEDCA (base de datos española) y, si no está, USDA FoodData Central. Alimentos de marca: valores típicos de la etiqueta en España.
- Si no se indica cantidad, usa la ración típica española de la tabla de abajo y anótalo en "assumptions".
- Arroz, pasta y legumbres: si no se dice "en crudo" o "en seco", asume peso ya cocido.
- Carnes y pescados: asume peso cocinado salvo que se diga "en crudo".
- Frito, rebozado, revuelto, salteado, a la plancha: añade el aceite absorbido como ingrediente aparte si el usuario no lo menciona (plancha 3 g, revuelto/salteado 5 g, frito 10 g) y anótalo en "assumptions". Si el usuario menciona aceite sin cantidad, asume 10 g (una cucharada); "un chorrito" son 5 g.
- Las kcal de cada ingrediente deben ser coherentes con 4·proteína + 4·hidratos + 9·grasa (el alcohol aporta 7 kcal/g y es la única excepción).
- No inventes ingredientes que el texto no sugiera. No añadas bebida, pan ni postre por tu cuenta.
- Pide aclaración ("clarification") SOLO si es imposible identificar qué se ha comido ("he comido algo", "lo de siempre"). En ese caso devuelve "items": [] y "confidence": 0. Si solo falta la cantidad, NO preguntes: estima y anótalo.
- Si el texto no describe comida o bebida, devuelve "items": [] y una "clarification" amable.
- Redondea a un decimal. Usa punto decimal en los números.

RACIONES TÍPICAS EN ESPAÑA
huevo M 55 g · rebanada de pan de molde 30 g · tostada de barra 40 g · bocadillo (media barra) 110 g de pan · \
plato de pasta o arroz cocido 280 g · plato de legumbres guisadas 330 g · filete de pollo o ternera 150 g · \
ración de pescado 160 g · hamburguesa 120 g · ensalada mixta 250 g · patata mediana 170 g · \
vaso 200 ml · taza 250 ml · café con leche 200 ml (140 ml de leche) · cortado 60 ml (25 ml de leche) · \
yogur 125 g · loncha de jamón cocido 20 g · loncha de jamón serrano 15 g · loncha de queso 20 g · \
lata pequeña de atún 56 g escurrido · puñado de frutos secos 30 g · pieza de fruta 150 g · plátano 120 g sin piel · \
cucharada sopera 10 g de aceite o 15 g de azúcar/miel · cucharadita 5 g · cazo de proteína 30 g · \
pincho de tortilla 150 g · croqueta 35 g · caña 200 ml · tercio 330 ml · copa de vino 150 ml · onza de chocolate 10 g

VALORES DE REFERENCIA por 100 g (kcal / proteína / hidratos / grasa)
huevo 143/12.6/0.7/9.5 · clara de huevo 52/11/0.7/0.2 · pan blanco 265/9/51/3 · pan integral 250/10/42/3.5 · \
arroz blanco cocido 130/2.7/28/0.3 · arroz crudo 360/7/79/0.7 · pasta cocida 150/5.5/30/0.9 · pasta cruda 360/12.5/72/1.5 · \
patata cocida 86/1.8/19/0.1 · patatas fritas 312/3.4/41/15 · avena en copos 375/13.5/60/7 · \
pechuga de pollo a la plancha 165/31/0/3.6 · pechuga de pollo cruda 112/23/0/2 · muslo de pollo asado 190/25/0/10 · \
ternera magra cocinada 190/28/0/8.5 · lomo de cerdo cocinado 175/27/0/7 · carne picada mixta cocinada 250/24/0/17 · \
salmón cocinado 208/22/0/13 · merluza cocinada 90/18/0/1.8 · atún al natural 110/25/0/1 · atún en aceite escurrido 190/26/0/9 · \
jamón serrano 240/31/0/13 · jamón cocido 110/19/1.5/3 · pavo en lonchas 105/20/1.5/2 · chorizo 450/24/2/38 · \
queso curado 400/25/0.5/33 · queso fresco 175/12/3/13 · queso fresco batido 0% 46/8/3.5/0.2 · mozzarella 280/22/2/20 · \
leche entera 64/3.2/4.7/3.6 · leche semidesnatada 46/3.3/4.8/1.6 · leche desnatada 35/3.4/5/0.2 · bebida de avena 45/1/7/1.5 · \
yogur natural 61/3.5/4.7/3.3 · yogur griego 120/6/4/9 · yogur proteico o skyr 62/10/4/0.2 · \
aceite de oliva 884/0/0/100 · mantequilla 717/0.9/0.1/81 · aguacate 160/2/8.5/14.7 · \
lentejas cocidas 116/9/20/0.4 · garbanzos cocidos 164/8.9/27/2.6 · alubias cocidas 127/8.7/22/0.5 · \
plátano 89/1.1/23/0.3 · manzana 52/0.3/14/0.2 · naranja 47/0.9/12/0.1 · fresas 32/0.7/7.7/0.3 · \
tomate 18/0.9/3.9/0.2 · lechuga 15/1.4/2.9/0.2 · brócoli cocido 35/2.4/7/0.4 · zanahoria 41/0.9/10/0.2 · \
nueces 654/15/14/65 · almendras 579/21/22/50 · crema de cacahuete 590/25/20/50 · \
proteína whey en polvo 380/78/6/5 · azúcar 387/0/100/0 · miel 304/0.3/82/0 · chocolate negro 70% 580/8/35/43 · \
galleta María 440/7/75/12 · tortilla de patatas 190/6.5/12/13 · paella mixta 160/8/20/5 · \
lentejas con chorizo 130/8/13/5 · pizza margarita 250/11/31/9 · croquetas 200/6/20/11 · \
cerveza 43/0.4/3.6/0 · vino tinto 85/0.1/2.6/0 · refresco de cola 42/0/10.6/0 · zumo de naranja 45/0.7/10.4/0.2"""

PHOTO_INSTRUCTIONS = """Analiza la foto de esta comida. Identifica cada alimento visible y estima su peso \
por el tamaño del plato y las proporciones (un plato llano mide unos 26 cm). Añade el aceite o las salsas \
que probablemente lleve. Si la foto no muestra comida o no se distingue, devuelve "items": [] y una \
"clarification" amable. La confianza con foto rara vez supera 0.7."""


class AiError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class AiItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qty: float = Field(default=1, ge=0, le=10000)
    unit: str = Field(default="g", max_length=16)
    grams: float = Field(gt=0, le=5000)
    kcal: float = Field(ge=0, le=6000)
    protein: float = Field(ge=0, le=600)
    carbs: float = Field(ge=0, le=1200)
    fat: float = Field(ge=0, le=600)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("kcal", "protein", "carbs", "fat", "grams", "qty")
    @classmethod
    def _round(cls, value: float) -> float:
        return round(value, 1)


class AiMeal(BaseModel):
    name: str = Field(default="", max_length=160)
    items: list[AiItem] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.7, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    clarification: str | None = None


def check_consistency(meal: AiMeal) -> AiMeal:
    """Corrige kcal claramente incoherentes con los macros (4/4/9)."""
    adjusted = False
    for item in meal.items:
        atwater = 4 * item.protein + 4 * item.carbs + 9 * item.fat
        # Menos kcal de las que suman los macros es imposible; más puede ser alcohol.
        if item.kcal < atwater * 0.8 - 10:
            item.kcal = round(atwater, 1)
            adjusted = True
    if adjusted:
        meal.confidence = round(min(meal.confidence, 0.6), 2)
        meal.assumptions.append("Calorías recalculadas a partir de los macros por coherencia")
    return meal


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(content: str) -> dict:
    text = _FENCE.sub("", content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no hay ningún objeto JSON en la respuesta")
    return json.loads(text[start : end + 1])


def parse_meal(content: str) -> AiMeal:
    meal = AiMeal.model_validate(extract_json(content))
    if not meal.items and not meal.clarification:
        raise ValueError('"items" está vacío y no hay "clarification"')
    return check_consistency(meal)


def _provider_params(model: str) -> dict:
    # Kimi fija la temperatura (0.6 sin razonamiento) y rechaza cualquier otra; el
    # razonamiento se desactiva para ganar rapidez y reducir tokens de salida.
    if model.lower().startswith("kimi"):
        return {"thinking": {"type": "disabled"}, "max_completion_tokens": MAX_OUTPUT_TOKENS}
    return {"temperature": 0.1, "max_tokens": MAX_OUTPUT_TOKENS}


MAX_RETRY_WAIT_SECONDS = 5.0


def _retry_after(resp: httpx.Response) -> float:
    try:
        return max(0.0, float(resp.headers.get("retry-after", "1")))
    except ValueError:
        return 1.0


def _is_quota_error(resp: httpx.Response) -> bool:
    """429 por saldo agotado (no por ritmo de peticiones): cambia lo que hay que decirle al usuario."""
    text = resp.text.lower()
    return any(mark in text for mark in ("quota", "insufficient", "balance", "billing", "credit"))


class AiClient:
    def __init__(self, settings: Settings, http: httpx.Client | None = None, sleep=time.sleep):
        self.settings = settings
        self.http = http or httpx.Client(timeout=settings.ai_timeout)
        self._sleep = sleep

    @property
    def configured(self) -> bool:
        return bool(self.settings.ai_api_key)

    def _post(self, body: dict, *, base_url: str | None = None, api_key: str | None = None) -> dict:
        s = self.settings
        api_key = s.ai_api_key if api_key is None else api_key
        if not api_key:
            raise AiError(
                "no_key",
                "La IA todavía no está configurada en el servidor. Mientras tanto puedes "
                "añadir comidas de tu historial.",
                503,
            )
        url = (base_url or s.ai_base_url).rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = self.http.post(url, json=body, headers=headers)
            if resp.status_code == 400:
                # Proveedores distintos aceptan parámetros distintos: reintento con lo mínimo.
                log.warning("La IA rechazó los parámetros (%s); reintento sin opcionales", resp.text[:300])
                minimal = {"model": body["model"], "messages": body["messages"]}
                resp = self.http.post(url, json=minimal, headers=headers)
            if resp.status_code == 429:
                wait = _retry_after(resp)
                # Una espera corta suele bastar (otra petición nuestra a punto de caducar en la ventana);
                # si el proveedor pide más, no se deja al usuario mirando una rueda: se le explica.
                if wait <= MAX_RETRY_WAIT_SECONDS:
                    log.warning("La IA pidió esperar %.0f s (429): %s", wait, resp.text[:200])
                    self._sleep(wait)
                    resp = self.http.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise AiError("timeout", "La IA ha tardado demasiado en responder. Prueba otra vez.", 504) from exc
        except httpx.HTTPError as exc:
            raise AiError("network", "No he podido conectar con la IA. Inténtalo en un momento.") from exc

        if resp.status_code in (401, 403):
            raise AiError("auth", "La clave de la IA no es válida o ha caducado. Revísala en el servidor.")
        if resp.status_code == 429:
            log.warning("Límite del proveedor de IA (429): %s", resp.text[:300])
            if _is_quota_error(resp):
                raise AiError(
                    "quota",
                    "La cuenta de la IA se ha quedado sin saldo. Recárgala en la consola del proveedor.",
                    503,
                )
            raise AiError(
                "rate",
                "Tu cuenta de IA ha llegado a su límite de peticiones por minuto. "
                "Espera un poco (hasta un minuto) y vuelve a intentarlo.",
                503,
            )
        if resp.status_code >= 400:
            log.error("Error %s de la IA: %s", resp.status_code, resp.text[:500])
            raise AiError("upstream", "La IA ha devuelto un error. Inténtalo de nuevo en un momento.")
        return resp.json()

    def analyze(
        self, user_content: str | list, *, model: str, base_url: str | None = None, api_key: str | None = None
    ) -> tuple[AiMeal, dict]:
        """Devuelve la comida validada y el uso (llamadas y tokens). Un reintento si el JSON falla."""
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        last_error = ""
        for attempt in range(2):
            body = {
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                **_provider_params(model),
            }
            data = self._post(body, base_url=base_url, api_key=api_key)
            usage["calls"] += 1
            reported = data.get("usage") or {}
            usage["prompt_tokens"] += int(reported.get("prompt_tokens") or 0)
            usage["completion_tokens"] += int(reported.get("completion_tokens") or 0)
            try:
                content = data["choices"][0]["message"]["content"] or ""
                return parse_meal(content), usage
            except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                last_error = str(exc)[:400]
                log.warning("Respuesta de IA inválida (intento %s): %s", attempt + 1, last_error)
                messages = messages[:2] + [
                    {
                        "role": "assistant",
                        "content": str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))[:2000],
                    },
                    {
                        "role": "user",
                        "content": "Tu respuesta no cumple el esquema: "
                        f"{last_error}. Devuelve únicamente el objeto JSON corregido.",
                    },
                ]
        error = AiError("invalid", "La IA ha respondido algo que no he sabido interpretar. Prueba a reformularlo.")
        error.usage = usage  # type: ignore[attr-defined]
        raise error

    def analyze_text(self, text: str) -> tuple[AiMeal, dict]:
        return self.analyze(f"Comida: {text.strip()}", model=self.settings.ai_model)

    def analyze_photo(self, image: bytes, mime: str, note: str = "") -> tuple[AiMeal, dict]:
        data_uri = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        prompt = PHOTO_INSTRUCTIONS
        if note.strip():
            prompt += f"\n\nNota de quien la ha comido: {note.strip()}"
        content = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": prompt},
        ]
        return self.analyze(
            content,
            model=self.settings.vision_model,
            base_url=self.settings.vision_base_url,
            api_key=self.settings.vision_api_key,
        )


def transcribe(settings: Settings, audio: bytes, filename: str, mime: str, http: httpx.Client | None = None) -> str:
    url = settings.stt_base_url.rstrip("/") + "/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.stt_api_key}"} if settings.stt_api_key else {}
    client = http or httpx.Client(timeout=settings.stt_timeout)
    try:
        resp = client.post(
            url,
            headers=headers,
            files={"file": (filename, audio, mime)},
            # Sin "prompt" a propósito. Una guía con comidas de ejemplo hacía que Whisper, ante un audio poco
            # claro, copiara la guía e inventara ingredientes que nadie había dicho.
            data={"model": settings.stt_model, "language": "es", "response_format": "json"},
        )
    except httpx.TimeoutException as exc:
        raise AiError("timeout", "La transcripción ha tardado demasiado. Prueba con un audio más corto.", 504) from exc
    except httpx.HTTPError as exc:
        raise AiError(
            "stt_down", "El servicio de transcripción no está disponible ahora mismo. Puedes escribirlo.", 503
        ) from exc
    finally:
        if http is None:
            client.close()
    if resp.status_code >= 400:
        log.error("Error %s del servicio de voz: %s", resp.status_code, resp.text[:300])
        raise AiError("stt_error", "No he podido transcribir el audio. Inténtalo otra vez o escríbelo.")
    text = (resp.json().get("text") or "").strip()
    if not text:
        raise AiError("stt_empty", "No he entendido nada en el audio. Acércate al micrófono y repite.", 422)
    return text
