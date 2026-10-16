"""Descarga una muestra de Nutrition5k para medir el análisis de fotos (scripts/bench_photos.py).

Nutrition5k (Google Research, CVPR 2021) son platos de cafetería fotografiados desde arriba, con cada ingrediente
pesado en báscula: da una referencia real de gramos y calorías. Licencia CC BY 4.0
(https://github.com/google-research-datasets/Nutrition5k). Solo usa la biblioteca estándar.

    python3 -I scripts/fetch_nutrition5k.py /ruta/vacia --n 20 --seed 2026

Elige al azar (semilla fija, para poder repetirlo) platos del conjunto de prueba con foto cenital, entre 150 y
1.200 kcal y entre 100 y 900 g, y guarda `dishes.json` y una carpeta por plato con su `rgb.png`.
"""

import argparse
import csv
import io
import json
import random
import sys
import urllib.request
from pathlib import Path

BASE = "https://storage.googleapis.com/nutrition5k_dataset/nutrition5k_dataset"
FIELDS_PER_INGREDIENT = 7  # id, nombre, gramos, kcal, grasa, hidratos, proteína


def get(path: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=60) as response:
        return response.read()


def dishes(metadata: str) -> dict[str, dict]:
    out = {}
    for row in csv.reader(io.StringIO(metadata)):
        if len(row) < 6 or (len(row) - 6) % FIELDS_PER_INGREDIENT:
            continue
        dish_id, kcal, mass, fat, carbs, protein = row[:6]
        ingredients = [
            {"name": row[i + 1], "grams": float(row[i + 2]), "kcal": float(row[i + 3])}
            for i in range(6, len(row), FIELDS_PER_INGREDIENT)
        ]
        out[dish_id] = {
            "id": dish_id,
            "kcal": float(kcal),
            "grams": float(mass),
            "fat": float(fat),
            "carbs": float(carbs),
            "protein": float(protein),
            "ingredients": ingredients,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path, help="Carpeta vacía donde guardar la muestra")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if any(args.out.iterdir()):
        sys.exit(f"{args.out} no está vacía")

    meta = dishes(get("metadata/dish_metadata_cafe1.csv").decode("utf-8"))
    test_ids = get("dish_ids/splits/rgb_test_ids.txt").decode("utf-8").split()
    pool = sorted(
        d for d in test_ids if d in meta and 150 <= meta[d]["kcal"] <= 1200 and 100 <= meta[d]["grams"] <= 900
    )
    random.Random(args.seed).shuffle(pool)

    chosen = []
    for dish_id in pool:
        if len(chosen) == args.n:
            break
        try:
            image = get(f"imagery/realsense_overhead/{dish_id}/rgb.png")
        except OSError as exc:
            print(f"  {dish_id}: sin foto ({exc})")
            continue
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            print(f"  {dish_id}: no es un PNG")
            continue
        folder = args.out / dish_id
        folder.mkdir()
        (folder / "rgb.png").write_bytes(image)
        chosen.append(meta[dish_id])
        print(f"  {dish_id}: {meta[dish_id]['kcal']:.0f} kcal, {meta[dish_id]['grams']:.0f} g, {len(image) // 1024} KB")

    (args.out / "dishes.json").write_text(json.dumps(chosen, ensure_ascii=False, indent=1))
    print(f"{len(chosen)} platos en {args.out} (de {len(pool)} candidatos)")


if __name__ == "__main__":
    main()
