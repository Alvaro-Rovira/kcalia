"""Importar datos: CSV de MyFitnessPal, Yazio o genérico (con mapeo de columnas) y el JSON exportado por Kcalia.

Idempotente: cada fila importada recibe un client_id determinista (huella de sus datos), así que importar dos veces el
mismo fichero no duplica nada. Además se avisa de las filas que parecen ya apuntadas a mano (mismo día, momento y
calorías) para poder saltarlas.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .textnorm import normalize

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000
FIELDS = ("date", "slot", "name", "kcal", "protein", "carbs", "fat", "fiber", "grams")
REQUIRED = ("date", "kcal")

# Cabeceras habituales de cada campo (normalizadas: minúsculas, sin tildes ni signos).
ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "fecha", "dia", "day", "datum"),
    "slot": ("meal", "comida del dia", "momento", "daytime", "tipo de comida", "meal type", "comida"),
    "name": ("name", "nombre", "food", "alimento", "producto", "product", "description", "descripcion", "note"),
    "kcal": ("calories", "calorias", "energy", "energia", "kcal", "energy kcal", "energia kcal", "calories kcal"),
    "protein": ("protein", "proteina", "proteinas", "protein g", "proteinas g", "proteina g"),
    "carbs": (
        "carbohydrates",
        "carbohidratos",
        "hidratos",
        "carbs",
        "hidratos de carbono",
        "carbohydrates g",
        "carbohidratos g",
    ),
    "fat": ("fat", "grasa", "grasas", "fat g", "grasas g", "grasa g", "total fat"),
    "fiber": ("fiber", "fibra", "fiber g", "fibra g", "dietary fiber"),
    "grams": ("grams", "gramos", "amount", "cantidad", "peso", "weight g"),
}

SLOT_WORDS = {
    "desayuno": ("breakfast", "desayuno", "fruhstuck", "morning"),
    "comida": ("lunch", "comida", "almuerzo", "mittagessen"),
    "merienda": ("merienda", "afternoon"),
    "cena": ("dinner", "cena", "abendessen", "supper"),
    "snack": ("snack", "snacks", "tentempie", "picoteo", "other"),
}


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", normalize(header))).strip()


@dataclass
class Parsed:
    format: str
    columns: list[str]
    rows: list[dict[str, str]]


def read_csv(raw: bytes) -> Parsed:
    if len(raw) > MAX_BYTES:
        raise ValueError("El fichero pesa demasiado (máximo 5 MB).")
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    columns = [c for c in (reader.fieldnames or []) if c is not None]
    if not columns:
        raise ValueError("No encuentro columnas en el fichero.")
    rows = []
    for index, row in enumerate(reader):
        if index >= MAX_ROWS:
            break
        rows.append({k: (v or "").strip() for k, v in row.items() if k is not None})
    return Parsed(detect_format(columns), columns, rows)


def detect_format(columns: list[str]) -> str:
    plain = {_norm(c) for c in columns}
    if {"meal", "calories"} <= plain and any(c.startswith("fat") for c in plain):
        return "myfitnesspal"
    if "daytime" in plain or any("yazio" in c for c in plain):
        return "yazio"
    return "generico"


def guess_mapping(columns: list[str]) -> dict[str, str | None]:
    """Qué columna corresponde a cada campo, según el nombre de la cabecera (la primera que encaje)."""
    plain = {c: _norm(c) for c in columns}
    mapping: dict[str, str | None] = {}
    for key, aliases in ALIASES.items():
        found = next((c for c, p in plain.items() if p in aliases), None)
        if found is None:
            found = next((c for c, p in plain.items() if any(p.startswith(a + " ") for a in aliases)), None)
        mapping[key] = found
    # «Comida» suele ser el momento del día; si ya se usó como momento, no vale como nombre.
    if mapping.get("name") == mapping.get("slot"):
        mapping["name"] = None
    return mapping


def parse_number(text: str) -> float | None:
    text = (text or "").strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(text: str, month_first: bool = False) -> str | None:
    text = (text or "").strip()[:10]
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    patterns = (
        ("%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")
        if month_first
        else (
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%m/%d/%Y",
        )
    )
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def parse_slot(text: str) -> str:
    plain = _norm(text)
    for slot, words in SLOT_WORDS.items():
        if any(word in plain for word in words):
            return slot
    return "snack"


@dataclass
class Row:
    line: int
    date: str
    slot: str
    name: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float | None
    grams: float
    client_id: str = ""


@dataclass
class Prepared:
    rows: list[Row] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def prepare(parsed: Parsed, mapping: dict[str, str | None], month_first: bool = False, source: str = "") -> Prepared:
    out = Prepared()
    missing = [key for key in REQUIRED if not mapping.get(key)]
    if missing:
        names = {"date": "fecha", "kcal": "calorías"}
        out.errors.append(
            {"line": 0, "message": "Falta indicar la columna de " + " y ".join(names[m] for m in missing)}
        )
        return out
    seen: dict[str, int] = {}
    label = {"myfitnesspal": "MyFitnessPal", "yazio": "Yazio"}.get(source or parsed.format, "importada")
    for index, raw in enumerate(parsed.rows, start=2):

        def value(key: str, _raw: dict = raw) -> str:
            column = mapping.get(key)
            return _raw.get(column, "") if column else ""

        day = parse_date(value("date"), month_first)
        kcal = parse_number(value("kcal"))
        if day is None or kcal is None:
            # Filas de totales o vacías (sin calorías ni nombre) se ignoran sin dar error.
            if value("kcal") or value("name"):
                out.errors.append({"line": index, "message": "Sin fecha o calorías que se puedan leer"})
            continue
        if not 0 <= kcal <= 10000 or date.fromisoformat(day) > date.today():
            out.errors.append({"line": index, "message": "Calorías fuera de rango o fecha futura"})
            continue
        slot = parse_slot(value("slot")) if mapping.get("slot") else "snack"
        name = value("name")[:150] or f"{value('slot') or 'Comida'} ({label})"
        row = Row(
            line=index,
            date=day,
            slot=slot,
            name=name,
            kcal=round(kcal, 1),
            protein=round(max(0.0, parse_number(value("protein")) or 0), 1),
            carbs=round(max(0.0, parse_number(value("carbs")) or 0), 1),
            fat=round(max(0.0, parse_number(value("fat")) or 0), 1),
            fiber=parse_number(value("fiber")) if mapping.get("fiber") else None,
            grams=max(0.0, parse_number(value("grams")) or 0),
        )
        fingerprint = f"{row.date}|{row.slot}|{normalize(row.name)}|{row.kcal}|{row.protein}|{row.carbs}|{row.fat}"
        seen[fingerprint] = seen.get(fingerprint, 0) + 1
        # Filas idénticas del mismo fichero son comidas distintas (dos cafés): la repetición entra en la huella.
        row.client_id = "imp-" + hashlib.sha1(f"{fingerprint}|{seen[fingerprint]}".encode()).hexdigest()[:30]  # noqa: S324
        out.rows.append(row)
    return out


def meal_items(row: Row) -> list[dict]:
    item = {
        "name": row.name.lower()[:120],
        "qty": row.grams or 1,
        "unit": "g" if row.grams else "racion",
        "grams": min(5000.0, row.grams),
        "kcal": min(6000.0, row.kcal),
        "protein": min(600.0, row.protein),
        "carbs": min(1200.0, row.carbs),
        "fat": min(600.0, row.fat),
    }
    if row.fiber is not None:
        item["fiber"] = round(max(0.0, min(300.0, row.fiber)), 1)
    return [item]


# ---------------------------------------------------------------- JSON de Kcalia


def import_kcalia(db, data: dict) -> dict[str, int]:
    """Importa una exportación JSON de Kcalia sin duplicar ni pisar nada que ya exista. Devuelve lo creado."""
    from sqlalchemy import select

    from . import services
    from .matching import extras, totals
    from .models import (
        BodyMeasurement,
        DayType,
        Dish,
        Exercise,
        Food,
        Meal,
        MealPlan,
        Product,
        Profile,
        Targets,
        UserPrefs,
        WaterLog,
        Weight,
        Workout,
        WorkoutSet,
        WorkoutTemplate,
    )
    from .schemas import Item, Prefs, ProductIn, ProfileIn, TargetsIn
    from .textnorm import food_key

    if not isinstance(data, dict) or data.get("app") != "Kcalia":
        raise ValueError("No es una exportación de Kcalia.")
    counts: dict[str, int] = {}

    def bump(key: str) -> None:
        counts[key] = counts.get(key, 0) + 1

    def items_ok(raw) -> list[dict] | None:
        try:
            return [Item.model_validate(i).model_dump() for i in raw][:30] or None
        except Exception:
            return None

    if data.get("profile") and services.get_profile(db) is None:
        try:
            db.add(
                Profile(
                    **ProfileIn.model_validate(data["profile"]).model_dump(),
                    weight_unit=data["profile"].get("weight_unit", "kg"),
                )
            )
            bump("perfil")
        except Exception:
            pass
    if data.get("targets") and services.get_targets(db) is None:
        try:
            values = TargetsIn.model_validate(data["targets"]).model_dump()
            t = data["targets"]
            db.add(
                Targets(
                    **values,
                    bmr=int(t.get("bmr", 0)),
                    tdee=int(t.get("tdee", values["kcal"])),
                    custom=bool(t.get("custom")),
                    basis_weight_kg=float(t.get("basis_weight_kg", 70)),
                )
            )
            bump("objetivos")
        except Exception:
            pass
    if data.get("prefs") and db.scalar(select(UserPrefs)) is None:
        try:
            db.add(UserPrefs(data=Prefs.model_validate(data["prefs"]).model_dump(mode="json")))
            bump("preferencias")
        except Exception:
            pass

    existing = set(db.scalars(select(Meal.client_id)))
    for meal in data.get("meals", []):
        items = items_ok(meal.get("items", []))
        cid = str(meal.get("client_id", ""))[:40]
        day = str(meal.get("date", ""))
        if not items or not cid or cid in existing or parse_date(day) is None:
            continue
        servings = float(meal.get("servings") or 1)
        db.add(
            Meal(
                client_id=cid,
                date=day,
                slot=meal.get("slot") if meal.get("slot") in SLOT_WORDS else "snack",
                name=str(meal.get("name") or "Comida")[:160],
                text=str(meal.get("text") or "")[:600],
                items=items,
                servings=servings,
                source=str(meal.get("source") or "import")[:12],
                confidence=float(meal.get("confidence") or 0.8),
                assumptions=list(meal.get("assumptions") or [])[:12],
                **totals(items, servings),
                **extras(items, servings),
            )
        )
        existing.add(cid)
        bump("comidas")

    have = set(db.scalars(select(Weight.date)))
    for weight in data.get("weights", []):
        if weight.get("date") in have or parse_date(str(weight.get("date"))) is None:
            continue
        kg = parse_number(str(weight.get("kg")))
        if kg and 30 <= kg <= 300:
            db.add(Weight(date=weight["date"], kg=kg))
            have.add(weight["date"])
            bump("pesos")

    norms = set(db.scalars(select(Dish.norm)))
    for dish in data.get("dishes", []):
        items = items_ok(dish.get("items", []))
        norm = normalize(str(dish.get("text") or dish.get("name") or ""))
        if not items or not norm or norm in norms:
            continue
        db.add(
            Dish(
                name=str(dish.get("name"))[:160],
                text=str(dish.get("text") or dish.get("name"))[:600],
                norm=norm,
                items=items,
                **totals(items),
                favorite=bool(dish.get("favorite")),
                use_count=int(dish.get("use_count") or 0),
            )
        )
        norms.add(norm)
        bump("comidas conocidas")

    names = {n.lower() for n in db.scalars(select(Product.name))}
    barcodes = set(db.scalars(select(Product.barcode).where(Product.barcode.is_not(None))))
    for product in data.get("products", []):
        try:
            body = ProductIn.model_validate(product)
        except Exception:
            continue
        if body.name.lower() in names or (body.barcode and body.barcode in barcodes):
            continue
        db.add(Product(**body.model_dump(), has_image=False))
        names.add(body.name.lower())
        bump("productos")

    foods = set(db.scalars(select(Food.norm)))
    for food in data.get("foods", []):
        key = food_key(str(food.get("name", "")))
        if not key or key in foods:
            continue
        try:
            db.add(
                Food(
                    name=str(food["name"])[:120],
                    norm=key,
                    kcal100=float(food["kcal100"]),
                    protein100=float(food["protein100"]),
                    carbs100=float(food["carbs100"]),
                    fat100=float(food["fat100"]),
                    fiber100=food.get("fiber100"),
                    alcohol100=food.get("alcohol100"),
                    unit_grams=dict(food.get("unit_grams") or {}),
                )
            )
            foods.add(key)
            bump("ingredientes")
        except (KeyError, TypeError, ValueError):
            continue

    water = set(db.scalars(select(WaterLog.client_id)))
    for entry in data.get("water", []):
        cid, ml = str(entry.get("client_id", ""))[:40], parse_number(str(entry.get("ml")))
        if cid and cid not in water and ml and 0 < ml <= 3000 and parse_date(str(entry.get("date"))):
            db.add(WaterLog(client_id=cid, date=entry["date"], ml=int(ml)))
            water.add(cid)
            bump("agua")

    days = set(db.scalars(select(BodyMeasurement.date)))
    for entry in data.get("measurements", []):
        if entry.get("date") in days or parse_date(str(entry.get("date"))) is None:
            continue
        values = {k: entry.get(k) for k in ("waist", "chest", "arm", "hip", "thigh")}
        if any(isinstance(v, int | float) for v in values.values()):
            db.add(
                BodyMeasurement(
                    date=entry["date"], **{k: v if isinstance(v, int | float) else None for k, v in values.items()}
                )
            )
            days.add(entry["date"])
            bump("medidas")

    typed = set(db.scalars(select(DayType.date)))
    for day, kind in (data.get("day_types") or {}).items():
        if day not in typed and kind in ("entreno", "descanso") and parse_date(day):
            db.add(DayType(date=day, kind=kind))
            bump("tipos de día")

    exercise_ids = dict(db.execute(select(Exercise.client_id, Exercise.id)).all())
    for exercise in data.get("exercises", []):
        cid = str(exercise.get("client_id", ""))[:40]
        if cid and cid not in exercise_ids and exercise.get("name"):
            row = Exercise(
                client_id=cid,
                name=str(exercise["name"])[:80],
                muscle=str(exercise.get("muscle") or "otro")[:20],
                unit=exercise.get("unit") if exercise.get("unit") in ("reps", "seg", "min") else "reps",
                custom=bool(exercise.get("custom", True)),
                archived=bool(exercise.get("archived")),
            )
            db.add(row)
            db.flush()
            exercise_ids[cid] = row.id
            bump("ejercicios")
    templates = set(db.scalars(select(WorkoutTemplate.client_id)))
    for template in data.get("workout_templates", []):
        cid = str(template.get("client_id", ""))[:40]
        if cid and cid not in templates:
            db.add(
                WorkoutTemplate(
                    client_id=cid,
                    name=str(template.get("name") or "Rutina")[:60],
                    exercises=[e for e in template.get("exercises", []) if e.get("exercise") in exercise_ids],
                    position=int(template.get("position") or 0),
                )
            )
            templates.add(cid)
            bump("plantillas")
    workouts = set(db.scalars(select(Workout.client_id)))
    for workout in data.get("workouts", []):
        cid = str(workout.get("client_id", ""))[:40]
        if not cid or cid in workouts or parse_date(str(workout.get("date"))) is None:
            continue
        row = Workout(
            client_id=cid,
            date=workout["date"],
            name=str(workout.get("name") or "Entreno")[:60],
            notes=str(workout.get("notes") or "")[:1000],
            duration_min=workout.get("duration_min"),
            intensity=workout.get("intensity")
            if workout.get("intensity") in ("suave", "moderada", "intensa")
            else "moderada",
            started_at=_dt(workout.get("started_at")),
            ended_at=_dt(workout.get("ended_at")) if workout.get("ended_at") else None,
        )
        db.add(row)
        db.flush()
        for s in workout.get("sets", []):
            exercise_id = exercise_ids.get(s.get("exercise"))
            if exercise_id is None:
                continue
            db.add(
                WorkoutSet(
                    client_id=str(s.get("client_id"))[:40],
                    workout_id=row.id,
                    exercise_id=exercise_id,
                    position=int(s.get("position") or 0),
                    reps=int(s.get("reps") or 0),
                    weight=float(s.get("weight") or 0),
                    rpe=s.get("rpe"),
                )
            )
        workouts.add(cid)
        bump("entrenos")

    plans = set(db.scalars(select(MealPlan.client_id)))
    for plan in data.get("meal_plans", []):
        items = items_ok(plan.get("items", []))
        cid = str(plan.get("client_id", ""))[:40]
        if items and cid and cid not in plans and parse_date(str(plan.get("date"))):
            db.add(
                MealPlan(
                    client_id=cid,
                    date=plan["date"],
                    slot=plan.get("slot") if plan.get("slot") in SLOT_WORDS else "comida",
                    name=str(plan.get("name") or "Comida")[:160],
                    items=items,
                    servings=float(plan.get("servings") or 1),
                )
            )
            plans.add(cid)
            bump("plan")

    db.commit()
    return counts


def _dt(value) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.now()
