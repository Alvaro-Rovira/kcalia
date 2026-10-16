"""Mide el análisis de FOTOS con platos pesados de verdad (Nutrition5k, Google Research, CC BY 4.0).

    python3 -I scripts/fetch_nutrition5k.py /root/n5k          # muestra fija de 20 platos
    docker compose run --rm --no-deps -T -v /root/n5k:/n5k:ro app \\
        python -m app.bench_photos /n5k --model claude-haiku-5-5 --price-in 0.10 --price-out 0.50
    ... --model kimi-k2.6 --rpm 3 --price-in 0.95 --price-out 4.00

Cada foto pasa por lo mismo que en la app (la IA identifica y pesa; refine() pone los valores de la tabla y el aceite)
y se compara con la báscula: error de calorías, de peso total y de macros, latencia y tokens.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from app.ai import AiClient, AiError, is_claude
from app.config import get_settings
from app.refine import refine

MACROS = ("protein", "carbs", "fat")


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def run(folder: Path, model: str, effort: str | None, rpm: float | None, passes: int) -> dict:
    dishes = json.loads((folder / "dishes.json").read_text())
    settings = get_settings()
    update = {"ai_vision_model": model, **({"ai_effort": effort} if effort is not None else {})}
    client = AiClient(settings.model_copy(update=update))
    if not (settings.anthropic_api_key if is_claude(model) else settings.vision_api_key):
        raise SystemExit("Falta la clave del proveedor de este modelo.")
    s = client.settings
    where = f"Anthropic · razonamiento {s.ai_effort or 'desactivado'}" if is_claude(model) else s.vision_base_url
    print(f"\nModelo: {model}  ·  {where}  ·  {len(dishes)} platos × {passes}\n")

    spacing = 60 / rpm + 1.5 if rpm else 0.0
    last_start = 0.0
    errors, signed, mass_errors, macro_errors, latencies, tokens_in, tokens_out = [], [], [], [], [], [], []
    failures = 0
    for _ in range(passes):
        for dish in dishes:
            image = (folder / dish["id"] / "rgb.png").read_bytes()
            pause = last_start + spacing - time.perf_counter()
            if pause > 0:
                time.sleep(pause)
            last_start = started = time.perf_counter()
            try:
                meal, usage = client.analyze_photo(image, "image/png")
            except AiError as error:
                failures += 1
                print(f"  ✗ {dish['id']}: {error}")
                continue
            seconds = time.perf_counter() - started
            latencies.append(seconds)
            tokens_in.append(usage["prompt_tokens"])
            tokens_out.append(usage["completion_tokens"])
            items, _ = refine([i.model_dump() for i in meal.items], text="", photo=True)
            if not items:
                failures += 1
                print(f"  ✗ {dish['id']}: sin ingredientes ({meal.clarification or 'sin aclaración'})")
                continue
            got = {k: sum(float(i.get(k) or 0) for i in items) for k in ("kcal", "grams", *MACROS)}
            error = (got["kcal"] - dish["kcal"]) / dish["kcal"]
            errors.append(abs(error))
            signed.append(error)
            mass_errors.append(abs(got["grams"] - dish["grams"]) / dish["grams"])
            macro_errors.append(sum(abs(got[m] - dish[m]) for m in MACROS) / 3)
            truth = ", ".join(i["name"] for i in dish["ingredients"][:4])
            seen = ", ".join(i["name"] for i in items[:4])
            print(
                f"  {'✓' if abs(error) <= 0.2 else '·'} {got['kcal']:>4.0f} kcal / {got['grams']:>3.0f} g  (real "
                f"{dish['kcal']:>4.0f} / {dish['grams']:>3.0f} g)  {error * 100:+4.0f} %  {seconds:4.1f} s"
                f"\n      real: {truth}\n      visto: {seen}"
            )

    n = len(errors)
    return {
        "model": model,
        "n": n,
        "failures": failures,
        "kcal_mape": statistics.mean(errors) * 100 if n else float("nan"),
        "kcal_median": statistics.median(errors) * 100 if n else float("nan"),
        "bias": statistics.mean(signed) * 100 if n else float("nan"),
        "within20": sum(e <= 0.2 for e in errors),
        "within30": sum(e <= 0.3 for e in errors),
        "mass_mape": statistics.mean(mass_errors) * 100 if n else float("nan"),
        "macro_mae": statistics.mean(macro_errors) if n else float("nan"),
        "median_s": statistics.median(latencies) if latencies else float("nan"),
        "p95_s": _p95(latencies) if latencies else float("nan"),
        "avg_in": statistics.mean(tokens_in) if tokens_in else 0,
        "avg_out": statistics.mean(tokens_out) if tokens_out else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="Carpeta creada por scripts/fetch_nutrition5k.py")
    parser.add_argument("--model", required=True, help="Modelo de fotos a probar (kimi-k2.6, claude-haiku-5-5...)")
    parser.add_argument("--effort", help="Solo Claude: low, medium o high activa el razonamiento")
    parser.add_argument("--rpm", type=float, help="Peticiones por minuto que permite tu cuenta")
    parser.add_argument("--passes", type=int, default=1, help="Pasadas por la muestra (las respuestas varían)")
    parser.add_argument("--price-in", type=float, help="USD por millón de tokens de entrada")
    parser.add_argument("--price-out", type=float, help="USD por millón de tokens de salida")
    args = parser.parse_args()

    r = run(args.folder, args.model, args.effort, args.rpm, args.passes)
    print("\n" + "─" * 64)
    print(f"Fotos analizadas: {r['n']}  ·  fallos: {r['failures']}")
    print(
        f"Calorías: error medio {r['kcal_mape']:.1f} %  ·  mediana {r['kcal_median']:.1f} %  ·  "
        f"sesgo {r['bias']:+.1f} %"
    )
    print(f"          dentro de ±20 %: {r['within20']}/{r['n']}  ·  de ±30 %: {r['within30']}/{r['n']}")
    print(f"Peso total: error medio {r['mass_mape']:.1f} %  ·  macros: error medio {r['macro_mae']:.1f} g")
    print(f"Latencia: mediana {r['median_s']:.1f} s  ·  p95 {r['p95_s']:.1f} s")
    print(f"Tokens por foto: {r['avg_in']:.0f} de entrada, {r['avg_out']:.0f} de salida")
    if args.price_in is not None and args.price_out is not None:
        per_photo = (r["avg_in"] * args.price_in + r["avg_out"] * args.price_out) / 1_000_000
        print(f"Coste estimado: {per_photo * 100:.3f} USD/100 fotos")


if __name__ == "__main__":
    main()
