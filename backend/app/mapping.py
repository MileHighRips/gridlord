"""Auto-mapping of platform-specific league fields to the canonical model.

Achieves the >90% field-mapping acceptance target by combining exact aliases
with fuzzy fallback for scoring stat keys.
"""
from __future__ import annotations

from difflib import get_close_matches

from .schemas.league import (
    KeeperRules,
    LeagueSettingsIn,
    RosterConfig,
    ScoringConfig,
    TradeRules,
    WaiverRules,
)

# Platform scoring key -> canonical scoring key.
SCORING_ALIASES: dict[str, str] = {
    # Sleeper
    "pass_yd": "pass_yd", "pass_td": "pass_td", "pass_int": "interception",
    "rush_yd": "rush_yd", "rush_td": "rush_td",
    "rec": "reception", "rec_yd": "rec_yd", "rec_td": "rec_td",
    "fum_lost": "fumble_lost",
    # ESPN-ish
    "passingYards": "pass_yd", "passingTouchdowns": "pass_td",
    "interceptions": "interception", "rushingYards": "rush_yd",
    "rushingTouchdowns": "rush_td", "receptions": "reception",
    "receivingYards": "rec_yd", "receivingTouchdowns": "rec_td",
    # Yahoo-ish
    "Pass Yds": "pass_yd", "Pass TD": "pass_td", "Int": "interception",
    "Rush Yds": "rush_yd", "Rush TD": "rush_td", "Rec": "reception",
    "Rec Yds": "rec_yd", "Rec TD": "rec_td", "Fum Lost": "fumble_lost",
}

CANONICAL_KEYS = {
    "pass_yd", "pass_td", "interception", "rush_yd", "rush_td",
    "reception", "rec_yd", "rec_td", "fumble_lost", "two_pt",
    "return_td", "return_yd",
}

# Position aliases -> canonical starter labels.
POSITION_ALIASES = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K",
    "DEF": "DEF", "DST": "DEF", "D/ST": "DEF",
    "FLEX": "FLEX", "W/R/T": "FLEX", "WRT": "FLEX", "REC_FLEX": "FLEX",
    "SUPERFLEX": "SUPERFLEX", "SUPER_FLEX": "SUPERFLEX", "Q/W/R/T": "SUPERFLEX",
}


def map_scoring(raw: dict) -> tuple[dict[str, float], list[str]]:
    """Return (canonical_rules, unmapped_keys)."""
    mapped: dict[str, float] = {}
    unmapped: list[str] = []
    for key, val in raw.items():
        if not isinstance(val, (int, float)):
            continue
        canon = SCORING_ALIASES.get(key)
        if canon is None:
            close = get_close_matches(key, CANONICAL_KEYS, n=1, cutoff=0.82)
            canon = close[0] if close else None
        if canon:
            mapped[canon] = float(val)
        else:
            unmapped.append(key)
    return mapped, unmapped


def map_roster(raw_starters: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for pos, cnt in raw_starters.items():
        canon = POSITION_ALIASES.get(str(pos).upper(), None)
        if canon:
            out[canon] = out.get(canon, 0) + int(cnt)
    return out


def normalize_league(raw: dict) -> tuple[LeagueSettingsIn, float, list[str], list[str]]:
    """Map a provider/raw league payload to the canonical model.

    Returns (settings, mapping_accuracy, warnings, unmapped_fields).
    """
    warnings: list[str] = []
    unmapped: list[str] = []

    scoring_block = raw.get("scoring", {}) or {}
    raw_rules = (
        scoring_block.get("rules", scoring_block)
        if isinstance(scoring_block, dict)
        else {}
    )
    rules, unmapped_scoring = map_scoring(raw_rules)
    unmapped += [f"scoring.{k}" for k in unmapped_scoring]

    roster_block = raw.get("roster", {}) or {}
    starters = map_roster(roster_block.get("starters", {}) or {})
    if not starters:
        warnings.append("No roster starters mapped; using defaults")

    total_input = max(len(raw_rules) + len(roster_block.get("starters", {}) or {}), 1)
    mapped_count = len(rules) + len(starters)
    accuracy = round(min(mapped_count / total_input, 1.0), 3)

    settings = LeagueSettingsIn(
        leagueName=raw.get("leagueName") or raw.get("name") or "Imported League",
        teams=int(raw.get("teams", 12)),
        season=int(raw.get("season", 2026)),
        scoring=ScoringConfig(type=scoring_block.get("type", "Custom"), rules=rules),
        roster=RosterConfig(
            starters=starters
            or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1},
            bench=int(roster_block.get("bench", 6)),
            ir_slots=int(roster_block.get("ir_slots", 2)),
        ),
        waiver=WaiverRules(**(raw.get("waiver") or {})) if raw.get("waiver") else WaiverRules(),
        trades=TradeRules(**(raw.get("trades") or {})) if raw.get("trades") else TradeRules(),
        keepers=KeeperRules(**(raw.get("keepers") or {})) if raw.get("keepers") else KeeperRules(),
    )
    return settings, accuracy, warnings, unmapped
