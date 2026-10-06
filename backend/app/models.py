from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TenantMixin:
    """Datos que pertenecen a un usuario. La sesión los filtra sola por `user_id` (ver tenancy.py)."""

    @declared_attr
    def user_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


ACCOUNT_STATUSES = ("pending", "approved", "suspended")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # pending (recién solicitada), approved o suspended. Solo una cuenta aprobada puede usar la app.
    status: Mapped[str] = mapped_column(String(12), default="pending")
    # Como mucho uno (índice único parcial). Solo lo asignan la migración y scripts/make-admin.py.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Límites diarios propios; None = el valor por defecto de la configuración.
    ai_daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stt_daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ux_users_single_admin", "is_admin", unique=True, sqlite_where=text("is_admin = 1")),
        Index("ix_users_status", "status"),
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Profile(TenantMixin, Base):
    __tablename__ = "profile"
    __table_args__ = (Index("ux_profile_user", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sex: Mapped[str] = mapped_column(String(8))
    age: Mapped[int] = mapped_column(Integer)
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    activity: Mapped[str] = mapped_column(String(16))
    goal: Mapped[str] = mapped_column(String(24))
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_unit: Mapped[str] = mapped_column(String(4), default="kg")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Targets(TenantMixin, Base):
    __tablename__ = "targets"
    __table_args__ = (Index("ux_targets_user", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kcal: Mapped[int] = mapped_column(Integer)
    protein: Mapped[int] = mapped_column(Integer)
    carbs: Mapped[int] = mapped_column(Integer)
    fat: Mapped[int] = mapped_column(Integer)
    bmr: Mapped[int] = mapped_column(Integer)
    tdee: Mapped[int] = mapped_column(Integer)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)
    # Peso con el que se calcularon, para sugerir recalcular cuando cambie.
    basis_weight_kg: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Dish(TenantMixin, Base):
    """Comida conocida: la biblioteca contra la que se busca antes de llamar a la IA."""

    __tablename__ = "dishes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    norm: Mapped[str] = mapped_column(String(400))
    items: Mapped[list] = mapped_column(JSON)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(12), default="ai")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ux_dishes_user_norm", "user_id", "norm", unique=True),)


class DishAlias(TenantMixin, Base):
    """Otra forma de escribir una comida conocida, aprendida al confirmar un "¿es esta?"."""

    __tablename__ = "dish_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    norm: Mapped[str] = mapped_column(String(400))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id", ondelete="CASCADE"), index=True)

    __table_args__ = (Index("ux_dish_aliases_user_norm", "user_id", "norm", unique=True),)


class Meal(TenantMixin, Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Generado en el cliente: hace idempotente la cola offline.
    client_id: Mapped[str] = mapped_column(String(40))
    date: Mapped[str] = mapped_column(String(10))
    slot: Mapped[str] = mapped_column(String(12))
    name: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON)
    servings: Mapped[float] = mapped_column(Float, default=1.0)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    # Fibra y gramos de alcohol (7 kcal/g, ya incluidos en kcal). None en comidas anteriores a estos datos.
    fiber: Mapped[float | None] = mapped_column(Float, nullable=True)
    alcohol: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(12), default="ai")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("dishes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ux_meals_user_client", "user_id", "client_id", unique=True),
        Index("ix_meals_user_date", "user_id", "date", "deleted_at"),
    )


class Food(TenantMixin, Base):
    """Caché de ingredientes: macros por 100 g y gramos por unidad habitual."""

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    norm: Mapped[str] = mapped_column(String(160))
    kcal100: Mapped[float] = mapped_column(Float)
    protein100: Mapped[float] = mapped_column(Float)
    carbs100: Mapped[float] = mapped_column(Float)
    fat100: Mapped[float] = mapped_column(Float)
    fiber100: Mapped[float | None] = mapped_column(Float, nullable=True)
    alcohol100: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_grams: Mapped[dict] = mapped_column(JSON, default=dict)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ux_foods_user_norm", "user_id", "norm", unique=True),)


class Weight(TenantMixin, Base):
    __tablename__ = "weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10))
    kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ux_weights_user_date", "user_id", "date", unique=True),)


class WeeklySummary(TenantMixin, Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[str] = mapped_column(String(10))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ux_weekly_user_week", "user_id", "week_start", unique=True),)


class Achievement(TenantMixin, Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ux_achievements_user_key", "user_id", "key", unique=True),)


class Counter(TenantMixin, Base):
    __tablename__ = "counters"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40))
    value: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ux_counters_user_key", "user_id", "key", unique=True),)


