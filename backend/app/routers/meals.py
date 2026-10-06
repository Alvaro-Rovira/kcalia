from datetime import date as date_type

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..ai import AiClient, AiMeal, transcribe
from ..config import get_settings
from ..db import get_db
from ..deps import get_ai_client, require_approved_user, require_user, today_local
from ..matching import extras, totals
from ..models import Dish, DishAlias, Meal, User, utcnow
from ..products import resolve_text
from ..schemas import DishPatch, MealIn, MealPatch, ResolveIn
from ..textnorm import normalize
from ..usage import check_ai_budget, check_stt_budget, run_ai

router = APIRouter(prefix="/api", tags=["comidas"], dependencies=[Depends(require_approved_user)])

MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_AUDIO_BYTES = 12 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _product_note(items: list[dict]) -> str:
    names = ", ".join(dict.fromkeys(i["name"] for i in items if i.get("product_id")))
    return f"Calculado con la etiqueta que guardaste de: {names}"


def _draft_from_products(text: str, items: list[dict]) -> dict:
    names = list(dict.fromkeys(i["name"] for i in items))
    name = (" y ".join(names) if len(names) <= 2 else ", ".join(names))[:60]
    return {
        "name": name[:1].upper() + name[1:],
        "text": text,
        "items": items,
        **totals(items),
        "confidence": 0.9,
        "assumptions": [_product_note(items), "Sin consultar a la IA"],
        "source": "product",
        "dish_id": None,
        "favorite": False,
    }


def _with_products(draft: dict, product_items: list[dict]) -> dict:
    """Une los ingredientes de etiquetas guardadas con los que ha estimado la IA para el resto."""
    items = product_items + draft["items"]
    return {
        **draft,
        "items": items,
        **totals(items),
        "assumptions": [_product_note(product_items), *draft["assumptions"]],
    }


def _draft_from_ai(meal: AiMeal, text: str, source: str) -> dict:
    items = [item.model_dump() for item in meal.items]
    return {
        "name": meal.name or text[:60] or "Comida",
        "text": text,
        "items": items,
        **totals(items),
        "confidence": meal.confidence,
        "assumptions": meal.assumptions,
        "source": source,
        "dish_id": None,
        "favorite": False,
    }


@router.post("/meals/resolve")
def resolve(
    body: ResolveIn,
    db: Session = Depends(get_db),
    ai: AiClient = Depends(get_ai_client),
    user: User = Depends(require_user),
) -> dict:
    """Historial exacto -> historial aproximado -> caché de ingredientes -> IA."""
    text = body.text.strip()
    norm = normalize(text)
    if not norm:
        raise HTTPException(422, "Cuéntame qué has comido con un poco más de detalle.")

    use_history = not body.skip_history and not body.force_ai
    if use_history:
        exact = services.find_exact_dish(db, norm)
        if exact is not None:
            return {"status": "exact", "draft": {**services.draft_from_dish(exact, "exact"), "text": text}}
        similar = services.find_similar_dishes(db, norm)
        if similar:
            return {
                "status": "fuzzy",
                "candidates": [
                    {**services.draft_from_dish(dish, "fuzzy", score), "matched_text": dish.text, "text": text}
                    for dish, score in similar
                ],
            }

    product_items: list[dict] = []
    leftover = [text]
    if not body.force_ai:
        found = resolve_text(text, services.product_infos(db))
        if found.items:
            product_items, leftover = found.items, found.rest
            if not leftover:
                return {"status": "product", "draft": _draft_from_products(text, product_items)}

    leftover_text = ", ".join(leftover)
    if not body.force_ai:
        items = services.resolve_with_food_cache(db, leftover_text)
        if items and product_items:
            # Productos de etiqueta + ingredientes ya conocidos: todo se resuelve sin IA.
            return {"status": "product", "draft": _draft_from_products(text, product_items + items)}
        if items:
            return {
                "status": "cache",
                "draft": {
                    "name": text[:1].upper() + text[1:60],
                    "text": text,
                    "items": items,
                    **totals(items),
                    "confidence": 0.8,
                    "assumptions": ["Calculado con ingredientes que ya conocía, sin consultar a la IA"],
                    "source": "cache",
                    "dish_id": None,
                    "favorite": False,
                },
            }

    check_ai_budget(db, user)
    # A la IA solo va lo que no es de un producto guardado: menos tokens y las cifras de la etiqueta, intactas.
    meal = run_ai(db, "text", lambda: ai.analyze_text(leftover_text))
    if not meal.items:
        return {"status": "clarify", "question": meal.clarification}
    draft = _draft_from_ai(meal, text, "ai")
    if product_items:
        draft = _with_products(draft, product_items)
    return {"status": "ai", "draft": draft}


