"""Ideas de la IA para cerrar el día, solo si se piden con el botón. La sugerencia normal se calcula en el móvil."""

import math

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import AiClient
from ..db import get_db
from ..deps import get_ai_client, require_approved_user, require_user
from ..matching import totals
from ..models import Dish, User
from ..schemas import SuggestAiIn
from ..usage import check_ai_budget, run_ai

router = APIRouter(prefix="/api/suggest", tags=["sugerencias"], dependencies=[Depends(require_approved_user)])

MIN_FACTOR = 0.3


def _scale(items: list[dict], factor: float) -> list[dict]:
    keys = ("grams", "kcal", "protein", "carbs", "fat", "fiber")
    out = []
    for item in items:
        scaled = {**item, "qty": round(item["qty"] * factor, 2)}
        for key in keys:
            if scaled.get(key) is not None:
                scaled[key] = round(scaled[key] * factor, 1)
        out.append(scaled)
    return out


def fit_to(items: list[dict], kcal_left: float) -> list[dict] | None:
    """Recorta la ración (en pasos del 5 %) hasta que no se pase; None si haría falta una ración ridícula."""
    if totals(items)["kcal"] <= kcal_left:
        return items
    factor = math.floor(kcal_left / totals(items)["kcal"] * 20) / 20
    while factor >= MIN_FACTOR:
        scaled = _scale(items, factor)
        if totals(scaled)["kcal"] <= kcal_left:
            return scaled
        factor = round(factor - 0.05, 2)
    return None


@router.post("/ai")
def ai_ideas(
    body: SuggestAiIn,
    db: Session = Depends(get_db),
    ai: AiClient = Depends(get_ai_client),
    user: User = Depends(require_user),
) -> dict:
    check_ai_budget(db, user)
    known = [d.name for d in db.scalars(select(Dish).order_by(Dish.use_count.desc()).limit(20))]
    protein, carbs, fat = (max(0, round(v)) for v in (body.protein, body.carbs, body.fat))
    request = (
        f"Le quedan {round(body.kcal)} kcal para hoy, como máximo. Le faltan {protein} g de proteína; "
        f"margen de hidratos {carbs} g y de grasas {fat} g. Son las {body.hour}:00."
    )
    if known:
        request += " Cosas que suele comer: " + "; ".join(known) + "."
    reply = run_ai(db, "text", lambda: ai.suggest_close(request))
    ideas = []
    for idea in reply.ideas:
        items = [item.model_dump() for item in idea.items]
        if any((item.get("alcohol") or 0) > 0 for item in items):
            continue  # nada con alcohol
        fitted = fit_to(items, body.kcal)
        if fitted is None:
            continue
        ideas.append({"name": idea.name or "Idea", "items": fitted, **totals(fitted)})
    return {"ideas": ideas[:3]}
