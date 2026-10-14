"""Genera los extractos literales de CIQUAL 2025 y USDA FoodData Central que usa la tabla de alimentos.

Solo hace falta al añadir o cambiar alimentos en `backend/app/data/alimentos.json`. Copia, sin tocarlas, las cifras
de las filas que esa tabla referencia (energía, proteína, hidratos, grasa, fibra y alcohol) a
`backend/app/data/ciqual_2025.tsv` y `backend/app/data/usda_fdc.tsv`. Los ficheros oficiales no se suben al repo:

    Excel de CIQUAL 2025: https://ciqual.anses.fr/ (Téléchargement)
    CSV de USDA: https://fdc.nal.usda.gov/download-datasets (SR Legacy y FNDDS)

Uso, desde la raíz del repo:

    uv run --with openpyxl python scripts/food_sources.py --ciqual "Table Ciqual 2025_FR_2025_11_03.xlsx" \\
        --usda FoodData_Central_sr_legacy_food_csv_2018-04 FoodData_Central_survey_food_csv_2024-10-31
"""

import argparse
import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "backend" / "app" / "data"
FIELDS = ("kcal", "protein", "carbs", "fat", "fiber", "alcohol")
USDA_FIELDS = ("kcal", "protein", "carbs_total", "fat", "fiber", "alcohol")
# Nutrientes de FoodData Central. SR Legacy usa el identificador nuevo (1008…) y FNDDS el número antiguo (208…).
USDA_NUTRIENTS = {
    "1008": "kcal",
    "1003": "protein",
    "1005": "carbs_total",
    "1004": "fat",
    "1079": "fiber",
    "1018": "alcohol",
    "208": "kcal",
    "203": "protein",
    "205": "carbs_total",
    "204": "fat",
    "291": "fiber",
    "221": "alcohol",
}


def used_codes() -> dict[str, set[str]]:
    codes: dict[str, set[str]] = {"ciqual": set(), "usda": set()}
    for spec in json.loads((DATA / "alimentos.json").read_text(encoding="utf-8")):
        source, _, code = spec["ref"].partition(":")
        codes[source].add(code)
    return codes


def _column(header: list[str], *needles: str) -> int:
    for index, name in enumerate(header):
        flat = " ".join(name.split())
        if all(needle in flat for needle in needles):
            return index
    raise SystemExit(f"No encuentro la columna {needles} en el Excel de CIQUAL")


def ciqual(path: Path, codes: set[str]) -> None:
    import openpyxl

    rows = openpyxl.load_workbook(path, read_only=True).worksheets[0].iter_rows(values_only=True)
    header = [str(h or "") for h in next(rows)]
    columns = {
        "code": _column(header, "alim_code"),
        "name": _column(header, "alim_nom_fr"),
        "kcal": _column(header, "Règlement", "kcal"),
        "protein": _column(header, "Protéines", "6.25"),
        "carbs": _column(header, "Glucides"),
        "fat": _column(header, "Lipides"),
        "fiber": _column(header, "Fibres"),
        "alcohol": _column(header, "Alcool"),
    }
    found = {}
    for row in rows:
        code = str(row[columns["code"]] or "").strip()
        if code in codes:
            found[code] = ["" if row[columns[k]] is None else str(row[columns[k]]).strip() for k in ("name", *FIELDS)]
    _write(DATA / "ciqual_2025.tsv", ("code", "name", *FIELDS), found, codes)


def usda(directories: list[Path], codes: set[str]) -> None:
    names: dict[str, str] = {}
    values: dict[str, dict[str, str]] = {code: {} for code in codes}
    for directory in directories:
        with (directory / "food.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["fdc_id"] in codes:
                    names[row["fdc_id"]] = row["description"]
        with (directory / "food_nutrient.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                field = USDA_NUTRIENTS.get(row["nutrient_id"])
                if field and row["fdc_id"] in codes:
                    values[row["fdc_id"]][field] = row["amount"]
    found = {code: [names[code], *(values[code].get(f, "") for f in USDA_FIELDS)] for code in names}
    empty = sorted(code for code, row in found.items() if not row[1])
    if empty:
        raise SystemExit(f"usda_fdc.tsv: filas sin energía {empty}")
    _write(DATA / "usda_fdc.tsv", ("code", "name", *USDA_FIELDS), found, codes)


def _write(path: Path, header: tuple[str, ...], found: dict[str, list[str]], wanted: set[str]) -> None:
    missing = sorted(wanted - set(found))
    if missing:
        raise SystemExit(f"{path.name}: no están en la fuente {missing}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        for code in sorted(found, key=int):
            writer.writerow([code, *found[code]])
    print(f"{path.name}: {len(found)} filas")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ciqual", type=Path, required=True, help="Excel oficial de CIQUAL 2025 (.xlsx)")
    parser.add_argument("--usda", type=Path, nargs="+", required=True, help="carpetas CSV de FoodData Central")
    args = parser.parse_args()
    codes = used_codes()
    ciqual(args.ciqual, codes["ciqual"])
    usda(args.usda, codes["usda"])


if __name__ == "__main__":
    main()
