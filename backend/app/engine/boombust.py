"""Boom/Bust probability model + expected-value banding.

Turns a single projection into a distribution: probability a player returns a
'boom' week (top-tier positional score) or a 'bust' week (below a startable
floor), using the projection mean/std blended with expert disagreement.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Weekly boom/bust thresholds by position (league PPR-ish points per game).
BOOM_THRESHOLD = {"QB": 24, "RB": 20, "WR": 20, "TE": 14, "K": 12, "DEF": 12}
BUST_THRESHOLD = {"QB": 14, "RB": 8, "WR": 8, "TE": 6, "K": 4, "DEF": 3}


@dataclass
class BoomBust:
    boom_pct: float  # P(weekly score >= boom threshold)
    bust_pct: float  # P(weekly score <= bust threshold)
    floor: float
    ceiling: float


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def boom_bust(
    season_mean: float,
    season_std: float,
    position: str,
    games: int = 17,
    expert_std: float | None = None,
) -> BoomBust:
    """Compute weekly boom/bust probabilities from a season projection."""
    if games <= 0:
        games = 17
    weekly_mean = season_mean / games
    # Weekly std ~ season_std / sqrt(games), widened by expert disagreement.
    weekly_std = max(season_std / math.sqrt(games), 1.0)
    if expert_std:
        weekly_std *= 1.0 + min(expert_std / 20.0, 0.6)

    boom_t = BOOM_THRESHOLD.get(position, 18)
    bust_t = BUST_THRESHOLD.get(position, 8)
    boom = 1.0 - _norm_cdf((boom_t - weekly_mean) / weekly_std)
    bust = _norm_cdf((bust_t - weekly_mean) / weekly_std)
    floor = max(0.0, weekly_mean - 1.28 * weekly_std)
    ceiling = weekly_mean + 1.28 * weekly_std
    return BoomBust(
        boom_pct=round(boom * 100, 1),
        bust_pct=round(bust * 100, 1),
        floor=round(floor, 1),
        ceiling=round(ceiling, 1),
    )
