"""Migraciones del esquema de SQLite, versionadas con `PRAGMA user_version`.

`create_all` solo crea tablas nuevas: no añade columnas ni cambia restricciones de las que ya existen. Cada
versión de MIGRATIONS lleva una base de la versión anterior a la siguiente, dentro de una transacción y con las
claves foráneas desactivadas, como indica la documentación de SQLite para reconstruir tablas:

    crear _new_x con el esquema nuevo -> copiar las filas -> borrar x -> renombrar _new_x a x -> índices

Antes de tocar nada se guarda una copia comprimida de la base. Una base nueva no se migra: se crea con
`create_all` y se marca directamente con la versión actual.
"""

import gzip
import json
import logging
import re
import shutil
import sqlite3
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Column, Table
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from .db import Base

log = logging.getLogger("kcalia.migrations")
DIALECT = sqlite_dialect.dialect()

# Tablas de datos de la versión 0: todas pasan a pertenecer a un usuario en la versión 1.
V0_DATA_TABLES = (
    "profile",
    "targets",
    "dishes",
    "dish_aliases",
    "meals",
    "foods",
    "weights",
    "weekly_summaries",
    "achievements",
    "counters",
    "ai_usage",
    "products",
    "product_images",
)


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
    return {row[0] for row in rows}


def column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def _default_value(column: Column):
    """Valor con el que rellenar una columna nueva en las filas que ya existían."""
    default = column.default
    if default is None:
        if column.nullable:
            return None
        raise RuntimeError(
            f"La columna {column.table.name}.{column.name} es nueva, obligatoria y sin valor por defecto"
        )
    value = default.arg(None) if default.is_callable else default.arg
    if isinstance(value, dict | list):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _is_rowid(column: Column) -> bool:
    return bool(column.primary_key and column.autoincrement and len(column.table.primary_key.columns) == 1)


def rebuild_table(conn: sqlite3.Connection, table: Table, fill: dict | None = None) -> None:
    """Rehace `table` en la base con el esquema actual del modelo, conservando sus filas.

    Las columnas que ya existían se copian tal cual. Las nuevas toman el valor de `fill`, o el valor por defecto
    del modelo; una clave primaria entera nueva la numera SQLite.
    """
    fill = fill or {}
    name = table.name
    old_columns = set(column_names(conn, name))
    temp_name = f"_new_{name}"
    # El DDL del modelo, con otro nombre: así la tabla temporal nunca entra en Base.metadata.
    ddl = str(CreateTable(table).compile(dialect=DIALECT))
    ddl, renamed = re.subn(rf'CREATE TABLE "?{re.escape(name)}"? \(', f'CREATE TABLE "{temp_name}" (', ddl, count=1)
    if not renamed:
        raise RuntimeError(f"No sé reconstruir la tabla {name}")

    targets: list[str] = []
    selects: list[str] = []
    params: list = []
    for column in table.columns:
        if column.name in old_columns:
            targets.append(f'"{column.name}"')
            selects.append(f'"{column.name}"')
        elif column.name in fill:
            targets.append(f'"{column.name}"')
            selects.append("?")
            params.append(fill[column.name])
        elif _is_rowid(column):
            continue
        else:
            targets.append(f'"{column.name}"')
            selects.append("?")
            params.append(_default_value(column))

    conn.execute(f'DROP TABLE IF EXISTS "{temp_name}"')
    conn.execute(ddl)
    conn.execute(
        f'INSERT INTO "{temp_name}" ({", ".join(targets)}) SELECT {", ".join(selects)} FROM "{name}"',
        params,
    )
    conn.execute(f'DROP TABLE "{name}"')
    conn.execute(f'ALTER TABLE "{temp_name}" RENAME TO "{name}"')
    for index in table.indexes:
        conn.execute(str(CreateIndex(index).compile(dialect=DIALECT)))


