"""Operaciones de base de datos compartidas por los routers."""

from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import summary as summary_lib
from . import tenancy
from .matching import FoodInfo, FoodUpdate, find_similar, learn_foods, resolve_from_foods, totals
from .models import (
    Achievement,
    AiUsage,
    AppSetting,
    Counter,
    Dish,
    DishAlias,
    Food,
    Meal,
    Product,
    ProductImage,
    Profile,
    Targets,
    WeeklySummary,
    Weight,
    utcnow,
)
from .nutrition import calculate_targets
from .products import ProductInfo
from .textnorm import normalize

SAVED_KEYS = ("saved_exact", "saved_fuzzy", "saved_cache", "saved_quick", "saved_product")
SAVED_BY_SOURCE = {
    "exact": "saved_exact",
    "fuzzy": "saved_fuzzy",
    "cache": "saved_cache",
    "favorite": "saved_quick",
    "recent": "saved_quick",
    "product": "saved_product",
}


# ---------------------------------------------------------------- contadores


def bump(db: Session, key: str, amount: int = 1) -> None:
    counter = db.scalar(select(Counter).where(Counter.key == key))
    if counter is None:
        db.add(Counter(key=key, value=amount))
    else:
        counter.value += amount


def counters(db: Session) -> dict[str, int]:
    return {c.key: c.value for c in db.scalars(select(Counter))}


AI_KINDS = ("text", "vision")


def ai_calls_today(db: Session, today: date, kinds: tuple[str, ...] = AI_KINDS) -> int:
    """Consultas de hoy del usuario de la sesión."""
    total = db.scalar(
        select(func.coalesce(func.sum(AiUsage.calls), 0)).where(
            AiUsage.date == today.isoformat(), AiUsage.kind.in_(kinds)
        )
    )
    return int(total or 0)


def global_calls_today(db: Session, today: date, kinds: tuple[str, ...] = AI_KINDS) -> int:
    """Consultas de hoy de todos los usuarios juntos: el tope global de la instalación."""
    with tenancy.unscoped(db):
        return ai_calls_today(db, today, kinds)


# ---------------------------------------------------------------- ajustes globales


def app_setting(db: Session, key: str, default=None):
    row = db.get(AppSetting, key)
    return default if row is None or row.value is None else row.value


def set_app_setting(db: Session, key: str, value) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = utcnow()


def ai_paused(db: Session) -> bool:
    return bool(app_setting(db, "ai_paused", False))


def record_usage(db: Session, today: date, kind: str, usage: dict) -> None:
    row = db.scalar(select(AiUsage).where(AiUsage.date == today.isoformat(), AiUsage.kind == kind))
    if row is None:
        row = AiUsage(date=today.isoformat(), kind=kind, calls=0, prompt_tokens=0, completion_tokens=0)
        db.add(row)
    row.calls += usage.get("calls", 1)
    row.prompt_tokens += usage.get("prompt_tokens", 0)
    row.completion_tokens += usage.get("completion_tokens", 0)
    db.commit()


# ---------------------------------------------------------------- perfil y objetivos


def get_profile(db: Session) -> Profile | None:
    return db.scalar(select(Profile).limit(1))


def get_targets(db: Session) -> Targets | None:
    return db.scalar(select(Targets).limit(1))


def profile_dict(profile: Profile) -> dict:
    return {
        "sex": profile.sex,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "activity": profile.activity,
        "goal": profile.goal,
        "target_weight_kg": profile.target_weight_kg,
        "weight_unit": profile.weight_unit,
    }


def targets_dict(targets: Targets) -> dict:
    return {
        "kcal": targets.kcal,
        "protein": targets.protein,
        "carbs": targets.carbs,
        "fat": targets.fat,
        "bmr": targets.bmr,
        "tdee": targets.tdee,
        "custom": targets.custom,
        "basis_weight_kg": targets.basis_weight_kg,
    }


def plan_for(profile: Profile) -> dict:
    return calculate_targets(
        sex=profile.sex,
        age=profile.age,
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        activity=profile.activity,
        goal=profile.goal,
        target_weight_kg=profile.target_weight_kg,
    )


