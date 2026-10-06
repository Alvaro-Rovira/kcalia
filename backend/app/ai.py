"""Cliente de IA compatible con OpenAI: texto y foto -> desglose nutricional validado."""

import base64
import json
import logging
import re
import time

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

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
      "grams": number,       // peso TOTAL comestible del ingrediente en gramos, con todas sus unidades juntas ("2 huevos" -> 110; líquidos: ml ≈ g)
      "kcal100": number,     // valores POR CADA 100 g de ese alimento (nunca del total)
      "protein100": number,  // gramos de proteína por 100 g
      "carbs100": number,    // gramos de hidratos disponibles por 100 g
      "fat100": number,      // gramos de grasa por 100 g
      "fiber100": number,    // gramos de fibra alimentaria por 100 g (0 si no tiene)
      "alcohol100": number   // gramos de alcohol etílico por 100 g: 0 salvo en bebidas alcohólicas
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
- NO calcules totales ni multipliques: da solo los valores por 100 g y el peso total en "grams"; el sistema hace la cuenta. Ejemplo: «2 huevos» -> qty 2, unit "pieza", grams 110, kcal100 143, protein100 12.6, carbs100 0.7, fat100 9.5.
- Un solo elemento por alimento: si el mismo alimento sale varias veces (p. ej. aceite en el revuelto y en la tostada), súmalo en uno.
- Las kcal por 100 g deben ser coherentes con 4·proteína + 4·hidratos + 9·grasa (el alcohol aporta 7 kcal/g y es la única excepción).
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


LABEL_PROMPT = """Eres un experto en leer etiquetas nutricionales de productos envasados vendidos en España. \
Recibes la foto de la parte de atrás de un producto. Respondes SOLO con un objeto JSON válido, sin texto \
alrededor ni bloques de código.

ESQUEMA (usa null cuando un dato no aparezca en la foto; nunca lo inventes):
{
  "is_label": boolean,        // false si la foto no muestra una tabla de información nutricional legible
  "name": string,             // nombre del producto tal como aparece en el envase; si no se ve, una descripción corta ("Yogur desnatado")
  "short_name": string,       // cómo lo llamaría una persona al apuntar lo que come: 1 a 3 palabras, minúsculas, singular ("yogur ligero")
  "basis": "g" | "ml",        // "ml" si la columna principal es por 100 ml (bebidas); "g" en el resto
  "kcal100": number|null,     // energía en kcal por 100 g/ml. Si solo hay kJ, déjalo en null y rellena energy_kj100
  "energy_kj100": number|null,
  "protein100": number|null,  // proteínas, g por 100
  "carbs100": number|null,    // hidratos de carbono TOTALES (no solo azúcares), g por 100
  "fat100": number|null,      // grasas TOTALES, g por 100
  "fiber100": number|null,
  "sugars100": number|null,
  "salt100": number|null,
  "serving_g": number|null,   // peso o volumen de UNA unidad o porción SI la etiqueta lo indica ("1 yogur (125 g)", "porción de 30 g")
  "serving_label": string|null, // nombre de esa unidad en singular: "yogur", "porción", "galleta", "lata"
  "per_serving": {"kcal": number|null, "protein": number|null, "carbs": number|null, "fat": number|null} | null,
  "confidence": number,       // 0 a 1: 0.9 o más si todo se lee con claridad, menos de 0.6 si hay cifras borrosas o dudosas
  "notes": [string]           // avisos breves en español: cifras difíciles de leer, varias columnas...
}

REGLAS
- Copia las cifras tal como están impresas. No estimes, no redondees, no corrijas ni completes con lo que sepas del producto.
- Si hay dos columnas («por 100 g» y «por porción»), usa SIEMPRE la de 100 g o 100 ml. "per_serving" solo si no existe la de 100.
- Los valores son por 100 g o 100 ml, nunca del envase entero. Devuelve los números con punto decimal.
- Si hay varias tablas (por ejemplo «tal como se vende» y «preparado»), usa la de «tal como se vende».
- Si no ves ninguna tabla nutricional, devuelve "is_label": false y el resto en null."""

KCAL_PER_KJ = 4.184


class LabelDraft(BaseModel):
    is_label: bool = True
    name: str = Field(default="", max_length=160)
    short_name: str = Field(default="", max_length=80)
    basis: str = "g"
    kcal100: float | None = None
    energy_kj100: float | None = None
    protein100: float | None = None
    carbs100: float | None = None
    fat100: float | None = None
    fiber100: float | None = None
    sugars100: float | None = None
    salt100: float | None = None
    serving_g: float | None = None
    serving_label: str | None = None
    per_serving: dict | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    notes: list[str] = Field(default_factory=list, max_length=8)


