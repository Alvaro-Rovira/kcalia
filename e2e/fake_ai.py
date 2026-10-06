"""IA simulada para pruebas y capturas: habla el mismo protocolo que un proveedor compatible con OpenAI.

No se usa nunca en producción. Permite probar el flujo completo (texto, foto y voz)
sin clave, sin coste y con respuestas deterministas.

    uv run --project backend python e2e/fake_ai.py --port 8799
"""

import argparse
import asyncio
import json
import os
import unicodedata

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()
CALLS = {"chat": 0, "stt": 0}


FIBER100 = {"pan integral": 7, "arroz blanco cocido": 0.4, "lentejas": 7.9, "avena": 10, "platano": 2.6, "nueces": 6.7,
            "brocoli": 3.3, "patata": 1.8, "tomate": 1.2}


def item(name, qty, unit, grams, kcal, protein, carbs, fat):
    """Como el modelo real: valores por 100 g y peso total (los totales los calcula la app)."""
    per100 = lambda value: round(value / grams * 100, 2)  # noqa: E731
    plain_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    fiber = next((v for k, v in FIBER100.items() if k in plain_name), 0)
    return {
        "name": name, "qty": qty, "unit": unit, "grams": grams,
        "kcal100": per100(kcal), "protein100": per100(protein), "carbs100": per100(carbs), "fat100": per100(fat),
        "fiber100": fiber, "alcohol100": 0,
    }


