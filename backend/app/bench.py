"""Mide la precisión de las calorías con comidas de referencia. Uso (en el servidor, sin ver la clave):

    docker compose exec app python -m app.bench --rpm 3
    docker compose exec app python -m app.bench --raw --rpm 3      # sin la canalización: solo lo que dice la IA
    docker compose exec app python -m app.bench --model kimi-k2.6 --price-in 0.95 --price-out 4.00

Las 30 comidas con cantidades explícitas tienen como referencia los valores oficiales de la tabla (CIQUAL 2025 y
USDA) para esas cantidades: mide cuánto se aleja cada sistema de los datos oficiales. Las 10 ambiguas se juzgan con un
rango razonable. Con --raw se suma lo que devuelve la IA tal cual, como hacía Kcalia antes de la tabla; sin --raw,
lo que sale después de refine() (valores de la tabla, gramos de las unidades y aceite de cocinar).
"""

import argparse
import statistics
import time

from .ai import AiClient, AiError
from .config import get_settings

try:  # el banco también corre en versiones sin la tabla (para medir el «antes»)
    from .refine import refine
except ImportError:  # pragma: no cover
    refine = None

# (texto, kcal, proteína, hidratos, grasa) por las cantidades indicadas. Salen de EXACT_SPEC con la tabla oficial;
# test_bench comprueba que coinciden. Los «a la plancha» incluyen el aceite de cocinar de la regla (2 g/100 g).
EXACT = [
    ("150 g de pechuga de pollo a la plancha", 238, 45.2, 0.0, 6.0),
    ("200 g de arroz blanco cocido", 310, 6.6, 66.4, 1.4),
    ("2 huevos cocidos", 134, 13.5, 0.5, 8.6),
    ("30 g de aceite de oliva", 270, 0.1, 0.0, 30.0),
    ("100 g de copos de avena", 369, 11.4, 57.7, 7.8),
    ("un plátano de 120 g", 105, 1.3, 23.6, 0.0),
    ("200 ml de leche entera", 133, 7.0, 9.8, 7.3),
    ("un yogur griego", 129, 3.7, 4.7, 10.2),
    ("60 g de pan integral", 140, 5.7, 24.7, 1.0),
    ("150 g de salmón a la plancha", 361, 38.3, 0.0, 23.2),
    ("100 g de lentejas cocidas", 125, 10.1, 16.2, 0.6),
    ("30 g de nueces", 213, 4.7, 2.1, 20.2),
    ("una lata de atún al natural", 80, 15.0, 0.0, 2.2),
    ("200 g de patata cocida", 162, 3.6, 33.6, 0.7),
    ("250 g de pasta cocida", 418, 16.7, 78.5, 2.8),
    ("2 rebanadas de pan de molde con 2 lonchas de jamón cocido", 201, 12.7, 28.5, 3.6),
    ("un café con leche", 73, 5.1, 7.9, 2.4),
    ("una manzana", 81, 0.4, 17.4, 0.4),
    ("un vaso de leche semidesnatada con una cucharada de cacao soluble", 136, 7.7, 17.9, 3.5),
    ("una tostada de pan con una cucharada de aceite", 217, 4.2, 25.6, 10.5),
    ("125 g de queso fresco batido 0%", 60, 9.0, 5.3, 0.0),
    ("un cazo de proteína whey con 300 ml de leche desnatada", 212, 34.4, 16.5, 0.5),
    ("una caña de cerveza", 79, 0.8, 6.3, 0.0),
    ("una copa de vino tinto de 150 ml", 113, 0.2, 0.0, 0.0),
    ("una lata de coca cola", 138, 0.0, 34.3, 0.0),
    ("150 g de patatas fritas", 387, 4.9, 49.0, 17.9),
    ("120 g de pechuga de pavo a la plancha", 170, 34.2, 0.0, 3.7),
    ("3 lonchas de jamón serrano", 106, 13.7, 0.3, 5.5),
    ("un puñado de almendras", 184, 6.8, 2.9, 15.4),
    ("un huevo frito", 88, 5.3, 0.4, 7.3),
]
# Cómo se calcula cada referencia: (alimento de la tabla, gramos).
EXACT_SPEC = [
    [("pechuga-pollo-plancha", 150), ("aceite-oliva", 3)],
    [("arroz-blanco-cocido", 200)],
    [("huevo-cocido", 100)],
    [("aceite-oliva", 30)],
    [("avena-copos", 100)],
    [("platano", 120)],
    [("leche-entera", 206)],
    [("yogur-griego", 125)],
    [("pan-integral", 60)],
    [("salmon-plancha", 150), ("aceite-oliva", 3)],
    [("lentejas-cocidas", 100)],
    [("nueces", 30)],
    [("atun-natural", 56)],
    [("patata-cocida", 200)],
    [("pasta-cocida", 250)],
    [("pan-molde", 56), ("jamon-cocido", 40)],
    [("cafe-con-leche", 204)],
    [("manzana", 150)],
    [("leche-semi", 206), ("cacao-soluble", 10)],
    [("tostada-pan", 40), ("aceite-oliva", 10)],
    [("queso-batido-0", 125)],
    [("whey", 30), ("leche-desnatada", 310.5)],
    [("cerveza", 202)],
    [("vino-tinto", 149.25)],
    [("cola", 343)],
    [("patatas-fritas", 150)],
    [("pavo-plancha", 120), ("aceite-oliva", 2.4)],
    [("jamon-serrano", 45)],
    [("almendras", 30)],
    [("huevo-frito", 46)],
]
# Sin cantidades: se acepta un rango razonable de calorías.
AMBIGUOUS = [
    ("dos huevos revueltos con una tostada de pan integral y aceite", 290, 420),
    ("tres croquetas de jamón", 180, 330),
    ("un bocadillo de jamón serrano", 350, 600),
    ("una tostada con tomate y aceite", 110, 240),
    ("un plato de lentejas con chorizo", 300, 620),
    ("una tortilla de patatas de pincho", 200, 380),
    ("un plato de paella", 350, 650),
    ("una ensalada mixta", 150, 450),
    ("un plato de macarrones con tomate", 400, 750),
    ("un filete de ternera con patatas fritas", 450, 800),
]
TOLERANCE = 0.12