def parse_label(content: str) -> LabelDraft:
    draft = LabelDraft.model_validate(extract_json(content))
    if draft.is_label:
        for key in ("kcal100", "protein100", "carbs100", "fat100", "fiber100", "sugars100", "salt100"):
            value = getattr(draft, key)
            if value is None:
                continue
            if value < 0 or value > (MAX_KCAL_PER_100G if key == "kcal100" else 100):
                raise ValueError(f"{key} = {value} no es posible: son valores por 100 g o 100 ml, no del envase entero")
        if (draft.protein100 or 0) + (draft.carbs100 or 0) + (draft.fat100 or 0) > 105:
            raise ValueError(
                "proteínas, hidratos y grasas por 100 g suman más de 100 g: revisa la columna que has leído"
            )
    return draft


def finalize_label(draft: LabelDraft) -> dict:
    """De lo que ha leído el modelo a lo que se le enseña al usuario para que lo revise.

    Aquí se completa lo que falta con cuentas (kJ -> kcal, porción -> 100 g) y se avisa de lo que no cuadra:
    leer mal una cifra es el error típico de este paso, y el usuario tiene la foto delante para comprobarlo.
    """
    warnings = [note.strip() for note in draft.notes if note and note.strip()]
    per100 = {k: getattr(draft, k) for k in ("kcal100", "protein100", "carbs100", "fat100")}
    basis = draft.basis if draft.basis in ("g", "ml") else "g"

    if per100["kcal100"] is None and draft.energy_kj100:
        per100["kcal100"] = round(draft.energy_kj100 / KCAL_PER_KJ)  # las etiquetas imprimen kcal enteras
        warnings.append("Las calorías se han calculado a partir de los kJ de la etiqueta.")

    serving = draft.per_serving or {}
    if draft.serving_g and draft.serving_g > 0 and serving:
        mapping = {"kcal100": "kcal", "protein100": "protein", "carbs100": "carbs", "fat100": "fat"}
        converted = False
        for target, source in mapping.items():
            value = serving.get(source)
            if per100[target] is None and isinstance(value, int | float):
                per100[target] = value / draft.serving_g * 100
                converted = True
        if converted:
            warnings.append("La etiqueta solo traía valores por porción; se han pasado a 100 g.")

    if all(per100[k] is not None for k in per100):
        expected = 4 * per100["protein100"] + 4 * per100["carbs100"] + 9 * per100["fat100"] + 2 * (draft.fiber100 or 0)
        gap = abs(per100["kcal100"] - expected)
        if gap > max(0.18 * max(per100["kcal100"], expected), 12):
            warnings.append(
                f"Las calorías ({per100['kcal100']:.0f}) no cuadran con los macros (≈ {expected:.0f}). "
                "Compáralo con la foto: puede haberse leído mal alguna cifra."
            )
            draft.confidence = min(draft.confidence, 0.55)

    def clean(value):
        # Dos decimales: las etiquetas traen cifras como 0,12 g de sal o 0,07 g de grasa.
        return None if value is None else round(float(value), 2)

    label = (draft.serving_label or "").strip().lower()
    unit_grams = clean(draft.serving_g) if draft.serving_g and draft.serving_g > 0 else None
    name = draft.name.strip() or draft.short_name.strip()
    alias = (draft.short_name.strip() or name).lower()
    return {
        "name": name,
        "alias": alias,
        "basis": basis,
        **{k: clean(v) for k, v in per100.items()},
        "fiber100": clean(draft.fiber100),
        "sugars100": clean(draft.sugars100),
        "salt100": clean(draft.salt100),
        "unit_label": (label or ("porción" if unit_grams else ""))[:30],
        "unit_grams": unit_grams,
        "confidence": round(draft.confidence, 2),
        "warnings": warnings,
        "missing": [k for k, v in per100.items() if v is None],
    }


class AiError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


PER100_KEYS = ("kcal100", "protein100", "carbs100", "fat100")
MAX_KCAL_PER_100G = 950  # el aceite puro ronda 884


