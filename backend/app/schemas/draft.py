"""Draft schemas — including the live-draft recommender contract."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DraftPickIn(BaseModel):
    overall_pick: int = Field(..., description="1-based overall pick number")
    player_id: int
    slot: int = Field(..., description="Draft slot / team that made the pick")


class DraftStateIn(BaseModel):
    """Snapshot of a live draft used to generate a recommendation."""

    league_id: int
    num_teams: int = 14
    rounds: int = 16
    my_slot: int = Field(..., description="Your 1-based draft slot")
    draft_type: str = "snake"
    picks_made: list[DraftPickIn] = Field(
        default_factory=list, description="All picks so far, in order"
    )
    # Optional: restrict recommendations to specific positions.
    position_filter: list[str] | None = None


class DraftRecommendation(BaseModel):
    player_id: int
    name: str
    position: str
    team: str | None = None
    proj_points: float
    vorp: float
    need_weighted_value: float
    adp: float | None = None
    reach_risk: str  # "safe" | "slight_reach" | "reach"
    survival_probability: float = Field(
        ..., description="P(available at your next pick) 0..1"
    )
    drivers: list[str]


class DraftRecommendResponse(BaseModel):
    on_the_clock: bool
    your_next_overall_pick: int
    picks_until_next: int
    current_round: int
    roster_needs: dict[str, int]
    scarcity_alerts: list[str]
    recommendations: list[DraftRecommendation]
    best_available_by_position: dict[str, DraftRecommendation | None]
    opponent_styles: list[dict] = []
    predicted_picks: list[dict] = []
    positional_forecast: dict[str, dict] = {}