# (palabras clave, respuesta). Gana la primera cuyas palabras estén todas en el texto.
MEALS = [
    (("huevo", "tostada"), {
        "name": "Huevos revueltos con tostada integral",
        "items": [
            item("huevo revuelto", 2, "pieza", 110, 157.3, 13.9, 0.8, 10.5),
            item("pan integral", 1, "rebanada", 40, 100, 4, 16.8, 1.4),
            item("aceite de oliva", 10, "g", 10, 88.4, 0, 0, 10),
        ],
        "confidence": 0.86,
        "assumptions": ["Huevos medianos de 55 g", "Una cucharada de aceite (10 g)"],
    }),
    (("cafe", "leche"), {
        "name": "Café con leche",
        "items": [
            item("café", 60, "ml", 60, 1.2, 0.1, 0, 0),
            item("leche semidesnatada", 140, "ml", 144, 64.4, 4.6, 6.7, 2.2),
        ],
        "confidence": 0.82,
        "assumptions": ["Taza de 200 ml con leche semidesnatada"],
    }),
    (("pollo", "arroz"), {
        "name": "Pechuga de pollo con arroz",
        "items": [
            item("pechuga de pollo a la plancha", 150, "g", 150, 247.5, 46.5, 0, 5.4),
            item("arroz blanco cocido", 200, "g", 200, 260, 5.4, 56, 0.6),
            item("aceite de oliva", 5, "g", 5, 44.2, 0, 0, 5),
        ],
        "confidence": 0.9,
        "assumptions": ["Peso del arroz ya cocido", "5 g de aceite para la plancha"],
    }),
    (("yogur",), {
        "name": "Yogur griego con nueces",
        "items": [
            item("yogur griego", 1, "pieza", 125, 150, 7.5, 5, 11.3),
            item("nueces", 1, "puñado", 20, 130.8, 3, 2.8, 13),
        ],
        "confidence": 0.8,
        "assumptions": ["Yogur de 125 g", "Un puñado pequeño de nueces (20 g)"],
    }),
    (("salmon",), {
        "name": "Salmón con patata y brócoli",
        "items": [
            item("salmón a la plancha", 1, "racion", 160, 332.8, 35.2, 0, 20.8),
            item("patata cocida", 1, "pieza", 170, 146.2, 3.1, 32.3, 0.2),
            item("brócoli cocido", 150, "g", 150, 52.5, 3.6, 10.5, 0.6),
        ],
        "confidence": 0.78,
        "assumptions": ["Ración de salmón de 160 g", "Patata mediana de 170 g"],
    }),
    (("lentejas",), {
        "name": "Lentejas con chorizo",
        "items": [item("lentejas con chorizo", 1, "plato", 330, 429, 26.4, 42.9, 16.5)],
        "confidence": 0.7,
        "assumptions": ["Plato de 330 g"],
    }),
    (("avena",), {
        "name": "Avena con plátano",
        "items": [
            item("avena en copos", 50, "g", 50, 187.5, 6.8, 30, 3.5),
            item("leche semidesnatada", 200, "ml", 206, 92, 6.6, 9.6, 3.2),
            item("plátano", 1, "pieza", 120, 106.8, 1.3, 27.6, 0.4),
        ],
        "confidence": 0.84,
        "assumptions": ["Plátano mediano de 120 g sin piel"],
    }),
    (("batido",), {
        "name": "Batido de proteína",
        "items": [item("proteína whey en polvo", 1, "cazo", 30, 114, 23.4, 1.8, 1.5)],
        "confidence": 0.9,
        "assumptions": ["Un cazo de 30 g con agua"],
    }),
    (("bocadillo",), {
        "name": "Bocadillo de jamón serrano",
        "items": [
            item("pan blanco de barra", 1, "pieza", 110, 291.5, 9.9, 56.1, 3.3),
            item("jamón serrano", 4, "loncha", 40, 96, 12.4, 0, 5.2),
            item("tomate", 60, "g", 60, 10.8, 0.5, 2.3, 0.1),
            item("aceite de oliva", 8, "g", 8, 70.7, 0, 0, 8),
        ],
        "confidence": 0.83,
        "assumptions": ["Medio pan de barra de 110 g", "Cuatro lonchas de jamón serrano (40 g)", "Un chorrito de aceite (8 g)"],
    }),
    (("ensalada",), {
        "name": "Ensalada de atún",
        "items": [
            item("lechuga", 100, "g", 100, 15, 1.4, 2.9, 0.2),
            item("tomate", 1, "pieza", 120, 21.6, 1.1, 4.7, 0.2),
            item("atún al natural", 1, "lata", 56, 61.6, 14, 0, 0.6),
            item("aceite de oliva", 10, "g", 10, 88.4, 0, 0, 10),
        ],
        "confidence": 0.76,
        "assumptions": ["Aliñada con una cucharada de aceite"],
    }),
    (("pasta",), {
        "name": "Pasta con tomate y carne",
        "items": [
            item("pasta cocida", 1, "plato", 280, 420, 15.4, 84, 2.5),
            item("carne picada mixta cocinada", 100, "g", 100, 250, 24, 0, 17),
            item("tomate frito", 80, "g", 80, 61.6, 1.2, 8.8, 2.4),
        ],
        "confidence": 0.74,
        "assumptions": ["Plato de pasta de 280 g ya cocida"],
    }),
]
PHOTO = {
    "name": "Pollo con arroz y ensalada",
    "items": [
        item("pechuga de pollo a la plancha", 140, "g", 140, 231, 43.4, 0, 5),
        item("arroz blanco cocido", 180, "g", 180, 234, 4.9, 50.4, 0.5),
        item("ensalada verde", 80, "g", 80, 14.4, 1, 2.6, 0.2),
        item("aceite de oliva", 8, "g", 8, 70.7, 0, 0, 8),
    ],
    "confidence": 0.62,
    "assumptions": ["Cantidades estimadas por el tamaño del plato", "Aceite del aliño y de la plancha"],
}
UNKNOWN = ("lo de siempre", "algo", "no se")


def plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def label(name, short, basis, kcal, kj, protein, carbs, fat, fiber, sugars, salt, serving_g, serving_label):
    return {
        "is_label": True, "name": name, "short_name": short, "basis": basis, "kcal100": kcal, "energy_kj100": kj,
        "protein100": protein, "carbs100": carbs, "fat100": fat, "fiber100": fiber, "sugars100": sugars,
        "salt100": salt, "serving_g": serving_g, "serving_label": serving_label, "per_serving": None,
        "confidence": 0.94, "notes": [],
    }