def apply_plan(db: Session, profile: Profile) -> tuple[Targets, dict]:
    plan = plan_for(profile)
    targets = get_targets(db)
    values = {
        "kcal": plan["kcal"],
        "protein": plan["protein"],
        "carbs": plan["carbs"],
        "fat": plan["fat"],
        "bmr": plan["bmr"],
        "tdee": plan["tdee"],
        "custom": False,
        "basis_weight_kg": profile.weight_kg,
    }
    if targets is None:
        targets = Targets(**values)
        db.add(targets)
    else:
        for key, value in values.items():
            setattr(targets, key, value)
    return targets, plan


# ---------------------------------------------------------------- comidas e historial


USAGE_WINDOW_DAYS = 120


def slot_usage(db: Session, today: date | None = None) -> tuple[dict[int, dict[str, int]], dict[int, dict[str, int]]]:
    """Cuántas veces se ha comido cada comida conocida y cada producto en cada momento del día (últimos meses).

    Sirve para ordenar favoritos y recientes según la hora: el café por la mañana, la cena por la noche.
    """
    since = ((today or date.today()) - timedelta(days=USAGE_WINDOW_DAYS)).isoformat()
    dishes: dict[int, dict[str, int]] = {}
    products: dict[int, dict[str, int]] = {}
    rows = db.execute(select(Meal.dish_id, Meal.slot, Meal.items).where(Meal.deleted_at.is_(None), Meal.date >= since))
    for dish_id, slot, items in rows:
        if dish_id:
            counts = dishes.setdefault(dish_id, {})
            counts[slot] = counts.get(slot, 0) + 1
        for product_id in {item.get("product_id") for item in items or [] if item.get("product_id")}:
            counts = products.setdefault(product_id, {})
            counts[slot] = counts.get(slot, 0) + 1
    return dishes, products


def dish_dict(dish: Dish, aliases: list[str] | None = None, slot_counts: dict[str, int] | None = None) -> dict:
    return {
        "id": dish.id,
        "name": dish.name,
        "text": dish.text,
        "norm": dish.norm,
        "aliases": aliases or [],
        "items": dish.items,
        "kcal": dish.kcal,
        "protein": dish.protein,
        "carbs": dish.carbs,
        "fat": dish.fat,
        "confidence": dish.confidence,
        "assumptions": dish.assumptions,
        "origin": dish.origin,
        "favorite": dish.favorite,
        "use_count": dish.use_count,
        "last_used_at": dish.last_used_at.isoformat() + "Z",
        "slot_counts": slot_counts or {},
    }


def all_dishes(db: Session, limit: int = 600, usage: dict[int, dict[str, int]] | None = None) -> list[dict]:
    dishes = db.scalars(select(Dish).order_by(Dish.last_used_at.desc()).limit(limit)).all()
    aliases: dict[int, list[str]] = {}
    for alias in db.scalars(select(DishAlias)):
        aliases.setdefault(alias.dish_id, []).append(alias.norm)
    if usage is None:
        usage = slot_usage(db)[0]
    return [dish_dict(d, aliases.get(d.id), usage.get(d.id)) for d in dishes]


def meal_dict(meal: Meal) -> dict:
    return {
        "id": meal.id,
        "client_id": meal.client_id,
        "date": meal.date,
        "slot": meal.slot,
        "name": meal.name,
        "text": meal.text,
        "items": meal.items,
        "servings": meal.servings,
        "kcal": meal.kcal,
        "protein": meal.protein,
        "carbs": meal.carbs,
        "fat": meal.fat,
        "source": meal.source,
        "confidence": meal.confidence,
        "assumptions": meal.assumptions,
        "dish_id": meal.dish_id,
        "created_at": meal.created_at.isoformat() + "Z",
    }


def draft_from_dish(dish: Dish, source: str, score: float | None = None) -> dict:
    draft = {
        "name": dish.name,
        "text": dish.text,
        "items": dish.items,
        **totals(dish.items),
        "confidence": dish.confidence,
        "assumptions": dish.assumptions,
        "source": source,
        "dish_id": dish.id,
        "favorite": dish.favorite,
    }
    if score is not None:
        draft["score"] = score
    return draft


def find_alias(db: Session, norm: str) -> DishAlias | None:
    return db.scalar(select(DishAlias).where(DishAlias.norm == norm))


