"""Migración de una base real de la versión 0 (un solo usuario) al esquema actual, sin perder nada."""

import gzip
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app import migrations, models  # noqa: F401  (registra las tablas)
from app.db import Base

FIXTURES = Path(__file__).parent / "fixtures"
DATA_TABLES = migrations.V0_DATA_TABLES


def make_v0(path: Path, *, with_users: bool = True) -> None:
    conn = sqlite3.connect(path)
    conn.executescript((FIXTURES / "schema_v0.sql").read_text())
    now = "2026-09-30 10:00:00.000000"
    if with_users:
        # La más antigua por fecha tiene el id más alto: manda la fecha de alta.
        conn.execute("INSERT INTO users VALUES (1, 'nuevo', 'hash1', '2026-09-30 12:00:00.000000')")
        conn.execute("INSERT INTO users VALUES (2, 'alvaro', 'hash2', '2026-09-29 09:00:00.000000')")
        conn.execute("INSERT INTO sessions VALUES (1, 'tok', 2, ?, ?, '2027-01-01 00:00:00.000000')", (now, now))
    conn.execute(
        "INSERT INTO profile VALUES (1, 'hombre', 30, 180, 80, 'moderado', 'definicion_ligera', NULL, 'kg', ?)", (now,)
    )
    conn.execute("INSERT INTO targets VALUES (1, 2200, 160, 230, 70, 1780, 2760, 0, 80, ?)", (now,))
    items = '[{"name": "huevo", "qty": 2, "unit": "pieza", "grams": 110, "kcal": 157, "protein": 14, "carbs": 1, "fat": 10}]'
    conn.execute(
        "INSERT INTO dishes VALUES (1, 'Huevos', 'dos huevos', '2 huevo', ?, 157, 14, 1, 10, 0.9, '[]', 'ai', 1, 3, ?, ?)",
        (items, now, now),
    )
    conn.execute("INSERT INTO dish_aliases VALUES ('2 huevos fritos', 1)")
    for n, day in enumerate(("2026-09-28", "2026-09-29", "2026-09-30"), start=1):
        conn.execute(
            "INSERT INTO meals VALUES (?, ?, ?, 'desayuno', 'Huevos', 'dos huevos', ?, 1, 157, 14, 1, 10, 'ai', 0.9,"
            " '[]', 1, ?, ?, NULL)",
            (n, f"cid-{n}", day, items, now, now),
        )
    conn.execute("INSERT INTO foods VALUES (1, 'huevo', 'huevo', 143, 12.6, 0.7, 9.5, '{\"pieza\": 55}', 2, ?)", (now,))
    conn.execute("INSERT INTO weights VALUES (1, '2026-09-30', 80.4, ?)", (now,))
    conn.execute("INSERT INTO weekly_summaries VALUES (1, '2026-09-21', '{\"logged_days\": 3}', ?)", (now,))
    conn.execute("INSERT INTO achievements VALUES ('primera_comida', ?)", (now,))
    conn.execute("INSERT INTO counters VALUES ('saved_exact', 4)")
    conn.execute("INSERT INTO ai_usage VALUES (1, '2026-09-30', 'text', 3, 2700, 330)")
    conn.execute(
        "INSERT INTO products VALUES (1, 'Yogur ligero', 'yogur ligero', 'g', 44, 4.4, 5.9, 0.1, NULL, 5.9, 0.1,"
        " 'yogur', 125, 1, 2, ?, ?)",
        (now, now),
    )
    conn.execute("INSERT INTO product_images VALUES (1, 'image/jpeg', ?)", (b"\xff\xd8foto\x00binaria",))
    conn.commit()
    conn.close()


