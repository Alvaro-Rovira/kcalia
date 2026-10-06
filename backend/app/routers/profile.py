from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..config import get_settings
from ..db import get_db
from ..deps import get_ai_client, require_approved_user, require_user, today_local
from ..models import Profile, User, Weight
from ..nutrition import calculate_targets, validate_custom_targets
from ..schemas import PrefsIn, ProfileIn, ProfileSave, TargetsIn
from ..usage import ai_limit_for, stt_limit_for
from ..workouts import estimated_kcal_by_day

router = APIRouter(prefix="/api", tags=["perfil"], dependencies=[Depends(require_approved_user)])


@router.get("/bootstrap")
def bootstrap(user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    """Todo lo que la app necesita al arrancar, en una sola petición."""
    settings = get_settings()
    profile = services.get_profile(db)
    targets = services.get_targets(db)
    today = today_local(settings)
    dish_usage, product_usage = services.slot_usage(db, today)
    prefs = services.get_prefs(db)
    return {
        "user": {"username": user.username, "is_admin": user.is_admin},
        "profile": services.profile_dict(profile) if profile else None,
        "targets": services.targets_dict(targets) if targets else None,
        "plan": services.plan_for(profile) if profile else None,
        "dishes": services.all_dishes(db, usage=dish_usage),
        "products": [services.product_dict(p, product_usage.get(p.id)) for p in services.all_products(db)],
        "foods": services.all_foods(db),
        "prefs": prefs.model_dump(),
        "suggest_min_kcal_default": settings.suggest_min_kcal,
        "exercise_kcal": estimated_kcal_by_day(db, (today - timedelta(days=60)).isoformat(), today.isoformat()),
        # Días con tipo cambiado a mano (cerca de hoy): con esto y las preferencias, el móvil calcula sin red.
        "day_types": services.day_type_overrides(
            db, (today - timedelta(days=120)).isoformat(), (today + timedelta(days=60)).isoformat()
        ),
        "water_goal_ml": services.water_goal(db, prefs),
        "ai": {
            "configured": get_ai_client().configured,
            "model": settings.ai_model,
            "used_today": services.ai_calls_today(db, today),
            "limit": ai_limit_for(user, settings),
            "paused": services.ai_paused(db),
            "stt_used_today": services.ai_calls_today(db, today, ("stt",)),
            "stt_limit": stt_limit_for(user, settings),
        },
        "server_date": today.isoformat(),
    }


@router.post("/plan/preview")
def preview_plan(body: ProfileIn) -> dict:
    return calculate_targets(**body.model_dump())


@router.put("/profile")
def save_profile(body: ProfileSave, db: Session = Depends(get_db)) -> dict:
    profile = services.get_profile(db)
    data = body.model_dump(exclude={"recalculate", "today"})
    first_time = profile is None
    if profile is None:
        profile = Profile(**data)
        db.add(profile)
    else:
        for key, value in data.items():
            setattr(profile, key, value)
    db.flush()

    targets = services.get_targets(db)
    plan = services.plan_for(profile)
    if targets is None or body.recalculate:
        targets, plan = services.apply_plan(db, profile)

    if first_time:
        day = body.today or today_local().isoformat()
        if db.scalar(select(Weight).where(Weight.date == day)) is None:
            db.add(Weight(date=day, kg=profile.weight_kg))
    db.commit()
    return {
        "profile": services.profile_dict(profile),
        "targets": services.targets_dict(targets),
        "plan": plan,
    }


@router.patch("/profile/prefs")
def save_prefs(body: PrefsIn, db: Session = Depends(get_db)) -> dict:
    profile = services.get_profile(db)
    if profile is None:
        raise HTTPException(409, "Completa primero tu perfil.")
    profile.weight_unit = body.weight_unit
    db.commit()
    return services.profile_dict(profile)


@router.put("/targets")
def save_targets(body: TargetsIn, db: Session = Depends(get_db)) -> dict:
    profile, targets = services.get_profile(db), services.get_targets(db)
    if profile is None or targets is None:
        raise HTTPException(409, "Completa primero tu perfil.")
    targets.kcal, targets.protein, targets.carbs, targets.fat = body.kcal, body.protein, body.carbs, body.fat
    targets.custom = True
    db.commit()
    return {
        "targets": services.targets_dict(targets),
        "warnings": validate_custom_targets(sex=profile.sex, kcal=body.kcal, tdee_kcal=targets.tdee),
    }


@router.post("/targets/recalculate")
def recalculate_targets(db: Session = Depends(get_db)) -> dict:
    profile = services.get_profile(db)
    if profile is None:
        raise HTTPException(409, "Completa primero tu perfil.")
    targets, plan = services.apply_plan(db, profile)
    db.commit()
    return {"targets": services.targets_dict(targets), "plan": plan}
