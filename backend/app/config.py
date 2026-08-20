"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./gridiron.db"
    redis_url: str = "redis://localhost:6379/0"

    # Comma-separated allowed CORS origins, or "*" for any (default: any).
    allowed_origins: str = "*"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    sleeper_base: str = "https://api.sleeper.app/v1"
    espn_swid: str = ""
    espn_s2: str = ""
    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        """Normalize managed-Postgres URLs (Render/Heroku) for psycopg 3."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
