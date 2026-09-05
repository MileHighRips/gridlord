"""Projection & ranking output schemas."""
from __future__ import annotations

from pydantic import BaseModel


class ProjectionOut(BaseModel):
    player_id: int
    week: int
    mean_points: float
    std_points: float
    floor_points: float | None = None
    ceiling_points: float | None = None
    is_ensemble: bool = False

    model_config = {"from_attributes": True}


class RankingRow(BaseModel):
    rank: int
    player_id: int
    name: str
    position: str
    team: str | None = None
    proj_points: float
    proj_points_standard: float = 0.0  # league scoring minus yardage bonuses
    vorp: float
    positional_rank: int
    adp: float | None = None
    adp_delta: float | None = None  # positive = value (falling further than talent)
    volatility: float
    upside_score: float
    tier: int
    # Top-3 explainability drivers, e.g. ["+3.1 VORP vs replacement", ...]
    drivers: list[str]
    ecr: float | None = None
    ecr_delta: float | None = None
    boom_pct: float | None = None
    bust_pct: float | None = None
    consensus_rank: int | None = None
    adp_divergence: float | None = None
    usage_score: float | None = None
    role_note: str | None = None