class AiItem(BaseModel):
    """Un ingrediente. El modelo da los valores por 100 g y el peso total; los totales los calcula el código,
    porque escalar a mano falla (dos huevos salieron como 314 kcal en lugar de 157)."""

    name: str = Field(min_length=1, max_length=120)
    qty: float = Field(default=1, ge=0, le=10000)
    unit: str = Field(default="g", max_length=16)
    grams: float = Field(gt=0, le=5000)
    kcal: float = Field(ge=0, le=6000)
    protein: float = Field(ge=0, le=600)
    carbs: float = Field(ge=0, le=1200)
    fat: float = Field(ge=0, le=600)
    # Opcionales: respuestas (y cachés) anteriores no los traen, y siguen siendo válidas.
    fiber: float | None = Field(default=None, ge=0, le=300)
    alcohol: float | None = Field(default=None, ge=0, le=500)

    @model_validator(mode="before")
    @classmethod
    def _totals_from_per100(cls, data):
        if not isinstance(data, dict) or not all(key in data for key in PER100_KEYS):
            return data  # respuesta con totales (modelos que ignoran el esquema): se acepta tal cual
        try:
            grams = float(data["grams"])
            kcal, protein, carbs, fat = (float(data[key]) for key in PER100_KEYS)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("los valores por 100 g y los gramos deben ser números") from exc
        if not 0 < grams <= 5000:
            raise ValueError("los gramos totales están fuera de rango")
        if min(kcal, protein, carbs, fat) < 0 or kcal > MAX_KCAL_PER_100G:
            raise ValueError(f"kcal100 debe estar entre 0 y {MAX_KCAL_PER_100G}: son kcal por 100 g, no del total")
        try:
            fiber = float(data["fiber100"]) if data.get("fiber100") is not None else None
            alcohol = float(data["alcohol100"]) if data.get("alcohol100") is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("fiber100 y alcohol100 deben ser números (0 si no hay)") from exc
        if (fiber is not None and not 0 <= fiber <= 90) or (alcohol is not None and not 0 <= alcohol <= 60):
            raise ValueError("fiber100 o alcohol100 fuera de rango: son gramos por 100 g")
        if protein + carbs + fat + (alcohol or 0) > 105:
            raise ValueError(
                "proteína, hidratos, grasa y alcohol por 100 g suman más de 100 g: no son valores por 100 g"
            )
        factor = grams / 100
        return {
            **data,
            "kcal": kcal * factor,
            "protein": protein * factor,
            "carbs": carbs * factor,
            "fat": fat * factor,
            "fiber": fiber * factor if fiber is not None else None,
            "alcohol": alcohol * factor if alcohol else None,
        }

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("kcal", "protein", "carbs", "fat", "grams", "qty", "fiber", "alcohol")
    @classmethod
    def _round(cls, value: float | None) -> float | None:
        return None if value is None else round(value, 1)


class AiMeal(BaseModel):
    name: str = Field(default="", max_length=160)
    items: list[AiItem] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.7, ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    clarification: str | None = None


def merge_duplicates(meal: AiMeal) -> AiMeal:
    """Un solo elemento por alimento, aunque el modelo repita el aceite del revuelto y el de la tostada."""
    merged: dict[str, AiItem] = {}
    for item in meal.items:
        first = merged.get(item.name)
        if first is None:
            merged[item.name] = item.model_copy()
            continue
        if first.unit == item.unit:
            first.qty = round(first.qty + item.qty, 1)
        else:
            first.unit, first.qty = "g", 0  # cantidades en unidades distintas: se deja el total en gramos
        first.grams = round(first.grams + item.grams, 1)
        first.kcal = round(first.kcal + item.kcal, 1)
        first.protein = round(first.protein + item.protein, 1)
        first.carbs = round(first.carbs + item.carbs, 1)
        first.fat = round(first.fat + item.fat, 1)
        for extra in ("fiber", "alcohol"):
            a, b = getattr(first, extra), getattr(item, extra)
            if a is not None or b is not None:
                setattr(first, extra, round((a or 0) + (b or 0), 1))
    for item in merged.values():
        if item.unit == "g" and item.qty == 0:
            item.qty = item.grams
    meal.items = list(merged.values())
    return meal


def check_consistency(meal: AiMeal) -> AiMeal:
    """Corrige kcal claramente incoherentes con los macros (4/4/9)."""
    adjusted = False
    for item in meal.items:
        atwater = 4 * item.protein + 4 * item.carbs + 9 * item.fat + 7 * (item.alcohol or 0)
        # Menos kcal de las que suman los macros (y el alcohol) es imposible.
        if item.kcal < atwater * 0.8 - 10:
            item.kcal = round(atwater, 1)
            adjusted = True
    if adjusted:
        meal.confidence = round(min(meal.confidence, 0.6), 2)
        meal.assumptions.append("Calorías recalculadas a partir de los macros por coherencia")
    return meal


