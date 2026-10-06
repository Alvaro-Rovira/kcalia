"""Aislamiento por usuario, seguro por defecto.

Cada sesión de base de datos lleva su usuario en `session.info["user_id"]`. Con él:
- toda consulta ORM (SELECT, y UPDATE o DELETE masivos) sobre una tabla de datos se filtra sola por ese usuario;
- todo dato nuevo de esas tablas se guarda a su nombre.

Una consulta que toque datos sin usuario y sin permiso explícito (`unscoped`) lanza TenancyError: olvidarse de
filtrar rompe en las pruebas en lugar de enseñar datos de otra persona.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from .models import TenantMixin

USER_KEY = "user_id"
ALL_KEY = "all_users"


class TenancyError(RuntimeError):
    pass


def scope(db: Session, user_id: int) -> Session:
    """A partir de aquí, esta sesión solo ve y escribe datos de `user_id`."""
    db.info[USER_KEY] = user_id
    db.info.pop(ALL_KEY, None)
    return db


def current_user_id(db: Session) -> int | None:
    return db.info.get(USER_KEY)


@contextmanager
def unscoped(db: Session) -> Iterator[Session]:
    """Acceso a los datos de todos los usuarios: solo para administración y tareas internas."""
    previous = db.info.get(ALL_KEY)
    db.info[ALL_KEY] = True
    try:
        yield db
    finally:
        if previous is None:
            db.info.pop(ALL_KEY, None)
        else:
            db.info[ALL_KEY] = previous


@contextmanager
def as_user(db: Session, user_id: int) -> Iterator[Session]:
    """Limita temporalmente la sesión a `user_id` (tareas internas y acciones del admin sobre una cuenta)."""
    saved = {key: db.info.get(key) for key in (USER_KEY, ALL_KEY)}
    scope(db, user_id)
    try:
        yield db
    finally:
        for key, value in saved.items():
            if value is None:
                db.info.pop(key, None)
            else:
                db.info[key] = value


def _touches_tenant_data(state: ORMExecuteState) -> bool:
    return any(issubclass(mapper.class_, TenantMixin) for mapper in state.all_mappers)


@event.listens_for(Session, "do_orm_execute")
def _filter_by_user(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    info = state.session.info
    if info.get(ALL_KEY):
        return
    user_id = info.get(USER_KEY)
    if user_id is None:
        if _touches_tenant_data(state):
            raise TenancyError("Consulta de datos de usuario sin usuario: usa tenancy.scope o tenancy.unscoped")
        return
    state.statement = state.statement.options(
        with_loader_criteria(TenantMixin, lambda cls: cls.user_id == user_id, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def _assign_owner(session: Session, _context, _instances) -> None:
    user_id = session.info.get(USER_KEY)
    for obj in session.new:
        if not isinstance(obj, TenantMixin):
            continue
        if obj.user_id is None:
            if user_id is None:
                raise TenancyError(f"{type(obj).__name__} nuevo sin usuario")
            obj.user_id = user_id
        elif user_id is not None and obj.user_id != user_id and not session.info.get(ALL_KEY):
            raise TenancyError(f"{type(obj).__name__} a nombre de otro usuario")