def schema(path: Path) -> dict:
    conn = sqlite3.connect(path)
    out = {}
    for table in sorted(migrations.table_names(conn)):
        columns = [(r[1], r[2], r[3], r[5]) for r in conn.execute(f'PRAGMA table_info("{table}")')]
        indexes = set()
        for idx in conn.execute(f'PRAGMA index_list("{table}")'):
            cols = tuple(r[2] for r in conn.execute(f'PRAGMA index_info("{idx[1]}")'))
            indexes.add((idx[1] if not idx[1].startswith("sqlite_autoindex") else "auto", idx[2], cols, idx[4]))
        fks = sorted((r[2], r[3], r[4], r[6]) for r in conn.execute(f'PRAGMA foreign_key_list("{table}")'))
        out[table] = (columns, indexes, fks)
    conn.close()
    return out


def migrate(path: Path, backups: Path) -> list[int]:
    applied = migrations.run(path, backups)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    return applied


def test_base_nueva_y_migrada_tienen_el_mismo_esquema(tmp_path):
    fresh = tmp_path / "nueva.db"
    engine = create_engine(f"sqlite:///{fresh}")
    Base.metadata.create_all(engine)
    engine.dispose()

    old = tmp_path / "v0.db"
    make_v0(old)
    assert migrate(old, tmp_path / "copias") == list(range(1, migrations.CURRENT_VERSION + 1))
    assert schema(old) == schema(fresh)


def test_migracion_conserva_todo_y_lo_asigna_al_usuario_mas_antiguo(tmp_path):
    path = tmp_path / "v0.db"
    make_v0(path)
    before = {t: sqlite3.connect(path).execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in DATA_TABLES}
    migrate(path, tmp_path / "copias")

    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrations.CURRENT_VERSION
    for table in DATA_TABLES:
        assert conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == before[table], table
        owners = {r[0] for r in conn.execute(f'SELECT DISTINCT user_id FROM "{table}"')}
        assert owners == {2}, table
    users = conn.execute("SELECT username, status, is_admin FROM users ORDER BY id").fetchall()
    assert users == [("nuevo", "approved", 0), ("alvaro", "approved", 1)]
    assert conn.execute("SELECT data FROM product_images").fetchone()[0] == b"\xff\xd8foto\x00binaria"
    assert conn.execute("SELECT user_id FROM sessions").fetchone()[0] == 2
    assert conn.execute("SELECT norm, dish_id FROM dish_aliases").fetchone() == ("2 huevos fritos", 1)
    assert conn.execute("SELECT key, value FROM counters").fetchone() == ("saved_exact", 4)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # Las restricciones únicas pasan a ser por usuario.
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO weights (user_id, date, kg, created_at) VALUES (2, '2026-09-30', 81, '2026-10-01')")
    conn.execute("INSERT INTO weights (user_id, date, kg, created_at) VALUES (1, '2026-09-30', 70, '2026-10-01')")
    # Solo puede haber un administrador.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE users SET is_admin = 1 WHERE id = 1")
    conn.close()


def test_copia_previa_y_reejecucion(tmp_path):
    path, backups = tmp_path / "v0.db", tmp_path / "copias"
    make_v0(path)
    migrate(path, backups)
    copies = list(backups.glob("premigracion-kcalia-v0-*.db.gz"))
    assert len(copies) == 1
    restored = tmp_path / "restaurada.db"
    restored.write_bytes(gzip.decompress(copies[0].read_bytes()))
    conn = sqlite3.connect(restored)
    assert conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0] == 3
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()
    # Ya migrada: no hace nada ni crea otra copia.
    assert migrate(path, backups) == []
    assert len(list(backups.glob("premigracion-*"))) == 1


def test_datos_sin_cuenta_no_se_pierden(tmp_path):
    path = tmp_path / "v0.db"
    make_v0(path, with_users=False)
    migrate(path, tmp_path / "copias")
    conn = sqlite3.connect(path)
    owner = conn.execute("SELECT id, username, is_admin FROM users").fetchone()
    assert owner[1:] == ("admin-recuperado", 1)
    assert conn.execute("SELECT COUNT(*) FROM meals WHERE user_id = ?", (owner[0],)).fetchone()[0] == 3
    conn.close()


def test_base_nueva_no_se_migra(tmp_path):
    assert migrations.run(tmp_path / "no-existe.db", tmp_path / "copias") == []
    assert not (tmp_path / "copias").exists()
