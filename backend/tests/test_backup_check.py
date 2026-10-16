"""Comprobación semanal de las copias: se abren de verdad (la local y la externa descifrada) y se avisa si fallan."""

import gzip
import sqlite3
from datetime import date

import httpx
import pytest
from test_offsite import FakeS3, settings_for

from app import backupcheck, notify, offsite

TODAY = date(2026, 10, 19)  # lunes


def local_only(tmp_path):
    return settings_for(tmp_path).model_copy(update={"backup_remote_url": ""})


def make_backup(settings, day: str, *, users: int = 1, raw: bytes | None = None):
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    path = settings.backup_dir / f"kcalia-{day}.db.gz"
    if raw is None:
        db_file = settings.backup_dir / "tmp.db"
        db_file.unlink(missing_ok=True)
        con = sqlite3.connect(db_file)
        con.execute("create table users (id integer primary key)")
        con.execute("create table meals (id integer primary key)")
        con.executemany("insert into users values (?)", [(n,) for n in range(1, users + 1)])
        con.executemany("insert into meals values (?)", [(n,) for n in range(1, 13)])
        con.commit()
        con.close()
        raw = db_file.read_bytes()
        db_file.unlink()
    path.write_bytes(gzip.compress(raw))
    return path


@pytest.fixture()
def alerts(monkeypatch):
    sent: list[str] = []
    monkeypatch.setattr(notify, "backup_problem", sent.append)
    return sent


def test_copia_local_buena(tmp_path, alerts):
    settings = local_only(tmp_path)
    make_backup(settings, "2026-10-19")
    status = backupcheck.run(settings, TODAY, http=None)
    assert status["ok"] is True and status["local"]["meals"] == 12 and status["remote"] is None
    assert alerts == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"raw": b"esto no es una base de datos" * 100}, "no se puede abrir"),
        ({"users": 0}, "ninguna cuenta"),
    ],
)
def test_copia_local_rota_o_vacia_avisa(tmp_path, alerts, kwargs, message):
    settings = local_only(tmp_path)
    make_backup(settings, "2026-10-19", **kwargs)
    status = backupcheck.run(settings, TODAY, http=None)
    assert status["ok"] is False and message in status["error"]
    assert len(alerts) == 1 and message in alerts[0]


def test_si_las_copias_dejaron_de_hacerse_avisa(tmp_path, alerts):
    settings = local_only(tmp_path)
    make_backup(settings, "2026-10-10")
    status = backupcheck.run(settings, TODAY, http=None)
    assert status["ok"] is False and "2026-10-10" in status["error"] and alerts


def test_la_copia_externa_se_descarga_descifra_y_abre(tmp_path, alerts):
    settings = settings_for(tmp_path, backup_encryption_key="una frase muy larga de prueba")
    s3 = FakeS3()
    http = httpx.Client(transport=httpx.MockTransport(s3.handler))
    local = make_backup(settings, "2026-10-19")
    assert offsite.upload(local, settings, http).ok
    status = backupcheck.run(settings, TODAY, http=http)
    assert status["ok"] is True and status["remote"]["key"].endswith(".db.gz.enc") and status["remote"]["meals"] == 12


def test_sin_la_frase_correcta_la_externa_no_sirve_y_avisa(tmp_path, alerts):
    settings = settings_for(tmp_path, backup_encryption_key="la frase de entonces")
    s3 = FakeS3()
    http = httpx.Client(transport=httpx.MockTransport(s3.handler))
    assert offsite.upload(make_backup(settings, "2026-10-19"), settings, http).ok
    changed = settings.model_copy(update={"backup_encryption_key": "otra frase distinta"})
    status = backupcheck.run(changed, TODAY, http=http)
    assert status["ok"] is False and "externa" in status["error"] and alerts


def test_solo_los_lunes_y_una_vez(tmp_path, alerts, monkeypatch):
    settings = local_only(tmp_path)
    make_backup(settings, "2026-10-19")
    saved: dict = {}
    monkeypatch.setattr(backupcheck, "_load", lambda: saved.get("status"))
    monkeypatch.setattr(backupcheck, "_save", lambda status: saved.update(status=status))
    assert backupcheck.run_if_due(settings, date(2026, 10, 18), http=None) is None  # domingo
    assert backupcheck.run_if_due(settings, TODAY, http=None)["ok"] is True
    assert backupcheck.run_if_due(settings, TODAY, http=None) is None  # ya hecha hoy
