"""League-context math: replacement levels scale with league size + roster.

This is what makes a 14-team league rank differently from a 12-team league —
the replacement baseline for VORP is the (teams × starters-at-position)-th best
player, so scarcer positions in bigger leagues gain value exactly as sources
like Flock describe.
"""
from __future__ import annotations

from dataclasses import dataclass

FLEX_ELIGIBLE = {"RB", "WR", "TE"}


@dataclass
class LeagueContext:
    num_teams: int
    starters: dict[str, int]  # position -> starting slots (incl FLEX/SUPERFLEX)
    replacement_rank: dict[str, int]


def _flex_share(starters: dict[str, int]) -> dict[str, float]:
    """Distribute FLEX/SUPERFLEX slots across eligible positions by usage weight."""
    flex = starters.get("FLEX", 0) + starters.get("W/R/T", 0)
    superflex = starters.get("SUPERFLEX", 0) + starters.get("SUPER_FLEX", 0)
    share = {"RB": 0.0, "WR": 0.0, "TE": 0.0, "QB": 0.0}
    if flex:
        # Empirically RB/WR soak most flex usage, TE a little.
        share["RB"] += flex * 0.45
        share["WR"] += flex * 0.45
        share["TE"] += flex * 0.10
    if superflex:
        share["QB"] += superflex * 0.85
        share["RB"] += superflex * 0.05
        share["WR"] += superflex * 0.10
    return share


def build_league_context(num_teams: int, starters: dict[str, int]) -> LeagueContext:
    """Compute per-position replacement ranks for VORP given league settings."""
    flex_share = _flex_share(starters)
    replacement: dict[str, int] = {}
    for pos in ("QB", "RB", "WR", "TE", "K", "DEF"):
        base = starters.get(pos, 0) + flex_share.get(pos, 0.0)
        # Replacement is the last startable player across the league, plus a
        # small streaming buffer so waiver-level players anchor the baseline.
        rank = int(round(num_teams * base)) + (num_teams // 2 if pos in FLEX_ELIGIBLE else 2)
        replacement[pos] = max(rank, num_teams)
    return LeagueContext(num_teams=num_teams, starters=starters,
                        replacement_rank=replacement)


def default_starters_from_slots(slots: list) -> dict[str, int]:
    """From ORM RosterSlot rows -> {position: count} (FLEX kept separate)."""
    out: dict[str, int] = {}
    for s in slots:
        out[s.position] = out.get(s.position, 0) + s.count
    return out