@router.post("/meals/photo")
def analyze_photo(
    image: UploadFile = File(...),
    note: str = Form(default="", max_length=300),
    db: Session = Depends(get_db),
    ai: AiClient = Depends(get_ai_client),
    user: User = Depends(require_user),
) -> dict:
    mime = (image.content_type or "").lower()
    if mime not in IMAGE_TYPES:
        raise HTTPException(415, "Ese formato de imagen no me vale. Prueba con una foto JPG o PNG.")
    data = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La foto pesa demasiado. Prueba con una más pequeña.")
    check_ai_budget(db, user)
    meal = run_ai(db, "vision", lambda: ai.analyze_photo(data, mime, note))
    if not meal.items:
        return {"status": "clarify", "question": meal.clarification}
    return {"status": "ai", "draft": _draft_from_ai(meal, "", "photo")}


@router.post("/transcribe")
def transcribe_audio(
    audio: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_user)
) -> dict:
    settings = get_settings()
    today = today_local(settings)
    check_stt_budget(db, user)
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "El audio es demasiado largo. Con 20 o 30 segundos es suficiente.")
    if len(data) < 800:
        raise HTTPException(422, "No he llegado a oír nada. Mantén pulsado y habla un par de segundos.")
    text = transcribe(settings, data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    services.record_usage(db, today, "stt", {"calls": 1})
    return {"text": text}


@router.get("/meals")
def list_meals(date: str, db: Session = Depends(get_db)) -> dict:
    try:
        date_type.fromisoformat(date)
    except ValueError as exc:
        raise HTTPException(422, "Esa fecha no es válida.") from exc
    meals = db.scalars(
        select(Meal).where(Meal.date == date, Meal.deleted_at.is_(None)).order_by(Meal.created_at, Meal.id)
    ).all()
    return {"date": date, "meals": [services.meal_dict(m) for m in meals]}


@router.get("/days")
def list_days(start: str, end: str, db: Session = Depends(get_db)) -> dict:
    return {"days": sorted(services.day_totals(db, start, end).values(), key=lambda d: d["date"])}


@router.post("/meals", status_code=201)
def create_meal(body: MealIn, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(Meal).where(Meal.client_id == body.client_id))
    if existing is not None:
        # Reintento de la cola offline: no se duplica.
        if existing.deleted_at is not None:
            existing.deleted_at = None
            db.commit()
        return services.meal_dict(existing)

    items = [item.model_dump() for item in body.items]
    macro = totals(items, body.servings)
    text = body.text.strip()

    from_products_only = all(item.get("product_id") for item in items)
    services.touch_products(db, items)

    dish: Dish | None = None
    if body.source in ("exact", "fuzzy", "favorite", "recent") and body.dish_id:
        dish = db.get(Dish, body.dish_id)
    if dish is not None:
        dish.use_count += 1
        dish.last_used_at = utcnow()
        if totals(dish.items) != totals(items):
            dish.items = items
            dish.kcal, dish.protein, dish.carbs, dish.fat = (
                totals(items)[m] for m in ("kcal", "protein", "carbs", "fat")
            )
        if body.source == "fuzzy" and text:
            norm = normalize(text)
            if norm and norm != dish.norm and services.find_alias(db, norm) is None:
                db.add(DishAlias(norm=norm, dish_id=dish.id))
    elif from_products_only:
        # Los productos ya son la memoria: no se duplican en el historial, y así editarlos cambia lo que sale.
        dish = None
    else:
        dish = services.upsert_dish(
            db,
            key_text=text or body.name,
            name=body.name,
            text=text,
            items=items,
            confidence=body.confidence,
            assumptions=body.assumptions,
            origin="photo" if body.source == "photo" else body.source,
        )

    services.learn_manual_items(db, items)
    if body.source in ("ai", "photo"):
        # Lo que viene de una etiqueta (o se añadió a mano) no se aprende como ingrediente de la IA.
        learnable = [item for item in items if not item.get("product_id") and not item.get("manual")]
        if learnable:
            services.learn_from_meal(
                db, text if body.source == "ai" and len(learnable) == len(items) else "", learnable
            )
    if body.source in services.SAVED_BY_SOURCE:
        services.bump(db, services.SAVED_BY_SOURCE[body.source])
    if body.via == "voice":
        services.bump(db, "voice_meals")
    if body.source == "photo":
        services.bump(db, "photo_meals")

    meal = Meal(
        client_id=body.client_id,
        date=body.date,
        slot=body.slot,
        name=body.name,
        text=text,
        items=items,
        servings=body.servings,
        source=body.source,
        confidence=body.confidence,
        assumptions=body.assumptions,
        dish_id=dish.id if dish else None,
        **macro,
        **extras(items, body.servings),
    )
    db.add(meal)
    db.commit()
    services.refresh_week_if_stored(db, meal.date, today_local())
    return services.meal_dict(meal)


def _get_meal(db: Session, client_id: str) -> Meal:
    # Se direcciona por client_id para que la cola offline pueda editar o borrar
    # una comida que creó antes de conocer su id de servidor.
    meal = db.scalar(select(Meal).where(Meal.client_id == client_id))
    if meal is None:
        raise HTTPException(404, "No encuentro esa comida. Puede que ya se hubiera borrado.")
    return meal


@router.patch("/meals/{client_id}")
def update_meal(client_id: str, body: MealPatch, db: Session = Depends(get_db)) -> dict:
    meal = _get_meal(db, client_id)
    old_date = meal.date
    if body.date:
        meal.date = body.date
    if body.slot:
        meal.slot = body.slot
    if body.name:
        meal.name = body.name
    if body.items is not None:
        meal.items = [item.model_dump() for item in body.items]
        services.learn_manual_items(db, meal.items)
    if body.servings is not None:
        meal.servings = body.servings
    macro = totals(meal.items, meal.servings)
    meal.kcal, meal.protein, meal.carbs, meal.fat = (macro[m] for m in ("kcal", "protein", "carbs", "fat"))
    meal.fiber, meal.alcohol = (extras(meal.items, meal.servings)[e] for e in ("fiber", "alcohol"))
    db.commit()
    today = today_local()
    services.refresh_week_if_stored(db, meal.date, today)
    if old_date != meal.date:
        services.refresh_week_if_stored(db, old_date, today)
    return services.meal_dict(meal)


@router.delete("/meals/{client_id}")
def delete_meal(client_id: str, db: Session = Depends(get_db)) -> dict:
    """Borrado lógico, para poder deshacerlo desde el aviso."""
    meal = _get_meal(db, client_id)
    meal.deleted_at = utcnow()
    db.commit()
    services.refresh_week_if_stored(db, meal.date, today_local())
    return {"ok": True}


@router.post("/meals/{client_id}/restore")
def restore_meal(client_id: str, db: Session = Depends(get_db)) -> dict:
    meal = _get_meal(db, client_id)
    meal.deleted_at = None
    db.commit()
    services.refresh_week_if_stored(db, meal.date, today_local())
    return services.meal_dict(meal)


@router.get("/foods")
def list_foods(db: Session = Depends(get_db)) -> dict:
    """Caché de ingredientes, para autocompletar al añadir uno a mano."""
    return {"foods": services.all_foods(db)}


@router.get("/dishes")
def list_dishes(db: Session = Depends(get_db)) -> dict:
    return {"dishes": services.all_dishes(db)}


@router.patch("/dishes/{dish_id}")
def update_dish(dish_id: int, body: DishPatch, db: Session = Depends(get_db)) -> dict:
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(404, "Esa comida ya no está en tu historial.")
    if body.favorite is not None:
        dish.favorite = body.favorite
    if body.name:
        dish.name = body.name
    db.commit()
    return services.dish_dict(dish)


@router.delete("/dishes/{dish_id}")
def delete_dish(dish_id: int, db: Session = Depends(get_db)) -> dict:
    dish = db.get(Dish, dish_id)
    if dish is not None:
        db.delete(dish)
        db.commit()
    return {"ok": True}
