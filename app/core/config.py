from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, читаются из переменных окружения и файла .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Ремонтная мастерская"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/repair_shop"
    db_echo: bool = False

    cors_origins: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500"]

    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает единственный (кэшированный) экземпляр настроек."""
    return Settings()


settings = get_settings()
