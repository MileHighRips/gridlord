"""Aggregated news items with NLP tags."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(80))
    headline: Mapped[str] = mapped_column(String(400))
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Comma-separated tags: injury, role_change, depth_chart, trade, suspension.
    tags: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1..1
    published_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
