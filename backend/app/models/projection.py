"""Projections, projection sources, and ADP entries."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProjectionSource(Base):
    """A named projection provider with a tracked historical accuracy weight."""

    __tablename__ = "projection_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    # Weight in [0,1] derived from historical accuracy (lower MAE => higher weight).
    accuracy_weight: Mapped[float] = mapped_column(Float, default=1.0)


class Projection(Base):
    """A raw or ensemble projection for a player-week (week=0 means ROS/season)."""

    __tablename__ = "projections"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("projection_sources.id"), nullable=True
    )
    season: Mapped[int] = mapped_column(Integer, default=2026)
    week: Mapped[int] = mapped_column(Integer, default=0)  # 0 = season/ROS

    # Fantasy points for the league's scoring (filled by scoring engine).
    mean_points: Mapped[float] = mapped_column(Float, default=0.0)
    # Uncertainty band: std dev of the points distribution.
    std_points: Mapped[float] = mapped_column(Float, default=0.0)
    floor_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    ceiling_points: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Boom/bust probability model (share of weeks above/below thresholds).
    boom_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    bust_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw stat line stored as compact JSON string for scoring recomputation.
    raw_stats_json: Mapped[str | None] = mapped_column(String, nullable=True)

    is_ensemble: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ADPEntry(Base):
    __tablename__ = "adp_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    source: Mapped[str] = mapped_column(String(50), default="consensus")
    format: Mapped[str] = mapped_column(String(20), default="PPR")
    adp: Mapped[float] = mapped_column(Float)
    rostered_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
