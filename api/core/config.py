"""ME2 application settings — loaded from .env via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://me2:change_me_in_production@localhost:5432/me2"

    # JWT
    jwt_secret_key: str = "change_me_to_a_random_secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    log_level: str = "INFO"

    # Collector
    collector_cycle_seconds: float = 1.0
    equipment_config_path: str = "../config/equipment.json"
    sqlite_buffer_path: str = "./collector/buffer.db"


settings = Settings()
