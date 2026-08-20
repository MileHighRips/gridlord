"""Re-score stored projections when a league's scoring settings change.

Projections keep their raw Sleeper stat line (``Projection.raw_stats_json``), so
changing scoring in the League Setup form recomputes every player's fantasy
points, floor/ceiling, and boom/bust for the new rules — no re-download needed.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .data_sources import score_defense, score_kicker, score_offense
from .engine.boombust import boom_bust
from .engine.scoring import rules_to_dict
from .models import League, Player, Projection


def league_scoring_dict(league: League) -> dict[str, float]:
    """Flatten a league's ScoringRule rows into an engine scoring dict."""
    return rules_to_dict(league.scoring_rules)


def rescore_projections(db: Session, league: League) -> int:
    """Recompute every stored projection using the league's scoring. Returns count."""
    scoring = league_scoring_dict(league)
    players = {p.id: p for p in db.query(Player).all()}
    projs = db.query(Projection).filter(Projection.week == 0).all()

    updated = 0
    for pr in projs:
        if not pr.raw_stats_json:
            continue
        player = players.get(pr.player_id)
        if not player:
            continue
        try:
            stats = json.loads(pr.raw_stats_json)
        except (ValueError, TypeError):
            continue

        pos = player.position
        if pos == "K":
            base = score_kicker(stats)
        elif pos == "DEF":
            base = score_defense(stats)
        else:
            base = score_offense(stats, scoring)

        factor = player.play_probability if player.play_probability is not None else 1.0
        mean = round(base * factor, 1)
        std = round(mean * (pr.std_points / (pr.mean_points + 1e-6)) if pr.mean_points else mean * 0.3, 1)
        pr.mean_points = mean
        pr.std_points = std
        pr.floor_points = round(mean - 1.04 * std, 1)
        pr.ceiling_points = round(mean + 1.04 * std, 1)
        bb = boom_bust(mean, std, pos, games=17, expert_std=player.ecr_std)
        pr.boom_pct = bb.boom_pct
        pr.bust_pct = bb.bust_pct
        updated += 1

    # Refresh consensus ranking to reflect new points ordering.
    _recompute_consensus(db, players)
    db.commit()
    return updated


def _recompute_consensus(db: Session, players: dict[int, Player]) -> None:
    projs = {
        p.player_id: p.mean_points
        for p in db.query(Projection).filter(Projection.week == 0).all()
    }
    ranked = sorted(players.values(), key=lambda p: -(projs.get(p.id, 0.0)))
    sleeper_rank = {p.id: i + 1 for i, p in enumerate(ranked)}
    for p in players.values():
        s_rank = sleeper_rank.get(p.id, len(players))
        p.consensus_rank = int(round(0.55 * s_rank + 0.45 * p.ecr)) if p.ecr else s_rank
