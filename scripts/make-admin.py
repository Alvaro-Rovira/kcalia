#!/usr/bin/env python3
"""Pasa el rol de administrador a otra cuenta. Solo puede haber uno: la cuenta anterior deja de serlo.

Ni la interfaz ni la API pueden asignar este rol; solo la migración inicial y este script de servidor.
El contenedor es de solo lectura, así que el script entra por la entrada estándar:

    cd /opt/kcalia && docker compose exec -T app python - USUARIO < scripts/make-admin.py

En local, indicando la base de datos:

    python scripts/make-admin.py USUARIO --db backend/data/kcalia.db

Usa solo la biblioteca estándar. Queda registrado en la auditoría de administración.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Asigna el rol de administrador de Kcalia a una cuenta.")
    parser.add_argument("username", help="usuario que pasará a ser el administrador")
    parser.add_argument("--db", default=os.path.join(os.environ.get("DATA_DIR", "/data"), "kcalia.db"))
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"No encuentro la base de datos en {args.db}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(args.db, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute(
            "SELECT id, username FROM users WHERE lower(username) = lower(?)", (args.username,)
        ).fetchone()
        if user is None:
            conn.execute("ROLLBACK")
            print(f"No existe ninguna cuenta llamada «{args.username}».", file=sys.stderr)
            return 1
        previous = conn.execute("SELECT id, username FROM users WHERE is_admin = 1").fetchone()
        conn.execute("UPDATE users SET is_admin = 0 WHERE is_admin = 1")
        conn.execute("UPDATE users SET is_admin = 1, status = 'approved' WHERE id = ?", (user[0],))
        has_audit = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'admin_audit'").fetchone()
        if has_audit:
            conn.execute(
                "INSERT INTO admin_audit (admin_id, admin_username, action, target_user_id, target_username, details,"
                " created_at) VALUES (NULL, 'scripts/make-admin.py', 'make_admin', ?, ?, ?, ?)",
                (
                    user[0],
                    user[1],
                    json.dumps({"previous_admin": previous[1] if previous else None}),
                    datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" "),
                ),
            )
        conn.execute("COMMIT")
    finally:
        conn.close()
    before = f" (antes: {previous[1]})" if previous and previous[0] != user[0] else ""
    print(f"{user[1]} es ahora el administrador{before}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
