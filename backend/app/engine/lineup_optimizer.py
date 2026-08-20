"""Weekly lineup optimizer.

Greedy fill by descending projected points respecting position eligibility and
FLEX/SuperFlex slots. This is optimal for standard lineup constraints because
slots form a matroid once eligibility is enforced.
"""
from __future__ import annotations

from dataclasses import dataclass

FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE = {"QB", "RB", "WR", "TE"}


@dataclass
class LineupPlayer:
    player_id: int
    name: str
    position: str
    proj_points: float
    opponent_adj: float = 0.0  # matchup adjustment added to projection


def _eligible(slot: str, position: str) -> bool:
    if slot == position:
        return True
    if slot in ("FLEX", "W/R/T", "WRT"):
        return position in FLEX_ELIGIBLE
    if slot in ("SUPERFLEX", "SFLEX", "Q/W/R/T"):
        return position in SUPERFLEX_ELIGIBLE
    return False


def _slot_flexibility(slot: str) -> int:
    if slot in ("SUPERFLEX", "SFLEX", "Q/W/R/T"):
        return 3
    if slot in ("FLEX", "W/R/T", "WRT"):
        return 2
    return 1


def optimize_lineup(players: list[LineupPlayer], slots: list[str]) -> dict:
    """Assign players to starting slots to maximize projected points.

    `slots` is the flattened starting lineup, e.g.
    ["QB","RB","RB","WR","WR","TE","FLEX","K","DEF"].
    """
    scored = sorted(players, key=lambda p: p.proj_points + p.opponent_adj, reverse=True)
    slot_order = sorted(range(len(slots)), key=lambda i: _slot_flexibility(slots[i]))

    assignment: dict[int, LineupPlayer] = {}
    used: set[int] = set()
    for si in slot_order:
        slot = slots[si]
        for p in scored:
            if p.player_id in used:
                continue
            if _eligible(slot, p.position):
                assignment[si] = p
                used.add(p.player_id)
                break

    starters = [
        {
            "slot": slots[si],
            "player_id": assignment[si].player_id,
            "name": assignment[si].name,
            "position": assignment[si].position,
            "proj_points": round(
                assignment[si].proj_points + assignment[si].opponent_adj, 2
            ),
        }
        for si in range(len(slots))
        if si in assignment
    ]
    bench = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "position": p.position,
            "proj_points": round(p.proj_points + p.opponent_adj, 2),
        }
        for p in scored
        if p.player_id not in used
    ]
    projected_total = round(sum(s["proj_points"] for s in starters), 2)
    return {"projected_total": projected_total, "starters": starters, "bench": bench}
