from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{settings.db_path}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Migra la base si viene de una versión anterior y crea las tablas que falten."""
    from . import migrations, models  # noqa: F401

    settings = get_settings()
    fresh = migrations.is_fresh(settings.db_path)
    if not fresh:
        migrations.run(settings.db_path, settings.backup_dir)
    Base.metadata.create_all(engine)
    if fresh:
        migrations.set_version(settings.db_path)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
