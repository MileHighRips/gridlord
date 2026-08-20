"""League import/export schemas — the canonical league JSON contract."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScoringConfig(BaseModel):
    """Scoring block. `rules` maps stat keys -> point weights.

    Bonus/threshold keys use the convention `bonus_<stat>_<threshold>`, e.g.
    `bonus_rush_yd_100`. The scoring engine awards the points once the raw stat
    reaches the embedded threshold.
    """

    type: str = Field("PPR", description="PPR | Half-PPR | Standard | Custom")
    rules: dict[str, float] = Field(default_factory=dict)


class RosterConfig(BaseModel):
    starters: dict[str, int] = Field(
        default_factory=dict,
        description="Position -> count, e.g. {'QB':1,'RB':2,'WR':2,'TE':1,'FLEX':1}",
    )
    bench: int = 6
    ir_slots: int = 2


class WaiverRules(BaseModel):
    type: str = "rolling"  # FAAB | rolling
    budget: int = 100
    reset: str = "weekly"
    process_day: str = "Tuesday"
    clear_days: int = 2


class TradeRules(BaseModel):
    review: str = "commissioner"  # commissioner | league_vote | none
    veto_votes: int = 0
    reject_days: int = 2
    deadline: str | None = None
    allow_draft_pick_trades: bool = False


class KeeperRules(BaseModel):
    count: int = 0
    cost_increase: str | None = None  # e.g. "+1_pick"


class LeagueSettingsIn(BaseModel):
    """Full manual-entry payload (also the shape stored/returned)."""

    leagueName: str
    teams: int = 12
    season: int = 2026
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    roster: RosterConfig = Field(default_factory=RosterConfig)
    waiver: WaiverRules = Field(default_factory=WaiverRules)
    trades: TradeRules = Field(default_factory=TradeRules)
    keepers: KeeperRules = Field(default_factory=KeeperRules)
    playoff_teams: int = 6
    playoff_start_week: int = 15
    playoff_end_week: int = 17
    fractional_points: bool = True
    negative_points: bool = True


class LeagueImportRequest(BaseModel):
    """POST /api/leagues/import body."""

    provider: str = Field("manual", description="manual|espn|yahoo|sleeper|nfl")
    leagueSettingsJson: dict = Field(
        ..., description="Raw league JSON in provider or canonical shape"
    )


class LeagueOut(BaseModel):
    id: int
    name: str
    provider: str
    season: int
    num_teams: int
    scoring_type: str
    settings: LeagueSettingsIn

    model_config = {"from_attributes": True}


class LeagueImportResponse(BaseModel):
    league: LeagueOut
    mapping_accuracy: float = Field(..., description="Fraction of fields auto-mapped 0..1")
    warnings: list[str] = Field(default_factory=list)
    unmapped_fields: list[str] = Field(default_factory=list)
