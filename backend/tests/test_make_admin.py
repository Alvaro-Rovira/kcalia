"""El rol de administrador solo se asigna con scripts/make-admin.py (y la migración)."""

import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.db import Base

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "make-admin.py"


def make_db(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    for n, (name, admin) in enumerate((("alvaro", 1), ("lucia", 0)), start=1):
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, status, is_admin) VALUES (?, ?, 'h', ?, ?, ?)",
            (n, name, "2026-10-01 10:00:00", "approved" if admin else "pending", admin),
        )
    conn.commit()
    conn.close()


def run(*args: str, stdin: bool = False) -> subprocess.CompletedProcess:
    if stdin:
        # Como en el servidor: el script entra por la entrada estándar.
        return subprocess.run(
            [sys.executable, "-", *args], input=SCRIPT.read_text(), capture_output=True, text=True, check=False
        )
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


def test_pasa_el_rol_y_deja_un_solo_admin(tmp_path):
    db = tmp_path / "kcalia.db"
    make_db(db)
    result = run("LUCIA", "--db", str(db), stdin=True)
    assert result.returncode == 0, result.stderr
    assert "lucia es ahora el administrador (antes: alvaro)" in result.stdout
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT username, is_admin, status FROM users ORDER BY id").fetchall() == [
        ("alvaro", 0, "approved"),
        ("lucia", 1, "approved"),
    ]
    audit = conn.execute("SELECT action, target_username, admin_username FROM admin_audit").fetchone()
    assert audit == ("make_admin", "lucia", "scripts/make-admin.py")


def test_usuario_inexistente(tmp_path):
    db = tmp_path / "kcalia.db"
    make_db(db)
    result = run("nadie", "--db", str(db))
    assert result.returncode == 1 and "No existe" in result.stderr
    assert sqlite3.connect(db).execute("SELECT username FROM users WHERE is_admin = 1").fetchone() == ("alvaro",)