LABELS = {
    "yogur": label("Yogur desnatado ligero sabor limón", "yogur ligero", "g", 44, 187, 4.1, 6.5, 0.1, None, 6.2, 0.12, 125, "yogur"),
    "galletas": label("Galletas integrales con avena", "galletas integrales", "g", 440, 1850, 7.5, 68, 14, 6.4, 19, 0.68, 12, "galleta"),
    "leche": label("Leche semidesnatada", "leche semidesnatada", "ml", 46, 192, 3.2, 4.7, 1.6, None, 4.7, 0.1, 200, "vaso"),
    "queso": label("Queso fresco batido 0 %", "queso batido", "g", 46, 192, 8.0, 3.5, 0.2, None, 3.5, 0.18, 250, "tarrina"),
}
NEXT_LABEL = ["yogur"]  # qué etiqueta devuelve la siguiente lectura (POST /next-label?kind=galletas)


def answer(messages: list[dict]) -> dict:
    # La lectura de etiquetas usa otro prompt de sistema: responde con la tabla de un yogur ligero.
    if messages and messages[0]["role"] == "system" and "etiquetas nutricionales" in str(messages[0]["content"]):
        return LABELS[NEXT_LABEL[0]]
    content = messages[-1]["content"]
    # La petición de reintento ("no cumple el esquema") se responde con la comida original.
    for message in reversed(messages):
        if message["role"] == "user" and "esquema" not in str(message["content"]):
            content = message["content"]
            break
    if isinstance(content, list):
        return {**PHOTO, "clarification": None}
    text = plain(content.removeprefix("Comida:").strip())
    if any(text == u or text.startswith(u + " ") for u in UNKNOWN) or len(text) < 3:
        return {"name": "", "items": [], "confidence": 0, "assumptions": [],
                "clarification": "No me queda claro qué has comido. ¿Me dices los alimentos y, si puedes, las cantidades?"}
    for keywords, meal in MEALS:
        if all(k in text for k in keywords):
            return {**meal, "clarification": None}
    grams = 250
    return {
        "name": content.removeprefix("Comida:").strip().capitalize()[:60],
        "items": [item(text[:60], 1, "racion", grams, 380, 18, 40, 16)],
        "confidence": 0.5,
        "assumptions": ["Ración estándar de 250 g"],
        "clarification": None,
    }


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    CALLS["chat"] += 1
    # FAKE_AI_DELAY simula la latencia de un modelo real (para capturar la animación de "analizando").
    await asyncio.sleep(float(os.environ.get("FAKE_AI_DELAY", "0")))
    return {
        "id": "fake",
        "model": body.get("model"),
        "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(answer(body["messages"]), ensure_ascii=False)}}],
        "usage": {"prompt_tokens": 1800, "completion_tokens": 160},
    }


@app.post("/v1/audio/transcriptions")
async def transcribe():
    CALLS["stt"] += 1
    return {"text": "Un yogur griego con nueces"}


@app.post("/next-label")
def next_label(kind: str = "yogur"):
    NEXT_LABEL[0] = kind if kind in LABELS else "yogur"
    return {"next": NEXT_LABEL[0]}


# Open Food Facts simulado (OFF_BASE_URL apunta aquí en las pruebas): un producto conocido y el resto, 404.
OFF_PRODUCTS = {
    "8410000123456": {
        "code": "8410000123456",
        "product_name_es": "Queso fresco batido 0 %",
        "brands": "Marca Blanca",
        "quantity": "500 g",
        "serving_size": "1 tarrina (250 g)",
        "serving_quantity": 250,
        "nutriments": {"energy-kcal_100g": 46, "proteins_100g": 8, "carbohydrates_100g": 3.5, "fat_100g": 0.2},
    }
}


@app.get("/api/v2/product/{code}")
def off_product(code: str):
    from fastapi.responses import JSONResponse

    CALLS["off"] = CALLS.get("off", 0) + 1
    product = OFF_PRODUCTS.get(code.removesuffix(".json"))
    if product is None:
        return JSONResponse({"status": 0, "status_verbose": "product not found"}, status_code=404)
    return {"status": 1, "product": product}


@app.get("/calls")
def calls():
    return CALLS


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    uvicorn.run(app, host="127.0.0.1", port=parser.parse_args().port, log_level="warning")
