"""User-authored custom draft board (personal ranking overrides)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CustomBoard(Base):
    """An ordered list of player ids representing a user's personal rankings."""

    __tablename__ = "custom_boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    league_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="My Board")
    # JSON array of player ids in draft-priority order.
    player_ids_json: Mapped[str] = mapped_column(String, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
