"""Tareas periódicas dentro del propio proceso: copia de seguridad diaria y resumen del domingo."""

import gzip
import logging
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import services
from .config import Settings, get_settings
from .db import SessionLocal
from .summary import week_start

log = logging.getLogger("kcalia.jobs")

BACKUP_HOUR = 3
SUMMARY_WEEKDAY = 6  # domingo
SUMMARY_HOUR = 21
CHECK_EVERY_SECONDS = 600


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


def _tick(settings: Settings) -> None:
    now = datetime.now(settings.zone)
    today = now.date()

    todays_backup = settings.backup_dir / f"kcalia-{today:%Y-%m-%d}.db.gz"
    if now.hour >= BACKUP_HOUR and not todays_backup.exists():
        path = backup_database(settings, now)
        if path:
            log.info("Copia de seguridad creada: %s", path.name)

    with SessionLocal() as db:
        closing_week = now.weekday() == SUMMARY_WEEKDAY and now.hour >= SUMMARY_HOUR
        created = services.ensure_summaries(db, today, include_current=closing_week)
        if closing_week:
            # Si se añade algo el domingo por la noche, el resumen ya guardado se rehace.
            services.store_week(db, week_start(today), today)
        if created:
            log.info("Resúmenes semanales generados: %s", created)


def start_scheduler(stop: threading.Event) -> threading.Thread:
    settings = get_settings()

    def loop() -> None:
        while not stop.is_set():
            try:
                _tick(settings)
            except Exception:
                log.exception("Fallo en las tareas periódicas")
            stop.wait(CHECK_EVERY_SECONDS)

    thread = threading.Thread(target=loop, name="kcalia-jobs", daemon=True)
    thread.start()
    return thread