def find_exact_dish(db: Session, norm: str) -> Dish | None:
    dish = db.scalar(select(Dish).where(Dish.norm == norm))
    if dish is not None:
        return dish
    alias = find_alias(db, norm)
    return db.get(Dish, alias.dish_id) if alias else None


def find_similar_dishes(db: Session, norm: str) -> list[tuple[Dish, float]]:
    candidates = [(d.id, d.norm) for d in db.execute(select(Dish.id, Dish.norm))]
    candidates += [(a.dish_id, a.norm) for a in db.scalars(select(DishAlias))]
    found: dict[int, float] = {}
    for dish_id, score in find_similar(norm, candidates, limit=6):
        found[dish_id] = max(score, found.get(dish_id, 0))
    ranked = sorted(found.items(), key=lambda pair: pair[1], reverse=True)[:3]
    return [(db.get(Dish, dish_id), score) for dish_id, score in ranked]


def resolve_with_food_cache(db: Session, text: str) -> list[dict] | None:
    def lookup(key: str) -> FoodInfo | None:
        food = db.scalar(select(Food).where(Food.norm == key))
        if food is None:
            return None
        return FoodInfo(food.name, food.kcal100, food.protein100, food.carbs100, food.fat100, food.unit_grams or {})

    return resolve_from_foods(text, lookup)


def store_foods(db: Session, updates: list[FoodUpdate]) -> None:
    for update in updates:
        food = db.scalar(select(Food).where(Food.norm == update.key))
        if food is None:
            db.add(
                Food(
                    name=update.name,
                    norm=update.key,
                    kcal100=update.kcal100,
                    protein100=update.protein100,
                    carbs100=update.carbs100,
                    fat100=update.fat100,
                    unit_grams=update.unit_grams,
                )
            )
        else:
            food.kcal100, food.protein100 = update.kcal100, update.protein100
            food.carbs100, food.fat100 = update.carbs100, update.fat100
            food.unit_grams = {**(food.unit_grams or {}), **update.unit_grams}
            food.hits += 1


def upsert_dish(
    db: Session,
    *,
    key_text: str,
    name: str,
    text: str,
    items: list[dict],
    confidence: float,
    assumptions: list[str],
    origin: str,
) -> Dish | None:
    norm = normalize(key_text)
    if not norm:
        return None
    dish = find_exact_dish(db, norm)
    macro = totals(items)
    if dish is None:
        dish = Dish(
            norm=norm,
            name=name,
            text=text or name,
            items=items,
            confidence=confidence,
            assumptions=assumptions,
            origin=origin,
            use_count=0,
            **macro,
        )
        db.add(dish)
    else:
        # Si el usuario corrigió el desglose, el historial aprende la versión corregida.
        dish.name, dish.items = name, items
        dish.kcal, dish.protein, dish.carbs, dish.fat = (macro[m] for m in ("kcal", "protein", "carbs", "fat"))
        dish.confidence, dish.assumptions = confidence, assumptions
    dish.use_count += 1
    dish.last_used_at = utcnow()
    db.flush()
    return dish


def learn_from_meal(db: Session, text: str, items: list[dict]) -> None:
    store_foods(db, learn_foods(text, items))


def learn_manual_items(db: Session, items: list[dict]) -> None:
    """Los ingredientes añadidos a mano entran en la caché: la próxima vez salen al autocompletar y sin IA."""
    manual = [item for item in items if item.get("manual") and not item.get("product_id") and item.get("grams", 0) > 0]
    if manual:
        store_foods(db, learn_foods("", manual))


def food_dict(food: Food) -> dict:
    return {
        "name": food.name,
        "norm": food.norm,
        "kcal100": food.kcal100,
        "protein100": food.protein100,
        "carbs100": food.carbs100,
        "fat100": food.fat100,
        "unit_grams": food.unit_grams or {},
    }


def all_foods(db: Session, limit: int = 1500) -> list[dict]:
    """Caché de ingredientes del usuario, los más usados primero (para autocompletar en el móvil)."""
    foods = db.scalars(select(Food).order_by(Food.hits.desc(), Food.updated_at.desc()).limit(limit))
    return [food_dict(f) for f in foods]


# ---------------------------------------------------------------- productos


