from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kcalia"
    domain: str = "localhost"
    tz: str = "Europe/Madrid"

    data_dir: Path = Path("./data")
    backup_dir: Path = Path("./backups")
    static_dir: Path = Path("./static")
    backup_keep: int = 7

    # Copia fuera del servidor (S3 compatible: AWS, Cloudflare R2, Backblaze B2, MinIO...). Vacío = solo copia local.
    backup_remote_url: str = ""
    backup_remote_bucket: str = ""
    backup_remote_prefix: str = "kcalia/"
    backup_remote_region: str = "auto"
    backup_remote_access_key: str = ""
    backup_remote_secret_key: str = ""
    backup_remote_keep: int = 30
    # Frase para cifrar las copias externas (AES-256-GCM). Vacía = sin cifrar (el almacenamiento debe ser privado).
    backup_encryption_key: str = ""

    session_days: int = 180
    # Comprime respuestas desde la propia app. Detrás de Caddy sobra (comprime él, con zstd); útil sin proxy.
    gzip: bool = False
    cookie_secure: bool = True

    ai_base_url: str = "https://api.moonshot.ai/v1"
    ai_api_key: str = ""
    ai_model: str = "kimi-k2.6"
    # Fotos: vacío = se usa el mismo modelo, proveedor y clave que para el texto. Rellenar solo
    # si prefieres otro modelo (o incluso otro proveedor compatible con OpenAI) para las imágenes.
    ai_vision_model: str = ""
    ai_vision_base_url: str = ""
    ai_vision_api_key: str = ""
    # Tope GLOBAL de consultas de IA al día entre todos los usuarios (texto y foto).
    ai_daily_limit: int = 60
    # Tope por usuario; el admin puede cambiarlo a cada uno desde el panel.
    ai_user_daily_limit: int = 20
    # Límite propio del administrador: no le bloquea lo que gasten los demás. 0 = igual que AI_DAILY_LIMIT.
    admin_ai_daily_limit: int = 0
    ai_timeout: float = 45.0
    # Precios por millón de tokens, solo para estimar el coste en el panel de administración.
    ai_price_input: float = 0.95
    ai_price_output: float = 4.00

    stt_base_url: str = "http://stt:8000/v1"
    stt_api_key: str = ""
    stt_model: str = "small"
    # Tope global de audios al día y tope por usuario.
    stt_daily_limit: int = 100
    stt_user_daily_limit: int = 30
    stt_timeout: float = 60.0
    # Coste estimado de cada audio (0 con el Whisper propio).
    stt_price_per_call: float = 0.0

    # Web Push (recordatorios y avisos al admin). Se generan con scripts/gen-vapid.py; vacías = sin notificaciones.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    # Contacto para los servicios de push (mailto: o https:). Vacío = https://DOMAIN (Apple rechaza «localhost»).
    vapid_subject: str = ""

    # Sugerencia para cerrar el día: a partir de cuántas calorías restantes aparece (cada usuario puede cambiarlo).
    suggest_min_kcal: int = 80

    # Open Food Facts (códigos de barras). Solo se cambia en pruebas, para apuntar a uno simulado.
    off_base_url: str = "https://world.openfoodfacts.org"

    # Registro de cuentas: abierto (toda cuenta nueva espera aprobación) o cerrado del todo.
    allow_signup: bool = True
    # Con tantas solicitudes pendientes, el registro se pausa hasta que el admin las revise.
    max_pending_accounts: int = 20

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kcalia.db"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def vision_model(self) -> str:
        return self.ai_vision_model or self.ai_model

    @property
    def vision_base_url(self) -> str:
        return self.ai_vision_base_url or self.ai_base_url

    @property
    def vision_api_key(self) -> str:
        return self.ai_vision_api_key or self.ai_api_key

    @property
    def push_configured(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)

    @property
    def admin_ai_limit(self) -> int:
        return self.admin_ai_daily_limit or self.ai_daily_limit


@lru_cache
def get_settings() -> Settings:
    return Settings()
