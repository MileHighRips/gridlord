"""Canonical default league settings — your real league ("The League").

14-team, Head-to-Head, PPR with bonus yardage. Sourced from league screenshots.
Used as the default seed and as the fallback when no settings are provided.
"""
from __future__ import annotations

from .engine.scoring import DEFAULT_SCORING
from .schemas.league import (
    KeeperRules,
    LeagueSettingsIn,
    RosterConfig,
    ScoringConfig,
    TradeRules,
    WaiverRules,
)

DEFAULT_LEAGUE = LeagueSettingsIn(
    leagueName="The League",
    teams=10,
    season=2026,
    scoring=ScoringConfig(type="PPR", rules=DEFAULT_SCORING),
    roster=RosterConfig(
        starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1},
        bench=6,
        ir_slots=2,
    ),
    waiver=WaiverRules(
        type="rolling", budget=100, reset="weekly",
        process_day="Tuesday", clear_days=2,
    ),
    trades=TradeRules(
        review="commissioner", veto_votes=0, reject_days=2,
        deadline="2026-11-28", allow_draft_pick_trades=False,
    ),
    keepers=KeeperRules(count=0),
    playoff_teams=6,
    playoff_start_week=15,
    playoff_end_week=17,
    fractional_points=True,
    negative_points=True,
)