class AiUsage(TenantMixin, Base):
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    calls: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ux_ai_usage_user_date_kind", "user_id", "date", "kind", unique=True),)


class Product(TenantMixin, Base):
    """Producto envasado del usuario, con las cifras de su etiqueta nutricional."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # Cómo lo dirá el usuario al apuntar ("yogur ligero"). Es lo primero con lo que se empareja.
    alias: Mapped[str] = mapped_column(String(60), default="")
    basis: Mapped[str] = mapped_column(String(2), default="g")  # la tabla va por 100 g o por 100 ml
    kcal100: Mapped[float] = mapped_column(Float)
    protein100: Mapped[float] = mapped_column(Float)
    carbs100: Mapped[float] = mapped_column(Float)
    fat100: Mapped[float] = mapped_column(Float)
    fiber100: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugars100: Mapped[float | None] = mapped_column(Float, nullable=True)
    salt100: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Lo que pesa UNA unidad ("yogur" = 125 g): con esto, «dos yogures» se multiplica solo.
    unit_label: Mapped[str] = mapped_column(String(30), default="")
    unit_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_image: Mapped[bool] = mapped_column(Boolean, default=False)
    # Código de barras (EAN/UPC), si se guardó escaneándolo. Único por usuario; varios sin código, sin problema.
    barcode: Mapped[str | None] = mapped_column(String(14), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (Index("ux_products_user_barcode", "user_id", "barcode", unique=True),)


class ProductImage(TenantMixin, Base):
    """Foto de la etiqueta. Aparte de Product para no arrastrarla en cada listado."""

    __tablename__ = "product_images"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    mime: Mapped[str] = mapped_column(String(30))
    data: Mapped[bytes] = mapped_column(LargeBinary)


class AppSetting(Base):
    """Ajustes globales de la instalación que cambia el administrador (pausar la IA, abrir el registro...)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict | list | str | int | bool | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AdminAudit(Base):
    """Registro de cada acción de administración: quién, qué, a quién y cuándo."""

    __tablename__ = "admin_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(40))
    # Sin clave foránea: la fila sobrevive al borrado de la cuenta afectada.
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_username: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BarcodeCache(Base):
    """Respuestas de Open Food Facts por código (también «no existe»). Datos públicos, sin nada del usuario."""

    __tablename__ = "barcode_cache"

    code: Mapped[str] = mapped_column(String(14), primary_key=True)
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserPrefs(TenantMixin, Base):
    """Preferencias del usuario (objetivo de agua, días de entreno, avisos...). JSON validado por schemas.Prefs."""

    __tablename__ = "user_prefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ux_user_prefs_user", "user_id", unique=True),)


class WaterLog(TenantMixin, Base):
    """Un vaso, una botella...: cada toque en +250 es una fila, para poder deshacerlo."""

    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Generado en el cliente: hace idempotente la cola offline.
    client_id: Mapped[str] = mapped_column(String(40))
    date: Mapped[str] = mapped_column(String(10))
    ml: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ux_water_user_client", "user_id", "client_id", unique=True),
        Index("ix_water_user_date", "user_id", "date"),
    )


MEASURES = ("waist", "chest", "arm", "hip", "thigh")


class BodyMeasurement(TenantMixin, Base):
    """Medidas corporales de un día, en centímetros (cintura, pecho, brazo, cadera y muslo)."""

    __tablename__ = "body_measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10))
    waist: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest: Mapped[float | None] = mapped_column(Float, nullable=True)
    arm: Mapped[float | None] = mapped_column(Float, nullable=True)
    hip: Mapped[float | None] = mapped_column(Float, nullable=True)
    thigh: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ux_measurements_user_date", "user_id", "date", unique=True),)


class ProgressPhoto(TenantMixin, Base):
    """Foto de progreso, ya reducida en el móvil. Los listados no cargan `data` (se pide aparte)."""

    __tablename__ = "progress_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(40))
    date: Mapped[str] = mapped_column(String(10))
    mime: Mapped[str] = mapped_column(String(30))
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    __table_args__ = (
        Index("ux_photos_user_client", "user_id", "client_id", unique=True),
        Index("ix_photos_user_date", "user_id", "date"),
    )