def product_dict(product: Product, slot_counts: dict[str, int] | None = None) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "alias": product.alias,
        "basis": product.basis,
        "kcal100": product.kcal100,
        "protein100": product.protein100,
        "carbs100": product.carbs100,
        "fat100": product.fat100,
        "fiber100": product.fiber100,
        "sugars100": product.sugars100,
        "salt100": product.salt100,
        "unit_label": product.unit_label,
        "unit_grams": product.unit_grams,
        "has_image": product.has_image,
        "barcode": product.barcode,
        "slot_counts": slot_counts or {},
        "use_count": product.use_count,
        "last_used_at": product.last_used_at.isoformat() + "Z",
        "created_at": product.created_at.isoformat() + "Z",
    }


def all_products(db: Session) -> list[Product]:
    """Los más usados primero: al empatar al emparejar, gana el que más se usa."""
    return list(db.scalars(select(Product).order_by(Product.use_count.desc(), Product.last_used_at.desc())))


def product_infos(db: Session) -> list[ProductInfo]:
    return [
        ProductInfo(
            p.id, p.name, p.alias, p.basis, p.kcal100, p.protein100, p.carbs100, p.fat100, p.unit_label, p.unit_grams
        )
        for p in all_products(db)
    ]


def touch_products(db: Session, items: list[dict]) -> None:
    """Cuenta el uso de los productos que aparecen en una comida guardada."""
    ids = {item.get("product_id") for item in items if item.get("product_id")}
    for product in db.scalars(select(Product).where(Product.id.in_(ids))) if ids else []:
        product.use_count += 1
        product.last_used_at = utcnow()


# ---------------------------------------------------------------- totales por día


def day_totals(db: Session, start: str | None = None, end: str | None = None) -> dict[str, dict]:
    query = (
        select(
            Meal.date,
            func.sum(Meal.kcal),
            func.sum(Meal.protein),
            func.sum(Meal.carbs),
            func.sum(Meal.fat),
            func.count(Meal.id),
        )
        .where(Meal.deleted_at.is_(None))
        .group_by(Meal.date)
    )
    if start:
        query = query.where(Meal.date >= start)
    if end:
        query = query.where(Meal.date <= end)
    return {
        row[0]: {"date": row[0], "kcal": row[1], "protein": row[2], "carbs": row[3], "fat": row[4], "meals": row[5]}
        for row in db.execute(query)
    }


def weights_map(db: Session) -> dict[str, float]:
    return {w.date: w.kg for w in db.scalars(select(Weight))}


# ---------------------------------------------------------------- resúmenes semanales


def compute_week(db: Session, start: date, today: date, targets: Targets) -> dict:
    end = start + timedelta(days=6)
    prev_start = start - timedelta(days=7)
    days = day_totals(db, prev_start.isoformat(), end.isoformat())
    weights = weights_map(db)
    tdict = targets_dict(targets)
    previous = summary_lib.build_week_summary(start=prev_start, today=today, days=days, targets=tdict, weights=weights)
    return summary_lib.build_week_summary(
        start=start, today=today, days=days, targets=tdict, weights=weights, previous=previous
    )


def store_week(db: Session, start: date, today: date) -> dict | None:
    targets = get_targets(db)
    if targets is None:
        return None
    data = compute_week(db, start, today, targets)
    if data["logged_days"] == 0:
        return None
    row = db.scalar(select(WeeklySummary).where(WeeklySummary.week_start == start.isoformat()))
    if row is None:
        db.add(WeeklySummary(week_start=start.isoformat(), data=data))
    else:
        row.data = data
        row.created_at = utcnow()
    db.commit()
    return data


def ensure_summaries(db: Session, today: date, include_current: bool = False) -> int:
    """Guarda el resumen de cada semana terminada que tenga registros y aún no lo tenga."""
    first = db.scalar(select(func.min(Meal.date)).where(Meal.deleted_at.is_(None)))
    if first is None:
        return 0
    current_week = summary_lib.week_start(today)
    week = summary_lib.week_start(date.fromisoformat(first))
    stored = set(db.scalars(select(WeeklySummary.week_start)))
    created = 0
    while week < current_week or (include_current and week == current_week):
        if week.isoformat() not in stored and store_week(db, week, today):
            created += 1
        week += timedelta(days=7)
    return created


