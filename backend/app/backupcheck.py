"""Comprobación semanal de las copias de seguridad: una copia que nunca se ha abierto no se sabe si sirve.

Cada lunes, después de la copia diaria, se abre la última copia local (descomprimida, con la comprobación de
integridad de SQLite y viendo que tiene cuentas) y, si hay destino externo, la última de fuera: se descarga, se
descifra con la frase y se abre igual. Si algo falla, el administrador recibe un aviso. El resultado se ve en /admin.
"""

import gzip
import logging
import sqlite3
import tempfile
from datetime import date

import httpx

from . import notify, offsite, services
from .config import Settings

log = logging.getLogger("kcalia.backupcheck")

STATUS_KEY = "backup_check"
CHECK_WEEKDAY = 0  # lunes
MAX_AGE_DAYS = 2  # si la última copia local es más vieja, las copias han dejado de hacerse


def check_database(raw: bytes) -> dict:
    """Abre una base SQLite (sin comprimir) y comprueba que está entera y tiene datos."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(raw)
        tmp.flush()
        try:
            con = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
            try:
                integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
                users = con.execute("SELECT count(*) FROM users").fetchone()[0]
                meals = con.execute("SELECT count(*) FROM meals").fetchone()[0]
            finally:
                con.close()
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"no se puede abrir como base de datos ({exc})") from exc
    if integrity != "ok":
        raise ValueError(f"la base no está entera: {integrity[:120]}")
    if users < 1:
        raise ValueError("la copia no tiene ninguna cuenta")
    return {"users": users, "meals": meals}


def check_local(settings: Settings, today: date) -> dict:
    backups = sorted(settings.backup_dir.glob("kcalia-*.db.gz"))
    if not backups:
        raise ValueError("no hay ninguna copia local")
    latest = backups[-1]
    day = date.fromisoformat(latest.name.removeprefix("kcalia-")[:10])
    if (today - day).days > MAX_AGE_DAYS:
        raise ValueError(f"la última copia local es del {day.isoformat()}: las copias diarias se han parado")
    try:
        raw = gzip.decompress(latest.read_bytes())
    except (OSError, EOFError) as exc:
        raise ValueError(f"la copia local {latest.name} no se puede descomprimir") from exc
    return {"file": latest.name, **check_database(raw)}


def check_remote(settings: Settings, http: httpx.Client | None) -> dict | None:
    if not offsite.configured(settings) or http is None:
        return None
    remote = offsite.Remote(settings, http)
    keys = [k for k in remote.list() if k.rsplit("/", 1)[-1].startswith("kcalia-")]
    if not keys:
        raise ValueError("no hay ninguna copia fuera del servidor")
    key = keys[-1]
    blob = remote.get(key)
    try:
        if blob.startswith(offsite.MAGIC):
            blob = offsite.decrypt(blob, settings.backup_encryption_key)
        raw = gzip.decompress(blob)
    except Exception as exc:  # frase cambiada o perdida, fichero dañado...
        raise ValueError(f"la copia externa {key} no se puede descifrar o descomprimir") from exc
    return {"key": key, **check_database(raw)}


def run(settings: Settings, today: date, http: httpx.Client | None) -> dict:
    """Comprueba las dos copias y avisa si alguna falla. Devuelve el resultado (no lo guarda)."""
    status: dict = {"date": today.isoformat(), "ok": True, "local": None, "remote": None, "error": None}
    problems = []
    try:
        status["local"] = check_local(settings, today)
    except Exception as exc:
        problems.append(f"Copia local: {exc}")
    try:
        status["remote"] = check_remote(settings, http)
    except Exception as exc:
        problems.append(f"Copia externa: {exc}")
    if problems:
        status["ok"], status["error"] = False, " · ".join(problems)
        notify.backup_problem(status["error"])
    else:
        log.info("Copias comprobadas: %s", {k: status[k] for k in ("local", "remote")})
    return status


def _load() -> dict | None:
    from .db import SessionLocal

    with SessionLocal() as db:
        return services.app_setting(db, STATUS_KEY, None)


def _save(status: dict) -> None:
    from .db import SessionLocal

    with SessionLocal() as db:
        services.set_app_setting(db, STATUS_KEY, status)
        db.commit()


def run_if_due(settings: Settings, today: date, http: httpx.Client | None) -> dict | None:
    """Los lunes, una vez al día. Devuelve el resultado si se ha hecho la comprobación."""
    if today.weekday() != CHECK_WEEKDAY:
        return None
    previous = _load()
    if previous and previous.get("date") == today.isoformat():
        return None
    status = run(settings, today, http)
    _save(status)
    return status
