"""Entrenamientos: calorías estimadas por día (se completa con el registro de entrenos)."""

from sqlalchemy.orm import Session


def estimated_kcal_by_day(db: Session, start: str, end: str) -> dict[str, float]:
    return {}
