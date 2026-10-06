"""Planificador semanal: comidas planificadas, macros frente al objetivo y lista de la compra marcable.

Sin IA salvo el botón opcional «rellenar huecos», que respeta todos los límites (ver usage.py).
"""

from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import services
from ..ai import AiClient
from ..db import get_db
from ..deps import get_ai_client, require_approved_user, require_user
from ..matching import extras, totals
from ..models import Dish, MealPlan, ShoppingCheck, User
from ..schemas import PlanFillIn, PlanIn, ShoppingCheckIn
from ..summary import week_start
from ..usage import check_ai_budget, run_ai

router = APIRouter(prefix="/api/plan", tags=["planificador"], dependencies=[Depends(require_approved_user)])

# Reparto orientativo del objetivo del día entre los momentos, para pedir ideas a la IA.
SLOT_SHARE = {"desayuno": 0.25, "comida": 0.35, "merienda": 0.1, "cena": 0.3, "snack": 0.1}


def _monday(value: str) -> date_type:
    try:
        return week_start(date_type.fromisoformat(value))
    except ValueError as exc:
        raise HTTPException(422, "Esa fecha no es válida.") from exc


def _entry(row: MealPlan) -> dict:
    return {
        "client_id": row.client_id,
        "date": row.date,
        "slot": row.slot,
        "name": row.name,
        "items": row.items,
        "servings": row.servings,
        "dish_id": row.dish_id,
        "source": row.source,
        **totals(row.items, row.servings),
        **extras(row.items, row.servings),
    }


@router.get("")
def week(start: str, db: Session = Depends(get_db)) -> dict:
    monday = _monday(start)
    sunday = monday + timedelta(days=6)
    rows = db.scalars(
        select(MealPlan)
        .where(MealPlan.date >= monday.isoformat(), MealPlan.date <= sunday.isoformat())
        .order_by(MealPlan.date, MealPlan.created_at, MealPlan.id)
    ).all()
    checks = db.scalars(select(ShoppingCheck).where(ShoppingCheck.week_start == monday.isoformat())).all()
    targets = services.get_targets(db)
    per_day = services.targets_by_day(db, monday, sunday, targets) if targets else {}
    return {
        "start": monday.isoformat(),
        "end": sunday.isoformat(),
        "entries": [_entry(r) for r in rows],
        "targets": per_day,
        "checks": {c.key: c.checked for c in checks},
    }


@router.put("")
def save(body: PlanIn, db: Session = Depends(get_db)) -> dict:
    """Crea o cambia una comida planificada (idempotente por client_id)."""
    row = db.scalar(select(MealPlan).where(MealPlan.client_id == body.client_id))
    if body.dish_id is not None and db.get(Dish, body.dish_id) is None:
        body.dish_id = None  # una comida conocida de otra cuenta (o ya borrada) no se enlaza
    values = body.model_dump(exclude={"client_id", "items"})
    items = [item.model_dump() for item in body.items]
    if row is None:
        row = MealPlan(client_id=body.client_id, items=items, **values)
        db.add(row)
    else:
        row.items = items
        for key, value in values.items():
            setattr(row, key, value)
    db.commit()
    return _entry(row)


@router.delete("/{client_id}")
def remove(client_id: str, db: Session = Depends(get_db)) -> dict:
    db.execute(delete(MealPlan).where(MealPlan.client_id == client_id))
    db.commit()
    return {"ok": True}


@router.put("/checks")
def check(body: ShoppingCheckIn, db: Session = Depends(get_db)) -> dict:
    monday = _monday(body.week_start).isoformat()
    row = db.scalar(select(ShoppingCheck).where(ShoppingCheck.week_start == monday, ShoppingCheck.key == body.key))
    if row is None:
        db.add(ShoppingCheck(week_start=monday, key=body.key, checked=body.checked))
    else:
        row.checked = body.checked
    db.commit()
    return {"ok": True}


@router.post("/fill")
def fill(
    body: PlanFillIn,
    db: Session = Depends(get_db),
    ai: AiClient = Depends(get_ai_client),
    user: User = Depends(require_user),
) -> dict:
    """Ideas de la IA para los huecos pedidos. No guarda nada: el usuario elige qué añadir."""
    monday = _monday(body.start)
    targets = services.get_targets(db)
    if targets is None:
        raise HTTPException(409, "Completa primero tu perfil.")
    per_day = services.targets_by_day(db, monday, monday + timedelta(days=6), targets)
    holes = []
    for hole in body.slots:
        day, slot = str(hole.get("date", "")), str(hole.get("slot", ""))
        if day not in per_day or slot not in SLOT_SHARE:
            raise HTTPException(422, "Hay un hueco que no es de esta semana o un momento del día que no existe.")
        holes.append(f"- {day} · {slot}: unas {round(per_day[day]['kcal'] * SLOT_SHARE[slot])} kcal")
    known = [d.name for d in db.scalars(select(Dish).order_by(Dish.use_count.desc()).limit(25))]
    request = "Huecos que rellenar:\n" + "\n".join(holes)
    if known:
        request += "\n\nPlatos que ya suele comer: " + "; ".join(known)
    check_ai_budget(db, user)
    reply = run_ai(db, "text", lambda: ai.suggest_plan(request))
    wanted = {(str(h.get("date")), str(h.get("slot"))) for h in body.slots}
    suggestions = []
    for meal in reply.meals:
        if (meal.date, meal.slot) not in wanted:
            continue
        items = [{**item.model_dump(), "alcohol": None} for item in meal.items]
        suggestions.append(
            {"date": meal.date, "slot": meal.slot, "name": meal.name or "Comida", "items": items, **totals(items)}
        )
    return {"suggestions": suggestions}
