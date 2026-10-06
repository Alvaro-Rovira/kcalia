"""Tareas periódicas dentro del propio proceso: copia de seguridad diaria y resumen del domingo."""

import gzip
import logging
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select

from . import offsite, reminders, services, tenancy
from .config import Settings, get_settings
from .db import SessionLocal
from .models import User
from .summary import week_start

log = logging.getLogger("kcalia.jobs")

BACKUP_HOUR = 3
SUMMARY_WEEKDAY = 6  # domingo
SUMMARY_HOUR = 21
CHECK_EVERY_SECONDS = 600
BACKUP_STATUS_KEY = "backup_remote"
# Los recordatorios se revisan cada minuto; copias y resúmenes, cada diez.
REMINDERS_EVERY_SECONDS = 60


def backup_database(settings: Settings, now: datetime | None = None) -> Path | None:
    """Copia consistente (API de backup de SQLite) comprimida, con rotación."""
    if not settings.db_path.exists():
        return None
    now = now or datetime.now(settings.zone)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.backup_dir / f"kcalia-{now:%Y-%m-%d}.db.gz"
    temp = settings.backup_dir / ".kcalia-backup.tmp"

    source = sqlite3.connect(settings.db_path)
    dest = sqlite3.connect(temp)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    with open(temp, "rb") as raw, gzip.open(target, "wb") as packed:
        shutil.copyfileobj(raw, packed)
    temp.unlink(missing_ok=True)

    backups = sorted(settings.backup_dir.glob("kcalia-*.db.gz"))
    for old in backups[: -settings.backup_keep]:
        old.unlink(missing_ok=True)
    return target


MAX_UPLOAD_ATTEMPTS = 6
_http: httpx.Client | None = None


def offsite_http() -> httpx.Client:
    """Cliente para la copia externa. Las pruebas lo sustituyen (nunca se sube a un servicio real)."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=120)
    return _http


def set_offsite_http(client: httpx.Client | None) -> None:
    global _http
    _http = client


def upload_offsite(settings: Settings, path: Path, day: str) -> dict | None:
    """Sube la copia del día si hay destino y aún no se ha subido bien (como mucho 6 intentos al día)."""
    if not offsite.configured(settings):
        return None
    with SessionLocal() as db:
        status = services.app_setting(db, BACKUP_STATUS_KEY, {}) or {}
        if status.get("date") == day and (status.get("ok") or status.get("attempts", 0) >= MAX_UPLOAD_ATTEMPTS):
            return status
        result = offsite.upload(path, settings, offsite_http())
        attempts = (status.get("attempts", 0) if status.get("date") == day else 0) + 1
        status = {
            "date": day,
            "ok": result.ok,
            "at": datetime.now(settings.zone).isoformat(timespec="seconds"),
            "key": result.key,
            "size": result.size,
            "sha256": result.sha256,
            "error": result.error,
            "attempts": attempts,
            # La última subida buena, para enseñarla aunque la de hoy falle.
            "last_ok_at": datetime.now(settings.zone).isoformat(timespec="seconds")
            if result.ok
            else status.get("last_ok_at"),
        }
        services.set_app_setting(db, BACKUP_STATUS_KEY, status)
        db.commit()
    return status


def _tick(settings: Settings) -> None:
    now = datetime.now(settings.zone)
    today = now.date()

    todays_backup = settings.backup_dir / f"kcalia-{today:%Y-%m-%d}.db.gz"
    if now.hour >= BACKUP_HOUR and not todays_backup.exists():
        path = backup_database(settings, now)
        if path:
            log.info("Copia de seguridad creada: %s", path.name)
    if todays_backup.exists():
        upload_offsite(settings, todays_backup, today.isoformat())

    closing_week = now.weekday() == SUMMARY_WEEKDAY and now.hour >= SUMMARY_HOUR
    with SessionLocal() as db:
        user_ids = list(db.scalars(select(User.id).where(User.status == "approved")))
    for user_id in user_ids:
        # Una sesión por usuario: cada resumen solo ve los datos de su dueño.
        with SessionLocal() as db, tenancy.as_user(db, user_id):
            created = services.ensure_summaries(db, today, include_current=closing_week)
            if closing_week:
                # Si se añade algo el domingo por la noche, el resumen ya guardado se rehace.
                services.store_week(db, week_start(today), today)
            if created:
                log.info("Resúmenes semanales generados para la cuenta %s: %s", user_id, created)


def start_scheduler(stop: threading.Event) -> threading.Thread:
    settings = get_settings()

    def loop() -> None:
        last_heavy = 0.0
        while not stop.is_set():
            if time.monotonic() - last_heavy >= CHECK_EVERY_SECONDS:
                last_heavy = time.monotonic()
                try:
                    _tick(settings)
                except Exception:
                    log.exception("Fallo en las tareas periódicas")
            try:
                reminders.run()
            except Exception:
                log.exception("Fallo al revisar los recordatorios")
            stop.wait(REMINDERS_EVERY_SECONDS)

    thread = threading.Thread(target=loop, name="kcalia-jobs", daemon=True)
    thread.start()
    return thread
