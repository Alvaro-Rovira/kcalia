from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..deps import require_user
from ..models import Weight
from ..schemas import WeightIn
from ..summary import moving_average

router = APIRouter(prefix="/api/weight", tags=["peso"], dependencies=[Depends(require_user)])

RECALC_THRESHOLD_KG = 1.0


def _payload(db: Session) -> dict:
    entries = [(w.date, w.kg) for w in db.scalars(select(Weight).order_by(Weight.date))]
    series = moving_average(entries)
    profile, targets = services.get_profile(db), services.get_targets(db)
    recalc = None
    if entries and profile and targets:
        latest = entries[-1][1]
        if abs(latest - targets.basis_weight_kg) >= RECALC_THRESHOLD_KG:
            # Objetivos que saldrían con el peso actual, para que el usuario decida.
            preview = services.plan_for(profile)
            recalc = {
                "from_kg": targets.basis_weight_kg,
                "to_kg": latest,
                "kcal": preview["kcal"],
                "protein": preview["protein"],
                "carbs": preview["carbs"],
                "fat": preview["fat"],
            }
    return {
        "entries": series,
        "target_kg": profile.target_weight_kg if profile else None,
        "recalc": recalc,
    }


def _sync_profile_weight(db: Session) -> None:
    latest = db.scalar(select(Weight).order_by(Weight.date.desc()).limit(1))
    profile = services.get_profile(db)
    if latest and profile:
        profile.weight_kg = latest.kg


@router.get("")
def list_weights(db: Session = Depends(get_db)) -> dict:
    return _payload(db)


@router.put("")
def save_weight(body: WeightIn, db: Session = Depends(get_db)) -> dict:
    entry = db.scalar(select(Weight).where(Weight.date == body.date))
    if entry is None:
        db.add(Weight(date=body.date, kg=body.kg))
    else:
        entry.kg = body.kg
    db.flush()
    _sync_profile_weight(db)
    db.commit()
    return _payload(db)


@router.delete("/{date}")
def delete_weight(date: str, db: Session = Depends(get_db)) -> dict:
    entry = db.scalar(select(Weight).where(Weight.date == date))
    if entry is not None:
        db.delete(entry)
        db.flush()
        _sync_profile_weight(db)
        db.commit()
    return _payload(db)
