"""Fechas como las escribe la app (es-ES, como fmtMedium en frontend/src/lib/dates.ts): «mar, 6 oct»."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

# La app y el navegador de las pruebas van en hora de Madrid (TZ y timezone_id en conftest y test_flow).
APP_ZONE = ZoneInfo("Europe/Madrid")


def app_today() -> date:
    """El «hoy» de la app. No vale date.today(): en CI (UTC) es otro día entre las 22:00 y las 24:00."""
    return datetime.now(APP_ZONE).date()

DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]


def medium(day: date, capital: bool = False) -> str:
    text = f"{DAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"
    return text[:1].upper() + text[1:] if capital else text
