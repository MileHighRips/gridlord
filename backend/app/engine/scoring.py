"""Fantasy scoring engine.

Computes fantasy points from a raw stat line for an arbitrary league scoring
configuration, including per-yard weights, TD points, negative events, kicker
distance buckets, DST points-allowed tiers, and yardage **bonus thresholds**.

The default configuration (:data:`DEFAULT_SCORING`) mirrors your real league
("The League") — 14-team H2H PPR with bonus yardage.
"""
from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Default scoring — matches the league screenshots exactly.
# --------------------------------------------------------------------------- #
DEFAULT_SCORING: dict[str, float] = {
    # Passing
    "pass_yd": 0.04,  # 25 yards per point
    "pass_td": 4.0,
    "interception": -1.0,
    "bonus_pass_yd_200": 3.0,
    "bonus_pass_yd_250": 5.0,
    "bonus_pass_yd_300": 7.0,
    # Rushing
    "rush_yd": 0.1,  # 10 yards per point
    "rush_td": 6.0,
    "bonus_rush_yd_75": 3.0,
    "bonus_rush_yd_100": 5.0,
    "bonus_rush_yd_150": 7.0,
    # Receiving (PPR)
    "reception": 1.0,
    "rec_yd": 0.1,
    "rec_td": 6.0,
    "bonus_rec_yd_75": 3.0,
    "bonus_rec_yd_100": 5.0,
    "bonus_rec_yd_150": 7.0,
    # Returns / misc
    "return_yd": 0.1,
    "return_td": 6.0,
    "two_pt": 2.0,
    "fumble_lost": -2.0,
    "off_fum_ret_td": 6.0,
    # Kicker — makes by distance
    "fg_0_19": 3.0,
    "fg_20_29": 3.0,
    "fg_30_39": 3.0,
    "fg_40_49": 4.0,
    "fg_50_plus": 5.0,
    # Kicker — misses by distance
    "fg_miss_0_19": -3.0,
    "fg_miss_20_29": -3.0,
    "fg_miss_30_39": -2.0,
    "fg_miss_40_49": -2.0,
    "fg_miss_50_plus": -3.0,
    "pat_made": 1.0,
    "pat_miss": -1.0,
    # DST
    "sack": 1.0,
    "def_int": 2.0,
    "fum_rec": 2.0,
    "def_td": 6.0,
    "safety": 2.0,
    "block_kick": 2.0,
    "def_return_td": 6.0,
    "xp_returned": 2.0,
}

# Standard scoring = the league's per-stat weights **without** any yardage
# bonuses. Used to show a "normal" projection next to the bonus-boosted one so
# you can see how much Gage's league bonuses inflate each player.
STANDARD_SCORING: dict[str, float] = {
    k: v for k, v in DEFAULT_SCORING.items() if not k.startswith("bonus_")
}


# DST points-allowed tiers: (inclusive_max_points_allowed, fantasy_points).
DEFAULT_POINTS_ALLOWED_TIERS: list[tuple[int, float]] = [
    (0, 10.0),
    (6, 7.0),
    (13, 4.0),
    (20, 1.0),
    (27, 0.0),
    (34, -1.0),
    (999, -4.0),  # 35+
]

# Yardage bonus rule prefixes -> the raw stat key they read.
_BONUS_STAT_MAP = {
    "bonus_pass_yd_": "pass_yd",
    "bonus_rush_yd_": "rush_yd",
    "bonus_rec_yd_": "rec_yd",
}

# Aliases so callers can pass friendlier stat names.
_ALIASES = {
    "reception": "receptions",
    "def_int": "interceptions_def",
}


@dataclass
class ScoreBreakdown:
    total: float
    components: dict[str, float]


def points_allowed_score(
    points_allowed: int,
    tiers: list[tuple[int, float]] | None = None,
) -> float:
    """Return DST fantasy points for a points-allowed value using tier buckets."""
    tiers = tiers or DEFAULT_POINTS_ALLOWED_TIERS
    for max_pa, pts in tiers:
        if points_allowed <= max_pa:
            return pts
    return tiers[-1][1]


def _bonus_points(
    stat_line: dict[str, float], scoring: dict[str, float]
) -> dict[str, float]:
    """Compute non-cumulative yardage bonuses.

    Only the highest reached threshold in each bonus family is awarded
    (thresholds are treated as replacement tiers, matching Yahoo behaviour).
    """
    families: dict[str, list[tuple[int, float]]] = {}
    for key, pts in scoring.items():
        for prefix, stat in _BONUS_STAT_MAP.items():
            if key.startswith(prefix):
                threshold = int(key[len(prefix):])
                families.setdefault(stat, []).append((threshold, pts))

    awarded: dict[str, float] = {}
    for stat, tiers in families.items():
        value = float(stat_line.get(stat, 0.0))
        best = 0.0
        best_threshold = None
        for threshold, pts in sorted(tiers):
            if value >= threshold:
                best = pts
                best_threshold = threshold
        if best_threshold is not None and best != 0.0:
            awarded[f"bonus_{stat}_{best_threshold}"] = best
    return awarded


def score_stat_line(
    stat_line: dict[str, float],
    scoring: dict[str, float] | None = None,
    points_allowed_tiers: list[tuple[int, float]] | None = None,
    fractional: bool = True,
) -> ScoreBreakdown:
    """Score a raw stat line.

    Cumulative stats use their weight key directly (``pass_yd`` etc.).
    Event counts use the same key (``pass_td``, ``sack``, ``reception``...).
    Defaults to the league's scoring (:data:`DEFAULT_SCORING`).
    """
    scoring = scoring or DEFAULT_SCORING
    components: dict[str, float] = {}

    for key, weight in scoring.items():
        if any(key.startswith(p) for p in _BONUS_STAT_MAP):
            continue  # bonuses handled separately (non-cumulative)
        count = stat_line.get(key)
        if count is None:
            count = stat_line.get(_ALIASES.get(key, key))
        if not count:
            continue
        components[key] = round(float(count) * weight, 4)

    components.update(_bonus_points(stat_line, scoring))

    if "points_allowed" in stat_line:
        components["points_allowed"] = points_allowed_score(
            int(stat_line["points_allowed"]), points_allowed_tiers
        )

    total = sum(components.values())
    if not fractional:
        total = float(round(total))
    return ScoreBreakdown(total=round(total, 2), components=components)


def rules_to_dict(scoring_rules) -> dict[str, float]:
    """Convert ORM ScoringRule rows into a flat scoring dict for the engine."""
    out: dict[str, float] = {}
    for rule in scoring_rules:
        if rule.min_value is not None:
            out[f"bonus_{rule.stat}_{int(rule.min_value)}"] = rule.points
        else:
            out[rule.stat] = rule.points
    return out
