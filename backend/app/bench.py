"""Compara modelos de IA en esta tarea con comidas de referencia. Uso (en el servidor, sin ver la clave):

    docker compose exec app python -m app.bench
    docker compose exec app python -m app.bench --model kimi-k2.6 --price-in 0.95 --price-out 4.00
    AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \\
      docker compose exec -e AI_API_KEY=... app python -m app.bench --model gemini-3-flash-preview

Mide, para cada modelo: error de calorías y macros frente a valores BEDCA/USDA, latencia y coste por
100 comidas. Las 15 comidas de referencia llevan cantidades explícitas, así que mide sobre todo si el
modelo aplica bien las tablas del prompt y escala; la estimación de raciones se juzga con las
4 comidas ambiguas (rango aceptable en lugar de valor exacto).
"""

import argparse
import statistics
import time

from .ai import AiClient, AiError
from .config import get_settings

# (texto, kcal, proteína, hidratos, grasa) por las cantidades indicadas
EXACT = [
    ("150 g de pechuga de pollo a la plancha", 248, 46.5, 0, 5.4),
    ("200 g de arroz blanco cocido", 260, 5.4, 56, 0.6),
    ("2 huevos medianos (110 g) cocidos", 157, 13.9, 0.8, 10.5),
    ("30 g de aceite de oliva", 265, 0, 0, 30),
    ("100 g de avena en copos", 375, 13.5, 60, 7),
    ("1 plátano de 120 g sin piel", 107, 1.3, 27.6, 0.4),
    ("200 ml de leche entera", 130, 6.4, 9.4, 7.2),
    ("125 g de yogur griego natural", 150, 7.5, 5, 11.3),
    ("60 g de pan integral", 150, 6, 25.2, 2.1),
    ("150 g de salmón cocinado", 312, 33, 0, 19.5),
    ("100 g de lentejas cocidas", 116, 9, 20, 0.4),
    ("30 g de nueces", 196, 4.5, 4.2, 19.5),
    ("una lata de atún al natural (56 g escurrido)", 62, 14, 0, 0.6),
    ("200 g de patata cocida", 172, 3.6, 38, 0.2),
    ("250 g de pasta cocida", 375, 13.8, 75, 2.3),
]
# Sin cantidades: se acepta un rango razonable de calorías.
AMBIGUOUS = [
    ("dos huevos revueltos con una tostada de pan integral y aceite", 290, 420),
    ("tres croquetas de jamón", 180, 330),
    ("un café con leche", 40, 130),
    ("una tostada con tomate y aceite", 110, 240),
    ("un plato de lentejas con chorizo", 300, 620),
    ("una tortilla de patatas de pincho", 200, 380),
]
TOLERANCE = 0.12


def run(model: str | None, base_url: str | None, api_key: str | None, rpm: float | None = None) -> dict:
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
    print(f"\nModelo: {client.settings.ai_model}  ·  {client.settings.ai_base_url}\n")
    for text, kcal, protein, carbs, fat in EXACT:
        meal, seconds, usage, error = ask(text)
        latencies.append(seconds)
        prompt_tokens.append(usage["prompt_tokens"])
        completion_tokens.append(usage["completion_tokens"])
        if meal is None or not meal.items:
            failures += 1
            print(f"  ✗ {text}: {error or 'sin resultado'}")
            continue
        got = {m: sum(getattr(i, m) for i in meal.items) for m in ("kcal", "protein", "carbs", "fat")}
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
        total = sum(i.kcal for i in meal.items)
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
    parser.add_argument("--rpm", type=float, help="Peticiones por minuto que permite tu cuenta (espacia las llamadas)")
    parser.add_argument("--price-in", type=float, help="USD por millón de tokens de entrada, para estimar el coste")
    parser.add_argument("--price-out", type=float, help="USD por millón de tokens de salida")
    args = parser.parse_args()

    r = run(args.model, args.base_url, args.api_key, args.rpm)
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
