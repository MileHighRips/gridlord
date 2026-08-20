"""League, settings, roster template, scoring rules, and teams."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(50), default="manual")
    provider_league_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    season: Mapped[int] = mapped_column(Integer, default=2026)
    num_teams: Mapped[int] = mapped_column(Integer, default=12)
    scoring_type: Mapped[str] = mapped_column(String(20), default="PPR")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    settings: Mapped["LeagueSettings"] = relationship(
        back_populates="league", uselist=False, cascade="all, delete-orphan"
    )
    roster_slots: Mapped[list["RosterSlot"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    scoring_rules: Mapped[list["ScoringRule"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    teams: Mapped[list["Team"]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )


class LeagueSettings(Base):
    __tablename__ = "league_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))

    # Bench / IR
    bench_size: Mapped[int] = mapped_column(Integer, default=6)
    ir_slots: Mapped[int] = mapped_column(Integer, default=2)

    # Waivers
    waiver_type: Mapped[str] = mapped_column(String(30), default="rolling")  # FAAB|rolling
    faab_budget: Mapped[int] = mapped_column(Integer, default=100)
    waiver_reset: Mapped[str] = mapped_column(String(20), default="weekly")
    waiver_process_day: Mapped[str] = mapped_column(String(20), default="Tuesday")
    waiver_clear_days: Mapped[int] = mapped_column(Integer, default=2)

    # Trades
    trade_review: Mapped[str] = mapped_column(String(30), default="commissioner")
    trade_veto_votes: Mapped[int] = mapped_column(Integer, default=0)
    trade_reject_days: Mapped[int] = mapped_column(Integer, default=2)
    trade_deadline: Mapped[str | None] = mapped_column(String(20), nullable=True)
    allow_draft_pick_trades: Mapped[bool] = mapped_column(Boolean, default=False)

    # Keepers
    keeper_count: Mapped[int] = mapped_column(Integer, default=0)
    keeper_cost_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Playoffs
    playoff_teams: Mapped[int] = mapped_column(Integer, default=6)
    playoff_start_week: Mapped[int] = mapped_column(Integer, default=15)
    playoff_end_week: Mapped[int] = mapped_column(Integer, default=17)
    playoff_reseeding: Mapped[bool] = mapped_column(Boolean, default=False)

    # Misc
    fractional_points: Mapped[bool] = mapped_column(Boolean, default=True)
    negative_points: Mapped[bool] = mapped_column(Boolean, default=True)
    play_median: Mapped[bool] = mapped_column(Boolean, default=False)

    league: Mapped["League"] = relationship(back_populates="settings")


class RosterSlot(Base):
    """One row per starting slot type with a count (e.g. WR x2, FLEX x1)."""

    __tablename__ = "roster_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    position: Mapped[str] = mapped_column(String(10))  # QB, RB, WR, TE, FLEX, SUPERFLEX, K, DEF, IDP
    count: Mapped[int] = mapped_column(Integer, default=1)

    league: Mapped["League"] = relationship(back_populates="roster_slots")


class ScoringRule(Base):
    """A single stat -> point-weight mapping. Threshold rules use min_value."""

    __tablename__ = "scoring_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    stat: Mapped[str] = mapped_column(String(50))  # e.g. rec, pass_yd, bonus_rush_100
    points: Mapped[float] = mapped_column(Float, default=0.0)
    # For bonus/threshold rules: award `points` when stat >= min_value.
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    applies_to: Mapped[str] = mapped_column(String(20), default="OFF")  # OFF|K|DST

    league: Mapped["League"] = relationship(back_populates="scoring_rules")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    name: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    draft_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_me: Mapped[bool] = mapped_column(Boolean, default=False)

    league: Mapped["League"] = relationship(back_populates="teams")
