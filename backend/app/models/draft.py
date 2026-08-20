"""Draft and draft-pick tracking (supports live manual entry)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    draft_type: Mapped[str] = mapped_column(String(20), default="snake")  # snake|linear|auction
    rounds: Mapped[int] = mapped_column(Integer, default=16)
    my_slot: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|live|complete
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    picks: Mapped[list["DraftPick"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class DraftPick(Base):
    __tablename__ = "draft_picks"

    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id"), index=True)
    overall_pick: Mapped[int] = mapped_column(Integer)  # 1-based overall
    round: Mapped[int] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)  # draft slot / team that made the pick
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    is_mine: Mapped[bool] = mapped_column(Boolean, default=False)
    keeper: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    draft: Mapped["Draft"] = relationship(back_populates="picks")
