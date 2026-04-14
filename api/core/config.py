"""ME2 application settings — loaded from .env via pydantic-settings."""

import asyncio
import platform
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Fix asyncpg on Windows — use SelectorEventLoop instead of ProactorEventLoop
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Find .env file — check CWD, parent, and project root
_env_candidates = [
    Path(".env"),
    Path("../.env"),
    Path(__file__).resolve().parent.parent.parent / ".env",
]
_env_file = next((p for p in _env_candidates if p.exists()), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
