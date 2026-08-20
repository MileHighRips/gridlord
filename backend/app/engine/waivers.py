"""Waiver / FAAB recommendation engine."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WaiverCandidate:
    player_id: int
    name: str
    position: str
    proj_points_next: float
    ros_points: float
    vorp: float
    rostered_pct: float  # 0..1 across platforms
    trend_factor: float = 1.0  # >1 = rising usage/snap share


def recommend_waivers(
    candidates: list[WaiverCandidate],
    faab_budget: int,
    faab_remaining: int,
    my_needs: list[str],
    top_n: int = 15,
) -> list[dict]:
    """Rank waiver targets and suggest FAAB bids as a % of remaining budget."""
    scored = []
    for c in candidates:
        need_boost = 1.25 if c.position in my_needs else 1.0
        ev = c.vorp * need_boost * c.trend_factor * (1.0 - c.rostered_pct)
        scored.append((ev, c))

    scored.sort(key=lambda x: -x[0])
    top = scored[:top_n]

    max_ev = top[0][0] if top and top[0][0] > 0 else 1.0
    out = []
    for ev, c in top:
        bid_pct = max(0.0, min(0.45, 0.45 * (ev / max_ev)))
        out.append(
            {
                "player_id": c.player_id,
                "name": c.name,
                "position": c.position,
                "expected_value": round(ev, 2),
                "suggested_faab": round(faab_remaining * bid_pct),
                "suggested_faab_pct": round(bid_pct * 100, 1),
                "rostered_pct": round(c.rostered_pct * 100, 1),
                "trend": "rising" if c.trend_factor > 1.05 else "steady",
                "priority": "high" if ev >= max_ev * 0.6 else "speculative",
            }
        )
    return out
