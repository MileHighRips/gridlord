"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./gridiron.db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    sleeper_base: str = "https://api.sleeper.app/v1"
    espn_swid: str = ""
    espn_s2: str = ""
    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""


settings = Settings()