def _totals(meal, text: str, raw: bool) -> dict[str, float]:
    keys = ("kcal", "protein", "carbs", "fat")
    if raw or refine is None:
        return {m: sum(getattr(i, m) for i in meal.items) for m in keys}
    items, _ = refine([i.model_dump() for i in meal.items], text=text)
    return {m: sum(float(i.get(m) or 0) for i in items) for m in keys}


def run(
    model: str | None, base_url: str | None, api_key: str | None, rpm: float | None = None, raw: bool = False
) -> dict:
    settings = get_settings()
    update = {k: v for k, v in {"ai_model": model, "ai_base_url": base_url, "ai_api_key": api_key}.items() if v}
    client = AiClient(settings.model_copy(update=update))
    if not client.configured:
        raise SystemExit("Falta AI_API_KEY (o --api-key).")

    spacing = 60 / rpm + 1.5 if rpm else 0.0
    last_start = [0.0]

    def ask(text: str):
        # Respeta el límite de peticiones por minuto de la cuenta: sin esto la mayoría de llamadas darían 429.
        pause = last_start[0] + spacing - time.perf_counter()
        if pause > 0:
            time.sleep(pause)
        last_start[0] = time.perf_counter()
        started = time.perf_counter()
        try:
            meal, usage = client.analyze_text(text)
        except AiError as error:
            return None, time.perf_counter() - started, {"prompt_tokens": 0, "completion_tokens": 0}, str(error)
        return meal, time.perf_counter() - started, usage, ""

    latencies, prompt_tokens, completion_tokens, kcal_errors, macro_errors, within, failures = [], [], [], [], [], 0, 0
    mode = "solo IA (--raw)" if raw or refine is None else "IA + tabla oficial"
    print(f"\nModelo: {client.settings.ai_model}  ·  {client.settings.ai_base_url}  ·  {mode}\n")
    for text, kcal, protein, carbs, fat in EXACT:
        meal, seconds, usage, error = ask(text)
        latencies.append(seconds)
        prompt_tokens.append(usage["prompt_tokens"])
        completion_tokens.append(usage["completion_tokens"])
        if meal is None or not meal.items:
            failures += 1
            print(f"  ✗ {text}: {error or 'sin resultado'}")
            continue
        got = _totals(meal, text, raw)
        error_pct = abs(got["kcal"] - kcal) / kcal
        kcal_errors.append(error_pct)
        macro_errors.append(sum(abs(got[m] - v) for m, v in (("protein", protein), ("carbs", carbs), ("fat", fat))) / 3)
        within += error_pct <= TOLERANCE
        mark = "✓" if error_pct <= TOLERANCE else "·"
        print(f"  {mark} {text:<48} {got['kcal']:>5.0f} kcal (ref {kcal})  {seconds:4.1f} s")

    ambiguous_ok = 0
    for text, low, high in AMBIGUOUS:
        meal, seconds, usage, error = ask(text)
        latencies.append(seconds)
        prompt_tokens.append(usage["prompt_tokens"])
        completion_tokens.append(usage["completion_tokens"])
        if meal is None or not meal.items:
            failures += 1
            print(f"  ✗ {text}: {error or 'sin resultado'}")
            continue
        total = _totals(meal, text, raw)["kcal"]
        ok = low <= total <= high
        ambiguous_ok += ok
        mark = "✓" if ok else "·"
        print(f"  {mark} {text:<48} {total:>5.0f} kcal (rango {low}-{high})  {seconds:4.1f} s")

    calls = len(EXACT) + len(AMBIGUOUS)
    latencies.sort()
    return {
        "model": client.settings.ai_model,
        "kcal_mape": statistics.mean(kcal_errors) * 100 if kcal_errors else float("nan"),
        "within": within,
        "exact": len(EXACT),
        "macro_mae_g": statistics.mean(macro_errors) if macro_errors else float("nan"),
        "ambiguous_ok": ambiguous_ok,
        "ambiguous": len(AMBIGUOUS),
        "failures": failures,
        "median_s": statistics.median(latencies),
        "p95_s": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "avg_prompt": statistics.mean(prompt_tokens),
        "avg_completion": statistics.mean(completion_tokens),
        "calls": calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="Modelo a probar (por defecto AI_MODEL)")
    parser.add_argument("--base-url", help="Base URL compatible con OpenAI (por defecto AI_BASE_URL)")
    parser.add_argument(
        "--api-key", help="Clave (por defecto AI_API_KEY). Mejor pasarla por entorno que por argumento."
    )
    parser.add_argument("--raw", action="store_true", help="Sumar lo que dice la IA, sin la tabla ni las reglas")
    parser.add_argument("--rpm", type=float, help="Peticiones por minuto que permite tu cuenta (espacia las llamadas)")
    parser.add_argument("--price-in", type=float, help="USD por millón de tokens de entrada, para estimar el coste")
    parser.add_argument("--price-out", type=float, help="USD por millón de tokens de salida")
    args = parser.parse_args()

    r = run(args.model, args.base_url, args.api_key, args.rpm, raw=args.raw)
    print("\n" + "─" * 64)
    band = f"{TOLERANCE * 100:.0f}"
    print(f"Calorías: error medio {r['kcal_mape']:.1f} %  ·  dentro de ±{band} %: {r['within']}/{r['exact']}")
    print(f"Macros:   error medio {r['macro_mae_g']:.1f} g por macro")
    print(f"Ambiguas: {r['ambiguous_ok']}/{r['ambiguous']} en rango  ·  fallos de formato o red: {r['failures']}")
    print(f"Latencia: mediana {r['median_s']:.1f} s  ·  p95 {r['p95_s']:.1f} s")
    print(f"Tokens por comida: {r['avg_prompt']:.0f} de entrada, {r['avg_completion']:.0f} de salida")
    if args.price_in is not None and args.price_out is not None:
        per_meal = (r["avg_prompt"] * args.price_in + r["avg_completion"] * args.price_out) / 1_000_000
        monthly = per_meal * 60 * 30
        print(f"Coste estimado (sin caché): {per_meal * 100:.3f} USD/100 comidas")
        print(f"                            {monthly:.2f} USD/mes al tope de 60 consultas al día")


if __name__ == "__main__":
    main()
