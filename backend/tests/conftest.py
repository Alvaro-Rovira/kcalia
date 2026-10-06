import os
import tempfile

# La configuración se lee al importar la app, así que el entorno va antes.
_TMP = tempfile.mkdtemp(prefix="kcalia-test-")
os.environ.update(
    DATA_DIR=_TMP,
    BACKUP_DIR=os.path.join(_TMP, "backups"),
    STATIC_DIR=os.path.join(_TMP, "static"),
    COOKIE_SECURE="false",
    AI_API_KEY="test-key",
    AI_DAILY_LIMIT="5",
)

PASSWORD = "contraseña-larga"


def reset_database() -> None:
    """Vacía todas las tablas: cada módulo de pruebas de la API empieza como una instalación nueva."""
    from app import security
    from app.db import Base, engine, init_db

    init_db()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    security.login_throttle._failures.clear()
    security.register_limit._events.clear()


def create_user(username: str, *, status: str = "approved", is_admin: bool = False, password: str = PASSWORD) -> int:
    """Crea una cuenta directamente en la base (sin pasar por la solicitud y la aprobación)."""
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password

    with SessionLocal() as db:
        user = User(username=username, password_hash=hash_password(password), status=status, is_admin=is_admin)
        db.add(user)
        db.commit()
        return user.id


def login(client, username: str, password: str = PASSWORD):
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response
