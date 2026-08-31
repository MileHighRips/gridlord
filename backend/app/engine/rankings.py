"""Ranking engine: VORP, positional scarcity, tiers, ADP delta, explainability.

Produces per-week and rest-of-season rankings with a top-3 "drivers" list for
each player so every ranking is explainable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# Replacement-level rank per position for a typical starting requirement.
# Tunable per league (num_teams * starters_at_position).
DEFAULT_REPLACEMENT_RANK = {
    "QB": 14,
    "RB": 26,  # slightly lower replacement floor so elite RBs stay near the top
    "WR": 32,
    "TE": 12,
    "K": 14,
    "DEF": 14,
}

# ECR (expert consensus) is a scoring-agnostic market prior. The engine should
# trust it more heavily when setting the order *within* a position; scoring-
# driven VORP still sets overall positional value.
MARKET_WITHIN_POS = 0.85
ECR_BLEND_WEIGHT = 0.55
ECR_CLAMP = 1.25


@dataclass
class PlayerProjection:
    player_id: int
    name: str
    position: str
    team: str | None
    proj_points: float
    std_points: float
    adp: float | None = None
    last_year_points: float | None = None
    injury_status: str | None = None
    play_probability: float | None = None
    ecr: float | None = None
    ecr_std: float | None = None
    ecr_delta: float | None = None
    boom_pct: float | None = None
    bust_pct: float | None = None
    consensus_rank: int | None = None
    usage_score: float | None = None
    role_note: str | None = None
    volatility_index: float | None = None


@dataclass
class RankedPlayer:
    rank: int
    player_id: int
    name: str
    position: str
    team: str | None
    proj_points: float
    vorp: float
    positional_rank: int
    adp: float | None
    adp_delta: float | None
    volatility: float
    upside_score: float
    tier: int
    drivers: list[str]
    ecr: float | None = None
    ecr_delta: float | None = None
    boom_pct: float | None = None
    bust_pct: float | None = None
    consensus_rank: int | None = None
    adp_divergence: float | None = None
    usage_score: float | None = None
    role_note: str | None = None


def compute_replacement_levels(
    players: list[PlayerProjection],
    replacement_rank: dict[str, int] | None = None,
) -> dict[str, float]:
    """Replacement level = projected points of the Nth-ranked player at a position."""
    replacement_rank = replacement_rank or DEFAULT_REPLACEMENT_RANK
    levels: dict[str, float] = {}
    by_pos: dict[str, list[float]] = {}
    for p in players:
        by_pos.setdefault(p.position, []).append(p.proj_points)
    for pos, pts in by_pos.items():
        pts_sorted = sorted(pts, reverse=True)
        idx = min(replacement_rank.get(pos, len(pts_sorted)) - 1, len(pts_sorted) - 1)
        levels[pos] = pts_sorted[max(idx, 0)]
    return levels


def _assign_tiers(vorps: list[float], gap_factor: float = 0.75) -> list[int]:
    """Cluster into tiers using drop-off gaps (larger-than-average gap => new tier)."""
    if not vorps:
        return []
    order = sorted(range(len(vorps)), key=lambda i: -vorps[i])
    diffs = [vorps[order[i]] - vorps[order[i + 1]] for i in range(len(order) - 1)]
    avg_gap = (np.mean([d for d in diffs if d > 0]) if diffs else 0.0) or 1e-9
    tiers = [0] * len(vorps)
    tier = 1
    tiers[order[0]] = tier
    for i in range(1, len(order)):
        if vorps[order[i - 1]] - vorps[order[i]] > avg_gap * (1 + gap_factor):
            tier += 1
        tiers[order[i]] = tier
    return tiers


def rank_players(
    players: list[PlayerProjection],
    replacement_rank: dict[str, int] | None = None,
) -> list[RankedPlayer]:
    """Rank players by VORP with scarcity-aware tiers and explainability drivers."""
    if not players:
        return []

    replacement = compute_replacement_levels(players, replacement_rank)

    pos_sorted: dict[str, list[int]] = {}
    for pos in {p.position for p in players}:
        ids = sorted(
            [p for p in players if p.position == pos], key=lambda x: -x.proj_points
        )
        pos_sorted[pos] = [p.player_id for p in ids]

    enriched = []
    vorps = []
    for p in players:
        repl = replacement.get(p.position, 0.0)
        vorp = p.proj_points - repl
        vorps.append(vorp)
        positional_rank = pos_sorted[p.position].index(p.player_id) + 1
        volatility = round(p.std_points / (p.proj_points + 1e-6), 3)
        upside = round((p.std_points * 1.04), 2)
        enriched.append(
            {
                "p": p,
                "vorp": round(vorp, 2),
                "positional_rank": positional_rank,
                "volatility": volatility,
                "upside": upside,
            }
        )

    tiers = _assign_tiers(vorps)
    for e, tier in zip(enriched, tiers):
        e["tier"] = tier

    # --- Ensemble ordering -------------------------------------------------
    # Scoring-driven VORP decides how valuable each position is (so heavy passing
    # scoring lifts QBs as a group). Expert consensus (ECR) decides the order
    # *within* a position, so the marquee players the market/analysts rank highest
    # (e.g. Allen, Lamar) sit atop their position instead of raw-projection noise.
    from collections import defaultdict as _dd

    by_pos: dict[str, list] = _dd(list)
    for e in enriched:
        by_pos[e["p"].position].append(e)

    for _pos, group in by_pos.items():
        vorps_desc = sorted((g["vorp"] for g in group), reverse=True)
        have_ecr = sorted((g for g in group if g["p"].ecr), key=lambda g: g["p"].ecr)
        no_ecr = sorted((g for g in group if not g["p"].ecr), key=lambda g: -g["vorp"])
        market_order = have_ecr + no_ecr
        for i, g in enumerate(market_order):
            market_vorp = vorps_desc[i]  # value of the i-th best slot at this position
            w = MARKET_WITHIN_POS if g["p"].ecr else 0.0
            # Heavier consensus weighting keeps tier-1 stars like Bijan / Gibbs near
            # the top of the board while still preserving slot-specific VORP value.
            if g["p"].ecr:
                w = max(w, ECR_BLEND_WEIGHT)
            g["blended"] = (1.0 - w) * g["vorp"] + w * market_vorp

    enriched.sort(key=lambda e: -e["blended"])

    ranked: list[RankedPlayer] = []
    for overall_idx, e in enumerate(enriched, start=1):
        p: PlayerProjection = e["p"]
        adp_delta = None
        if p.adp is not None:
            adp_delta = round(p.adp - overall_idx, 1)
        adp_divergence = None
        if p.adp is not None and p.ecr:
            adp_divergence = round(p.adp - p.ecr, 1)  # + = experts higher than ADP

        drivers = _build_drivers(e, overall_idx, adp_delta)
        ranked.append(
            RankedPlayer(
                rank=overall_idx,
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                team=p.team,
                proj_points=round(p.proj_points, 1),
                vorp=e["vorp"],
                positional_rank=e["positional_rank"],
                adp=p.adp,
                adp_delta=adp_delta,
                volatility=e["volatility"],
                upside_score=e["upside"],
                tier=e["tier"],
                drivers=drivers,
                ecr=p.ecr,
                ecr_delta=p.ecr_delta,
                boom_pct=p.boom_pct,
                bust_pct=p.bust_pct,
                consensus_rank=p.consensus_rank,
                adp_divergence=adp_divergence,
                usage_score=p.usage_score,
                role_note=p.role_note,
            )
        )
    return ranked


def _build_drivers(e: dict, overall_rank: int, adp_delta: float | None) -> list[str]:
    """Top-3 human-readable drivers behind a ranking."""
    p: PlayerProjection = e["p"]
    drivers = [
        f"+{e['vorp']:.1f} VORP over {p.position} replacement",
        f"{p.position}{e['positional_rank']} in projected points ({p.proj_points:.1f})",
    ]
    # Injury signal takes priority when material.
    if p.injury_status and (p.play_probability is not None and p.play_probability < 0.95):
        drivers.insert(
            1, f"⚠ {p.injury_status} — projection discounted for availability"
        )
    # Expert consensus + movement.
    if p.ecr:
        if p.ecr_delta and abs(p.ecr_delta) >= 2:
            arrow = "▲ rising" if p.ecr_delta > 0 else "▼ falling"
            drivers.append(f"Experts: ECR {p.ecr:.0f} ({arrow} {abs(p.ecr_delta):.0f})")
        else:
            drivers.append(f"Expert consensus ECR {p.ecr:.0f}")
    if p.role_note:
        drivers.append(p.role_note)
    if adp_delta is not None and abs(adp_delta) >= 4:
        if adp_delta > 0:
            drivers.append(
                f"Value: ADP {p.adp:.0f} vs talent rank {overall_rank} (+{adp_delta:.0f})"
            )
        else:
            drivers.append(
                f"Caution: drafted {abs(adp_delta):.0f} spots ahead of talent rank"
            )
    elif p.last_year_points is not None and p.last_year_points > 0:
        trend = p.proj_points - p.last_year_points
        arrow = "↑" if trend > 8 else ("↓" if trend < -8 else "→")
        drivers.append(
            f"2025 actual {p.last_year_points:.0f} pts {arrow} 2026 proj {p.proj_points:.0f}"
        )
    elif e["volatility"] > 0.35:
        drivers.append(f"High volatility ({e['volatility']:.0%}) — boom/bust upside")
    else:
        drivers.append(f"Ceiling +{e['upside']:.1f} pts above projection")
    return drivers[:3]
