"""Fechas como las escribe la app (es-ES, como fmtMedium en frontend/src/lib/dates.ts): «mar, 6 oct»."""

from datetime import date

DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def medium(day: date, capital: bool = False) -> str:
    text = f"{DAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"
    return text[:1].upper() + text[1:] if capital else text
