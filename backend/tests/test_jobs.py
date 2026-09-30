import gzip
import sqlite3
from datetime import datetime, timedelta

from app.config import Settings
from app.jobs import backup_database


def make_settings(tmp_path, keep=7) -> Settings:
    data = tmp_path / "data"
    data.mkdir()
    db = sqlite3.connect(data / "kcalia.db")
    db.execute("CREATE TABLE meals (id INTEGER PRIMARY KEY, name TEXT)")
    db.executemany("INSERT INTO meals (name) VALUES (?)", [("tostada",), ("café con leche",)])
    db.commit()
    db.close()
    return Settings(_env_file=None, data_dir=data, backup_dir=tmp_path / "backups", backup_keep=keep)


def test_la_copia_es_una_base_de_datos_valida(tmp_path):
    settings = make_settings(tmp_path)
    target = backup_database(settings, datetime(2026, 9, 30, 3, 30))
    assert target.name == "kcalia-2026-09-30.db.gz"
    # Restaurar es descomprimir: lo que sale debe abrirse y tener los datos.
    restored = tmp_path / "restaurada.db"
    restored.write_bytes(gzip.decompress(target.read_bytes()))
    rows = sqlite3.connect(restored).execute("SELECT name FROM meals ORDER BY id").fetchall()
    assert rows == [("tostada",), ("café con leche",)]
    assert not (settings.backup_dir / ".kcalia-backup.tmp").exists()


def test_rotacion_conserva_las_siete_ultimas(tmp_path):
    settings = make_settings(tmp_path)
    first = datetime(2026, 9, 1, 3, 0)
    for day in range(10):
        backup_database(settings, first + timedelta(days=day))
    names = sorted(p.name for p in settings.backup_dir.glob("kcalia-*.db.gz"))
    assert len(names) == 7
    assert names[0] == "kcalia-2026-09-04.db.gz" and names[-1] == "kcalia-2026-09-10.db.gz"


def test_repetir_el_mismo_dia_no_acumula(tmp_path):
    settings = make_settings(tmp_path)
    now = datetime(2026, 9, 30, 3, 0)
    backup_database(settings, now)
    backup_database(settings, now)
    assert len(list(settings.backup_dir.glob("kcalia-*.db.gz"))) == 1


def test_sin_base_de_datos_no_hace_nada(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path / "vacio", backup_dir=tmp_path / "backups")
    assert backup_database(settings) is None
    assert not (tmp_path / "backups").exists()
