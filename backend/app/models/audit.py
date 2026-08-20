"""Audit logs, provider OAuth tokens, and users."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default="manager")  # manager|commissioner|admin
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProviderToken(Base):
    """Minimal OAuth token storage — store only what is necessary; revocable."""

    __tablename__ = "provider_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30))  # espn|yahoo|sleeper|nfl
    access_token: Mapped[str] = mapped_column(String(2000))
    refresh_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Records every ranking refresh / ingestion with the sources used."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80))  # ranking_refresh|adp_ingest|sync
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"), nullable=True)
    sources: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