PLAN_PROMPT = """Eres un dietista-nutricionista español. Propones comidas sencillas, habituales en España y fáciles \
de preparar para rellenar huecos de un plan semanal. Respondes SOLO con un objeto JSON válido, sin texto alrededor.

ESQUEMA:
{
  "meals": [                  // una por hueco pedido, EN EL MISMO ORDEN
    {
      "date": "AAAA-MM-DD",
      "slot": "desayuno" | "comida" | "merienda" | "cena" | "snack",
      "name": string,          // título corto, sin cantidades
      "items": [               // ingredientes, igual que al analizar una comida
        {"name": string, "qty": number, "unit": string, "grams": number,
         "kcal100": number, "protein100": number, "carbs100": number, "fat100": number,
         "fiber100": number, "alcohol100": 0}
      ]
    }
  ]
}

REGLAS
- Valores POR CADA 100 g y el peso total en "grams": el sistema hace las cuentas. No calcules totales.
- Ajusta las cantidades para acercarte a las calorías orientativas de cada hueco SIN pasarte.
- Prioriza alimentos con proteína. Nada de alcohol.
- Si la persona ya come ciertos platos, úsalos o propón algo parecido.
- Valores de referencia: BEDCA y, si no está, USDA. Punto decimal y un decimal."""


class PlanMeal(BaseModel):
    date: str = Field(max_length=10)
    slot: str = Field(max_length=12)
    name: str = Field(default="", max_length=160)
    items: list[AiItem] = Field(min_length=1, max_length=15)


class PlanReply(BaseModel):
    meals: list[PlanMeal] = Field(default_factory=list, max_length=14)


def parse_plan(content: str) -> PlanReply:
    reply = PlanReply.model_validate(extract_json(content))
    if not reply.meals:
        raise ValueError('"meals" está vacío')
    for meal in reply.meals:
        check_consistency(merge_duplicates(AiMeal(name=meal.name, items=meal.items)))
    return reply


SUGGEST_PROMPT = """Eres un dietista-nutricionista español. La persona ya ha comido hoy y le quedan unas calorías. \
Propón 3 ideas sencillas y habituales en España para cerrar el día SIN SUPERAR las calorías que le quedan, priorizando \
la proteína que le falta. Respondes SOLO con un objeto JSON válido, sin texto alrededor.

ESQUEMA:
{
  "ideas": [
    {"name": string, "items": [{"name": string, "qty": number, "unit": string, "grams": number,
      "kcal100": number, "protein100": number, "carbs100": number, "fat100": number, "fiber100": number,
      "alcohol100": 0}]}
  ]
}

REGLAS
- Valores POR CADA 100 g y la cantidad total en "grams": el sistema calcula los totales y descarta lo que se pase.
- Nada de alcohol. Nada copioso si es tarde por la noche.
- Cantidades realistas (una pieza de fruta, un yogur, una lata de atún...)."""


class SuggestIdea(BaseModel):
    name: str = Field(default="", max_length=160)
    items: list[AiItem] = Field(min_length=1, max_length=8)


class SuggestReply(BaseModel):
    ideas: list[SuggestIdea] = Field(default_factory=list, max_length=5)


def parse_suggestions(content: str) -> SuggestReply:
    reply = SuggestReply.model_validate(extract_json(content))
    if not reply.ideas:
        raise ValueError('"ideas" está vacío')
    return reply


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
    return check_consistency(merge_duplicates(meal))


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

    def _complete(
        self, system: str, user_content: str | list, parse, *, model: str, base_url: str | None, api_key: str | None
    ):
        """Pide una respuesta JSON, la valida con `parse` y, si no cumple el esquema, un único reintento.

        Devuelve lo validado y el uso (llamadas y tokens).
        """
        messages: list[dict] = [
            {"role": "system", "content": system},
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
                return parse(content), usage
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

    def analyze(
        self, user_content: str | list, *, model: str, base_url: str | None = None, api_key: str | None = None
    ) -> tuple[AiMeal, dict]:
        """Devuelve la comida validada y el uso (llamadas y tokens). Un reintento si el JSON falla."""
        return self._complete(SYSTEM_PROMPT, user_content, parse_meal, model=model, base_url=base_url, api_key=api_key)

    def analyze_label(self, image: bytes, mime: str) -> tuple[dict, dict]:
        """Lee la tabla nutricional de la foto del envase. Devuelve los datos del producto y el uso."""
        data_uri = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        content = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": "Lee la etiqueta nutricional de esta foto."},
        ]
        return self._complete(
            LABEL_PROMPT,
            content,
            parse_label,
            model=self.settings.vision_model,
            base_url=self.settings.vision_base_url,
            api_key=self.settings.vision_api_key,
        )

    def suggest_plan(self, request: str) -> tuple[PlanReply, dict]:
        return self._complete(
            PLAN_PROMPT, request, parse_plan, model=self.settings.ai_model, base_url=None, api_key=None
        )

    def suggest_close(self, request: str) -> tuple[SuggestReply, dict]:
        return self._complete(
            SUGGEST_PROMPT, request, parse_suggestions, model=self.settings.ai_model, base_url=None, api_key=None
        )

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