def refresh_week_if_stored(db: Session, iso_date: str, today: date) -> None:
    """Un cambio en un día de una semana ya resumida rehace ese resumen."""
    start = summary_lib.week_start(date.fromisoformat(iso_date))
    if db.scalar(select(WeeklySummary.id).where(WeeklySummary.week_start == start.isoformat())):
        store_week(db, start, today)


# ---------------------------------------------------------------- racha y logros


def compute_stats(db: Session, today: date, ai_limit: int) -> dict:
    """Racha, logros y uso de IA del usuario de la sesión; `ai_limit` es su límite diario."""
    targets = get_targets(db)
    profile = get_profile(db)
    days = day_totals(db)
    count = counters(db)
    saved = {key: count.get(key, 0) for key in SAVED_KEYS}
    saved_total = sum(saved.values())

    statuses: dict[str, str] = {}
    weekly_on_target: dict[str, int] = {}
    weekly_protein: dict[str, int] = {}
    if targets is not None:
        for iso, day in days.items():
            statuses[iso] = summary_lib.day_status(day["kcal"], targets.kcal)
            week = summary_lib.week_start(date.fromisoformat(iso)).isoformat()
            if statuses[iso] == "cumplido":
                weekly_on_target[week] = weekly_on_target.get(week, 0) + 1
            if summary_lib.protein_met(day["protein"], targets.protein):
                weekly_protein[week] = weekly_protein.get(week, 0) + 1
    streak = summary_lib.streak(statuses, today)

    meals = db.scalar(select(func.count(Meal.id)).where(Meal.deleted_at.is_(None))) or 0
    weights = db.scalars(select(Weight).order_by(Weight.date)).all()
    target_reached = False
    if profile and profile.target_weight_kg and len(weights) >= 2:
        first, last, goal = weights[0].kg, weights[-1].kg, profile.target_weight_kg
        target_reached = (first > goal >= last) or (first < goal <= last)

    unlocked_now = summary_lib.evaluate_achievements(
        {
            "meals": meals,
            "best_streak": streak["best"],
            "max_on_target_week": max(weekly_on_target.values(), default=0),
            "max_protein_week": max(weekly_protein.values(), default=0),
            "weights": len(weights),
            "target_reached": target_reached,
            "saved": saved_total,
            "favorites": db.scalar(select(func.count(Dish.id)).where(Dish.favorite.is_(True))) or 0,
            "photos": count.get("photo_meals", 0),
            "voice": count.get("voice_meals", 0),
        }
    )
    stored = {a.key: a for a in db.scalars(select(Achievement))}  # solo los del usuario de la sesión
    fresh = sorted(unlocked_now - stored.keys())
    for key in fresh:
        achievement = Achievement(key=key)
        db.add(achievement)
        stored[key] = achievement
    if fresh:
        db.commit()

    achievements = [
        {
            **definition,
            "unlocked_at": stored[definition["key"]].unlocked_at.isoformat() + "Z"
            if definition["key"] in stored
            else None,
        }
        for definition in summary_lib.ACHIEVEMENTS
    ]
    return {
        "streak": streak,
        "achievements": achievements,
        "new_achievements": fresh,
        "ai": {
            "used_today": ai_calls_today(db, today),
            "limit": ai_limit,
            "saved_total": saved_total,
            "saved": saved,
            "calls_total": int(
                db.scalar(select(func.coalesce(func.sum(AiUsage.calls), 0)).where(AiUsage.kind != "stt")) or 0
            ),
        },
        "counts": {"meals": meals, "weights": len(weights), "days": len(days)},
    }


# ---------------------------------------------------------------- borrado


def wipe_data(db: Session) -> None:
    """Borra todos los datos del usuario de la sesión (el filtro por usuario se aplica también a los DELETE)."""
    if tenancy.current_user_id(db) is None:
        raise tenancy.TenancyError("wipe_data necesita una sesión limitada a un usuario")
    for model in (
        Meal,
        DishAlias,
        Dish,
        Food,
        ProductImage,
        Product,
        Weight,
        WeeklySummary,
        Achievement,
        Counter,
        AiUsage,
        Targets,
        Profile,
    ):
        db.execute(delete(model))
    db.commit()


def delete_user(db: Session, user) -> None:
    """Borra la cuenta y todo lo suyo. Las tablas de datos también caen en cascada desde `users`."""
    from .models import AuthSession, User

    with tenancy.as_user(db, user.id):
        wipe_data(db)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
