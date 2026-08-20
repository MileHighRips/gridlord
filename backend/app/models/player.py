"""Player master record."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cross-platform id map is stored as string columns for portability.
    sleeper_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    espn_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    yahoo_id: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), index=True)
    position: Mapped[str] = mapped_column(String(10), index=True)  # QB/RB/WR/TE/K/DEF
    team: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bye_week: Mapped[int | None] = mapped_column(Integer, nullable=True)

    age: Mapped[float | None] = mapped_column(Float, nullable=True)
    years_exp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    injury_status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # Q/D/O/IR
    play_probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    depth_chart_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Prior-season fantasy points (league scoring) — context for projections.
    last_year_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    injury_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Expert-consensus (FantasyPros) + advanced intelligence.
    ecr: Mapped[float | None] = mapped_column(Float, nullable=True)  # expert consensus rank
    ecr_std: Mapped[float | None] = mapped_column(Float, nullable=True)  # expert disagreement
    ecr_delta: Mapped[float | None] = mapped_column(Float, nullable=True)  # recent movement
    consensus_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..100
    role_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    volatility_index: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..100
    practice_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