def backup_before(db_path: Path, backup_dir: Path, version: int) -> Path:
    """Copia consistente y comprimida antes de migrar. No entra en la rotación de las copias diarias."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"premigracion-kcalia-v{version}-{stamp}.db.gz"
    temp = backup_dir / ".premigracion.tmp"
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(temp)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    with open(temp, "rb") as raw, gzip.open(target, "wb") as packed:
        shutil.copyfileobj(raw, packed)
    temp.unlink(missing_ok=True)
    return target


# ---------------------------------------------------------------- versiones


def _v1_multiuser(conn: sqlite3.Connection) -> None:
    """Cada dato pasa a tener dueño. El usuario más antiguo se queda con todo y es el administrador."""
    tables = table_names(conn)
    rebuild_table(conn, Base.metadata.tables["users"], {"status": "approved", "is_admin": False})
    row = conn.execute("SELECT id FROM users ORDER BY created_at, id LIMIT 1").fetchone()
    owner = row[0] if row else None

    has_data = any(
        conn.execute(f'SELECT 1 FROM "{name}" LIMIT 1').fetchone() for name in V0_DATA_TABLES if name in tables
    )
    if owner is None and has_data:
        # No debería pasar (borrar la cuenta borra los datos), pero si pasa no se pierde nada: los datos van a una
        # cuenta administradora sin contraseña válida, que se puede reasignar con scripts/make-admin.py.
        log.warning("Datos sin ninguna cuenta: se asignan a la cuenta 'admin-recuperado'")
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at, status, is_admin) VALUES (?, '!', ?, ?, 0)",
            ("admin-recuperado", datetime.now().isoformat(sep=" "), "approved"),
        )
        owner = conn.execute("SELECT id FROM users WHERE username = 'admin-recuperado'").fetchone()[0]
    if owner is not None:
        conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (owner,))

    for name in V0_DATA_TABLES:
        if name in tables:
            rebuild_table(conn, Base.metadata.tables[name], {"user_id": owner})


def _v2_barcodes(conn: sqlite3.Connection) -> None:
    """Productos con código de barras (columna nueva y única por usuario)."""
    rebuild_table(conn, Base.metadata.tables["products"])


def _v3_fiber_alcohol(conn: sqlite3.Connection) -> None:
    """Fibra y alcohol en las comidas y en la caché de ingredientes (columnas nuevas, vacías en lo antiguo)."""
    rebuild_table(conn, Base.metadata.tables["meals"])
    rebuild_table(conn, Base.metadata.tables["foods"])


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_v1_multiuser, _v2_barcodes, _v3_fiber_alcohol]
CURRENT_VERSION = len(MIGRATIONS)


def current_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def set_version(db_path: Path, version: int = CURRENT_VERSION) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"PRAGMA user_version = {int(version)}")
        conn.commit()
    finally:
        conn.close()


def is_fresh(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    conn = sqlite3.connect(db_path)
    try:
        return "users" not in table_names(conn)
    finally:
        conn.close()


def run(db_path: Path, backup_dir: Path) -> list[int]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas."""
    from . import models  # noqa: F401  (registra las tablas en Base.metadata)

    if is_fresh(db_path):
        return []
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= CURRENT_VERSION:
            return []
        backup = backup_before(db_path, backup_dir, version)
        log.info("Copia previa a la migración: %s", backup.name)
        conn.execute("PRAGMA foreign_keys = OFF")
        applied = []
        for number in range(version + 1, CURRENT_VERSION + 1):
            conn.execute("BEGIN IMMEDIATE")
            try:
                MIGRATIONS[number - 1](conn)
                broken = conn.execute("PRAGMA foreign_key_check").fetchall()
                if broken:
                    raise RuntimeError(f"Claves foráneas rotas tras la migración {number}: {broken[:5]}")
                conn.execute(f"PRAGMA user_version = {number}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                log.exception("La migración %s ha fallado; la base queda como estaba", number)
                raise
            applied.append(number)
            log.info("Migración %s aplicada", number)
        return applied
    finally:
        conn.close()
