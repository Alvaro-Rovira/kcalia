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

    session_days: int = 180
    cookie_secure: bool = True

    ai_base_url: str = "https://api.moonshot.ai/v1"
    ai_api_key: str = ""
    ai_model: str = "kimi-k2.6"
    # Fotos: vacío = se usa el mismo modelo, proveedor y clave que para el texto. Rellenar solo
    # si prefieres otro modelo (o incluso otro proveedor compatible con OpenAI) para las imágenes.
    ai_vision_model: str = ""
    ai_vision_base_url: str = ""
    ai_vision_api_key: str = ""
    ai_daily_limit: int = 60
    ai_timeout: float = 45.0

    stt_base_url: str = "http://stt:8000/v1"
    stt_api_key: str = ""
    stt_model: str = "small"
    stt_daily_limit: int = 100
    stt_timeout: float = 60.0

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
