"""Hidden-gem discovery.

Flags undervalued players by comparing projection vs. ADP-implied expectation,
weighted by usage trend and inverse rostered percentage across platforms.

    score = (projection - adp_equivalent) * usage_trend * (1 - rostered_pct)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class GemCandidate:
    player_id: int
    name: str
    position: str
    proj_points: float
    adp: float | None
    rostered_pct: float  # 0..1
    usage_trend: float = 1.0  # >1 rising snap/target share
    pickup_velocity: float = 0.0  # adds per day across platforms


def _adp_equivalent_points(players: list[GemCandidate]) -> dict[int, float]:
    """Fit projected points vs ADP *within each position* for a fair baseline.

    A global fit mixes positional scoring scales (QBs score far more than TEs)
    and produces garbage deltas, so we fit one curve per position.
    """
    by_pos: dict[str, list[GemCandidate]] = {}
    for p in players:
        by_pos.setdefault(p.position, []).append(p)

    out: dict[int, float] = {}
    for pos, group in by_pos.items():
        have_adp = [(p.adp, p.proj_points) for p in group if p.adp is not None]
        if len(have_adp) < 4:
            for p in group:
                out[p.player_id] = p.proj_points  # not enough data -> no delta
            continue
        adps = np.array([a for a, _ in have_adp])
        pts = np.array([q for _, q in have_adp])
        coef = np.polyfit(np.log(adps + 1), pts, 1)  # points ~ a + b*log(adp)
        for p in group:
            out[p.player_id] = (
                p.proj_points
                if p.adp is None
                else float(np.polyval(coef, np.log(p.adp + 1)))
            )
    return out


def find_hidden_gems(
    players: list[GemCandidate],
    delta_threshold: float = 8.0,
    max_rostered: float = 0.6,
    top_n: int = 25,
) -> list[dict]:
    """Return undervalued players sorted by gem score."""
    adp_eq = _adp_equivalent_points(players)
    gems = []
    for p in players:
        if p.rostered_pct > max_rostered:
            continue
        delta = p.proj_points - adp_eq[p.player_id]
        if delta < delta_threshold:
            continue
        score = delta * p.usage_trend * (1.0 - p.rostered_pct)
        gems.append(
            {
                "player_id": p.player_id,
                "name": p.name,
                "position": p.position,
                "gem_score": round(score, 2),
                "projection_vs_adp_delta": round(delta, 1),
                "adp": p.adp,
                "rostered_pct": round(p.rostered_pct * 100, 1),
                "usage_trend": p.usage_trend,
                "pickup_velocity": p.pickup_velocity,
                "drivers": [
                    f"Projected {delta:.1f} pts above its ADP tier",
                    f"Only {p.rostered_pct * 100:.0f}% rostered across platforms",
                    (
                        f"Usage trending up (x{p.usage_trend:.2f})"
                        if p.usage_trend > 1.05
                        else f"Waiver velocity {p.pickup_velocity:.0f}/day"
                    ),
                ],
            }
        )
    gems.sort(key=lambda g: -g["gem_score"])
    return gems[:top_n]
